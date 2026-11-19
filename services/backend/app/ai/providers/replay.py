"""Replay provider serving eval/data/replay fixtures by sha256 or doc_id."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from app.ai.schemas import (
    ExtractionResult,
    OCRLine,
    OCRPage,
    OCRResult,
    OCRWord,
)
from app.core.config import settings

logger = logging.getLogger("ai.providers.replay")


def get_replay_dir() -> Path:
    """Return the resolved replay fixtures directory or raise clear error."""
    return settings.get_replay_fixtures_dir()


# Map of document numbers to doc_id
_DOC_NUMBER_MAP: dict[str, str] = {
    "PR-1001": "s1-pr-1001",
    "Q-1042": "s1-quote-gulfline",
    "Q-8821": "s1-quote-falcon",
    "Q-3055": "s1-quote-corniche",
    "PO-0042": "s1-po-0042",
    "DN-771": "s1-dn-771",
    "DN-772": "s1-dn-772",
    "INV-2291": "s1-inv-2291",
    "PO-0050": "s2-po-0050",
    "INV-5510": "s2-inv-5510",
    "PO-0061": "s3-po-0061",
    "DN-1090": "s3-dn-1090",
    "INV-9041": "s3-inv-9041",
    "Q-4110": "s4-quote-falcon",
    "PO-0075": "s4-po-0075",
    "Q-6201": "s5-quote-sandstone",
    "PO-0088": "s5-po-0088",
    "INV-6001": "s6-inv-6001-vat",
    "INV-6004": "s6-inv-6004-scan",
    "INV-7001": "s7-inv-7001-inj",
}

# Cache for sha256 -> doc_id
_SHA256_TO_DOC_ID: dict[str, str] = {}


def _init_sha256_map() -> None:
    if _SHA256_TO_DOC_ID:
        return
    try:
        from tools.datagen.layouts import render_pdf_to_bytes
        from tools.datagen.scenarios import get_all_scenarios

        for spec in get_all_scenarios():
            pdf_bytes = render_pdf_to_bytes(spec)
            h = hashlib.sha256(pdf_bytes).hexdigest()
            _SHA256_TO_DOC_ID[h] = spec.doc_id
    except Exception as exc:
        logger.debug("Could not precompute scenario hashes: %s", exc)


def resolve_doc_id(
    doc_id: str | None = None,
    file_sha256: str | None = None,
    file_bytes: bytes | None = None,
    text_content: str | None = None,
    replay_dir: Path | None = None,
) -> str:
    """Resolve which replay fixture doc_id to use."""
    r_dir = replay_dir or get_replay_dir()
    if doc_id and (r_dir / f"{doc_id}.di.json").exists():
        return doc_id

    _init_sha256_map()
    if file_sha256 and file_sha256 in _SHA256_TO_DOC_ID:
        return _SHA256_TO_DOC_ID[file_sha256]

    if file_bytes:
        h = hashlib.sha256(file_bytes).hexdigest()
        if h in _SHA256_TO_DOC_ID:
            return _SHA256_TO_DOC_ID[h]

    # Search in text or bytes for known document numbers
    content_str = text_content or ""
    if not content_str and file_bytes:
        if file_bytes.startswith(b"%PDF"):
            try:
                import io

                import pypdf

                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                content_str = "\n".join(p.extract_text() or "" for p in reader.pages)
            except Exception:
                pass
        if not content_str:
            try:
                content_str = file_bytes.decode("utf-8", errors="ignore")
            except Exception:
                pass

    if content_str:
        num_pattern = (
            r"(?:Number|Invoice No|Quote No|PO No|DN No|Delivery Note No)"
            r"[\.\:]?\s*([A-Za-z0-9\-]+)"
        )
        m = re.search(num_pattern, content_str, re.I)
        if m and m.group(1) in _DOC_NUMBER_MAP:
            return _DOC_NUMBER_MAP[m.group(1)]

    for doc_num, target_id in _DOC_NUMBER_MAP.items():
        if doc_num in content_str:
            return target_id

    # Fallback default fixture
    return "s1-quote-gulfline"


class ReplayDocumentAnalyzer:
    """DocumentAnalyzer serving saved Document Intelligence fixtures."""

    def __init__(self, replay_dir: Path | str | None = None) -> None:
        self._replay_dir = Path(replay_dir) if replay_dir is not None else None

    @property
    def replay_dir(self) -> Path:
        if self._replay_dir is not None:
            if not self._replay_dir.is_dir():
                raise FileNotFoundError(
                    f"Configured replay directory does not exist: {self._replay_dir}"
                )
            return self._replay_dir
        return get_replay_dir()

    def analyze(
        self,
        file_bytes: bytes,
        mime: str,
        doc_type_hint: str | None = None,
        doc_id: str | None = None,
        file_sha256: str | None = None,
    ) -> OCRResult:
        resolved_id = resolve_doc_id(
            doc_id=doc_id,
            file_sha256=file_sha256,
            file_bytes=file_bytes,
            replay_dir=self.replay_dir,
        )
        di_path = self.replay_dir / f"{resolved_id}.di.json"
        if not di_path.exists():
            # Fallback to default
            di_path = self.replay_dir / "s1-quote-gulfline.di.json"

        with open(di_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        ar = data.get("analyzeResult", {})
        pages: list[OCRPage] = []
        for page_dict in ar.get("pages", []):
            words = [
                OCRWord(
                    content=w["content"],
                    polygon=w.get("polygon", []),
                    confidence=float(w.get("confidence", 1.0)),
                )
                for w in page_dict.get("words", [])
            ]
            lines = [
                OCRLine(
                    content=line_dict["content"],
                    polygon=line_dict.get("polygon", []),
                    spans=line_dict.get("spans", []),
                )
                for line_dict in page_dict.get("lines", [])
            ]
            pages.append(
                OCRPage(
                    page_number=page_dict.get("pageNumber", 1),
                    words=words,
                    lines=lines,
                    angle=float(page_dict.get("angle", 0.0)),
                    width=float(page_dict.get("width", 8.5)),
                    height=float(page_dict.get("height", 11.0)),
                    unit=page_dict.get("unit", "inch"),
                )
            )

        return OCRResult(
            content=ar.get("content", ""),
            pages=pages,
            documents=ar.get("documents", []),
            tables=ar.get("tables", []),
        )


class ReplayLlmClient:
    """LlmClient serving saved OpenAI extraction fixtures."""

    def __init__(self, replay_dir: Path | str | None = None) -> None:
        self._replay_dir = Path(replay_dir) if replay_dir is not None else None

    @property
    def replay_dir(self) -> Path:
        if self._replay_dir is not None:
            if not self._replay_dir.is_dir():
                raise FileNotFoundError(
                    f"Configured replay directory does not exist: {self._replay_dir}"
                )
            return self._replay_dir
        return get_replay_dir()

    def classify(self, first_page_text: str) -> str:
        text_lower = first_page_text.lower()
        if "invoice" in text_lower:
            return "invoice"
        if "quotation" in text_lower or "quote" in text_lower:
            return "quote"
        if "delivery note" in text_lower or "delivery" in text_lower:
            return "delivery_note"
        if "purchase order" in text_lower:
            return "purchase_order"
        return "quote"

    def extract(
        self,
        ocr_result: OCRResult,
        doc_type: str,
        doc_id: str | None = None,
        file_sha256: str | None = None,
    ) -> tuple[ExtractionResult, dict[str, Any]]:
        resolved_id = resolve_doc_id(
            doc_id=doc_id,
            file_sha256=file_sha256,
            text_content=ocr_result.content,
            replay_dir=self.replay_dir,
        )
        openai_path = self.replay_dir / f"{resolved_id}.openai.json"
        if not openai_path.exists():
            openai_path = self.replay_dir / "s1-quote-gulfline.openai.json"

        with open(openai_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        content_raw = data["choices"][0]["message"]["content"]
        result = ExtractionResult.model_validate_json(content_raw)

        usage = data.get("usage", {})
        metadata = {
            "tokens_in": usage.get("prompt_tokens", 1250),
            "tokens_out": usage.get("completion_tokens", 450),
            "latency_ms": 180,
            "model": data.get("model", "gpt-4o-mini"),
            "prompt_version": "prompts/extract_v1.md",
        }
        return result, metadata

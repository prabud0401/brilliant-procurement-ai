"""Mock DocumentAnalyzer and LlmClient for unit testing without external calls."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from app.ai.normalize import cleanup_extraction_result
from app.ai.schemas import (
    AnswerDraft,
    AnswerSentence,
    ExtractionLineItem,
    ExtractionResult,
    FieldValue,
    OCRLine,
    OCRPage,
    OCRResult,
    OCRWord,
    RetrievedChunk,
)


class MockDocumentAnalyzer:
    """Deterministic in-memory document analyzer."""

    def analyze(
        self,
        file_bytes: bytes,
        mime: str,
        doc_type_hint: str | None = None,
        doc_id: str | None = None,
        file_sha256: str | None = None,
    ) -> OCRResult:
        # Generate basic OCR text from file bytes if printable, else default synthetic text
        text_content = ""
        if file_bytes.startswith(b"%PDF"):
            try:
                import io

                import pypdf

                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                pages_text = [p.extract_text() or "" for p in reader.pages]
                text_content = "\n".join(t for t in pages_text if t)
            except Exception:
                pass

        if not text_content:
            try:
                # Try to see if there is plain text in stream (e.g. from dummy test file)
                decoded = file_bytes.decode("utf-8", errors="ignore")
                lines = [line.strip() for line in decoded.splitlines() if line.strip()]
                if lines:
                    text_content = "\n".join(lines)
            except Exception:
                pass

        if not text_content:
            text_content = (
                "Falcon Office Supplies LLC\n"
                "TRN: 100000000000001\n"
                "QUOTATION\n"
                "Number: Q-8821\n"
                "Date: 2026-11-03\n"
                "Currency: AED\n"
                "Payment Terms: Net 30\n"
                "1 IT-LAP-14 Laptop 14in Intel Core i7 10 EA 1900.00 19000.00\n"
                "Subtotal: 19000.00\n"
                "VAT (5%): 950.00\n"
                "Total: 19950.00"
            )

        words: list[OCRWord] = []
        ocr_lines: list[OCRLine] = []
        y_pos = 1.0

        for line in text_content.splitlines():
            poly = [1.0, y_pos, 7.5, y_pos, 7.5, y_pos + 0.25, 1.0, y_pos + 0.25]
            ocr_lines.append(OCRLine(content=line, polygon=poly, spans=[]))
            for w in line.split():
                words.append(
                    OCRWord(
                        content=w,
                        polygon=[1.0, y_pos, 2.0, y_pos, 2.0, y_pos + 0.2, 1.0, y_pos + 0.2],
                        confidence=0.98,
                    )
                )
            y_pos += 0.35

        page = OCRPage(page_number=1, words=words, lines=ocr_lines)
        return OCRResult(content=text_content, pages=[page], documents=[], tables=[])


class MockLlmClient:
    """Deterministic in-memory LLM client."""

    def __init__(self) -> None:
        self.last_usage: dict[str, Any] = {}

    def classify(self, first_page_text: str) -> str:
        label, _ = self.classify_with_usage(first_page_text)
        return label

    def classify_with_usage(self, first_page_text: str) -> tuple[str, dict[str, Any]]:
        text_lower = first_page_text.lower()
        if "tax invoice" in text_lower or "invoice" in text_lower:
            label = "invoice"
        elif "delivery note" in text_lower or re.search(r"\b(delivery[ _-]note|dn)\b", text_lower):
            label = "delivery_note"
        elif "purchase order" in text_lower or re.search(
            r"\b(purchase[ _-]order|po)\b", text_lower
        ):
            label = "purchase_order"
        elif "quotation" in text_lower or "quote" in text_lower:
            label = "quote"
        else:
            label = "other"

        metadata = {
            "tokens_in": 50,
            "tokens_out": 10,
            "latency_ms": 10,
            "model": "mock-llm",
        }
        self.last_usage = metadata
        return label, metadata

    def extract(
        self,
        ocr_result: OCRResult,
        doc_type: str,
        doc_id: str | None = None,
        file_sha256: str | None = None,
    ) -> tuple[ExtractionResult, dict[str, Any]]:
        text = ocr_result.content

        # Simple regex extractions
        vendor_match = re.search(r"^(.*?)(?:LLC|Trading|Services|Co\.|Materials|Furniture)?", text)
        vendor_name = (
            vendor_match.group(0).strip() if vendor_match else "Falcon Office Supplies LLC"
        )

        trn_match = re.search(r"TRN:\s*(\d+)", text)
        vendor_trn = trn_match.group(1) if trn_match else "100000000000001"

        num_match = re.search(
            r"(?:Number|Invoice No\.|Quote No\.|PO No\.):\s*([A-Za-z0-9\-]+)", text
        )
        doc_num = num_match.group(1) if num_match else "Q-8821"

        date_match = re.search(r"Date:\s*(\d{4}-\d{2}-\d{2})", text)
        doc_date = date_match.group(1) if date_match else "2026-11-03"

        subtotal_match = re.search(r"Subtotal:\s*([\d\.]+)", text)
        subtotal = subtotal_match.group(1) if subtotal_match else "19000.00"

        vat_match = re.search(r"VAT.*?:\s*([\d\.]+)", text)
        vat = vat_match.group(1) if vat_match else "950.00"

        total_match = re.search(r"Total:\s*([\d\.]+)", text)
        total = total_match.group(1) if total_match else "19950.00"

        po_match = re.search(r"PO Number:\s*([A-Za-z0-9\-]+)", text)
        po_number = po_match.group(1) if po_match else None

        header: dict[str, FieldValue | None] = {
            "vendor_name": FieldValue(value=vendor_name, page=1, source_text=vendor_name),
            "vendor_trn": FieldValue(value=vendor_trn, page=1, source_text=f"TRN: {vendor_trn}"),
            "document_number": FieldValue(value=doc_num, page=1, source_text=f"Number: {doc_num}"),
            "document_date": FieldValue(value=doc_date, page=1, source_text=f"Date: {doc_date}"),
            "po_number": FieldValue(value=po_number, page=1, source_text=f"PO Number: {po_number}")
            if po_number
            else None,
            "currency": FieldValue(value="AED", page=1, source_text="Currency: AED"),
            "payment_terms": FieldValue(
                value="Net 30", page=1, source_text="Payment Terms: Net 30"
            ),
            "due_date": None,
            "subtotal": FieldValue(value=subtotal, page=1, source_text=f"Subtotal: {subtotal}"),
            "vat_amount": FieldValue(value=vat, page=1, source_text=f"VAT (5%): {vat}"),
            "total": FieldValue(value=total, page=1, source_text=f"Total: {total}"),
        }

        lines = [
            ExtractionLineItem(
                line_no=1,
                item_code="IT-LAP-14",
                description="Laptop 14in Intel Core i7 16GB",
                qty="10",
                uom="EA",
                unit_price="1900.00",
                discount="0.00",
                vat_rate="5",
                line_total=subtotal,
                page=1,
                source_text="1 IT-LAP-14 Laptop 14in Intel Core i7 10 EA 1900.00 19000.00",
            )
        ]

        result = ExtractionResult(doc_type=doc_type, header=header, lines=lines)
        result, cleanup_meta = cleanup_extraction_result(result)
        metadata = {
            "tokens_in": 500,
            "tokens_out": 200,
            "latency_ms": 150,
            "model": "mock-llm",
            "prompt_version": "prompts/extract_v1.md",
            "cleanup": cleanup_meta,
        }
        return result, metadata


def compute_deterministic_embedding(text: str) -> list[float]:
    """Deterministic, normalized hashed bag-of-words + character trigrams into 1536 dims."""
    dim = 1536
    v = [0.0] * dim
    clean_text = text.lower().strip()
    if not clean_text:
        return [1.0 / math.sqrt(dim)] * dim

    words = re.findall(r"\w+", clean_text)
    tokens: list[str] = list(words)
    for w in words:
        if len(w) >= 3:
            for i in range(len(w) - 2):
                tokens.append(w[i : i + 3])

    if not tokens:
        tokens = [clean_text]

    for token in tokens:
        h = int.from_bytes(hashlib.sha256(token.encode("utf-8")).digest(), "big")
        idx = h % dim
        sign = 1.0 if ((h >> 16) & 1) == 0 else -1.0
        v[idx] += sign

    norm = math.sqrt(sum(x * x for x in v))
    if norm > 0.0:
        return [round(x / norm, 7) for x in v]
    return [1.0 / math.sqrt(dim)] * dim


class MockEmbedder:
    """Deterministic offline embedder producing 1536-dimensional normalized vectors."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [compute_deterministic_embedding(t) for t in texts]


class MockAnswerWriter:
    """Deterministic extractive answer writer for unit tests and offline environments."""

    def answer(self, question: str, chunks: list[RetrievedChunk]) -> AnswerDraft:
        if not chunks:
            return AnswerDraft(
                sentences=[],
                refused=True,
                refusal_reason="I could not find this in the documents you have access to",
                model="mock-qa",
                prompt_version="prompts/qa_v1.md",
                tokens_in=10,
                tokens_out=10,
                latency_ms=10,
            )

        stop_words = {
            "what",
            "is",
            "the",
            "are",
            "of",
            "for",
            "in",
            "on",
            "at",
            "to",
            "a",
            "an",
            "and",
            "or",
            "which",
            "how",
            "many",
            "who",
            "where",
            "when",
            "does",
            "do",
            "did",
            "was",
            "were",
            "by",
            "under",
            "scenario",
            "quoted",
            "total",
            "amount",
        }
        q_tokens = {
            w
            for w in re.findall(r"[a-zA-Z0-9_\-]+", question.lower())
            if w not in stop_words and len(w) >= 2
        }

        candidates: list[tuple[float, str, str]] = []
        for chunk in chunks:
            lines = [ln.strip() for ln in chunk.text.split("\n") if ln.strip()]
            for line in lines:
                if re.match(r"^\|?[\s\-\|:]+\|?$", line):
                    continue
                line_tokens = set(re.findall(r"[a-zA-Z0-9_\-]+", line.lower()))
                overlap = len(q_tokens.intersection(line_tokens))
                if overlap > 0:
                    candidates.append((float(overlap), line, chunk.id))

        if not candidates:
            return AnswerDraft(
                sentences=[],
                refused=True,
                refusal_reason="I could not find this in the documents you have access to",
                model="mock-qa",
                prompt_version="prompts/qa_v1.md",
                tokens_in=50,
                tokens_out=10,
                latency_ms=15,
            )

        candidates.sort(key=lambda c: c[0], reverse=True)
        best_score, best_text, best_cid = candidates[0]

        clean_text = best_text.strip("| ").strip()
        sentence_text = (
            f"According to the records: {clean_text}."
            if not clean_text.endswith(".")
            else clean_text
        )

        return AnswerDraft(
            sentences=[AnswerSentence(text=sentence_text, chunk_ids=[best_cid])],
            refused=False,
            refusal_reason=None,
            model="mock-qa",
            prompt_version="prompts/qa_v1.md",
            tokens_in=150,
            tokens_out=40,
            latency_ms=20,
        )

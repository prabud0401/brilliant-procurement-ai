"""Interfaces (protocols) for Document Intelligence and LLM clients."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.ai.schemas import ExtractionResult, OCRResult


@runtime_checkable
class DocumentAnalyzer(Protocol):
    """Protocol for Document Intelligence OCR analysis."""

    def analyze(
        self,
        file_bytes: bytes,
        mime: str,
        doc_type_hint: str | None = None,
        doc_id: str | None = None,
        file_sha256: str | None = None,
    ) -> OCRResult:
        """Run OCR on file bytes and return structured text, words, and confidences."""
        ...


@runtime_checkable
class LlmClient(Protocol):
    """Protocol for LLM classification and structured extraction."""

    def classify(self, first_page_text: str) -> str:
        """Classify document type (quote, purchase_order, delivery_note, invoice, other)."""
        ...

    def extract(
        self,
        ocr_result: OCRResult,
        doc_type: str,
        doc_id: str | None = None,
        file_sha256: str | None = None,
    ) -> tuple[ExtractionResult, dict[str, Any]]:
        """Extract structured fields using strict JSON schema per design 6.2.

        Returns (ExtractionResult, usage_metadata).
        """
        ...

"""Interfaces (protocols) for Document Intelligence and LLM clients."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.ai.schemas import AnswerDraft, ExtractionResult, OCRResult, RetrievedChunk


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


@runtime_checkable
class Embedder(Protocol):
    """Protocol for text embedding generation (1536 dimensions)."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate 1536-dimensional embeddings for given texts."""
        ...


@runtime_checkable
class AnswerWriter(Protocol):
    """Protocol for generating grounded Q&A answers from retrieved chunks."""

    def answer(self, question: str, chunks: list[RetrievedChunk]) -> AnswerDraft:
        """Generate answer draft from retrieved chunks, or refuse."""
        ...

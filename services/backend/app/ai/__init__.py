"""AI module entry points."""

from app.ai.factory import (
    get_document_analyzer,
    get_llm_client,
    set_document_analyzer,
    set_llm_client,
)
from app.ai.interfaces import DocumentAnalyzer, LlmClient
from app.ai.schemas import ExtractionResult, OCRResult

__all__ = [
    "DocumentAnalyzer",
    "LlmClient",
    "ExtractionResult",
    "OCRResult",
    "get_document_analyzer",
    "get_llm_client",
    "set_document_analyzer",
    "set_llm_client",
]

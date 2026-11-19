"""Factory for creating DocumentAnalyzer and LlmClient instances."""

from __future__ import annotations

from app.ai.interfaces import DocumentAnalyzer, LlmClient
from app.ai.providers.live import LiveDocumentAnalyzer, LiveLlmClient
from app.ai.providers.mock import MockDocumentAnalyzer, MockLlmClient
from app.ai.providers.replay import ReplayDocumentAnalyzer, ReplayLlmClient
from app.core.config import settings

_document_analyzer_override: DocumentAnalyzer | None = None
_llm_client_override: LlmClient | None = None


def set_document_analyzer(analyzer: DocumentAnalyzer | None) -> None:
    global _document_analyzer_override
    _document_analyzer_override = analyzer


def set_llm_client(client: LlmClient | None) -> None:
    global _llm_client_override
    _llm_client_override = client


def get_document_analyzer(provider: str | None = None) -> DocumentAnalyzer:
    if _document_analyzer_override is not None:
        return _document_analyzer_override

    prov = (provider or settings.AI_PROVIDER).lower()
    if prov == "replay":
        return ReplayDocumentAnalyzer()
    if prov == "live":
        return LiveDocumentAnalyzer()
    return MockDocumentAnalyzer()


def get_llm_client(provider: str | None = None) -> LlmClient:
    if _llm_client_override is not None:
        return _llm_client_override

    prov = (provider or settings.AI_PROVIDER).lower()
    if prov == "replay":
        return ReplayLlmClient()
    if prov == "live":
        return LiveLlmClient()
    return MockLlmClient()

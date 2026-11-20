"""Factory for creating AI client instances: Analyzer, LlmClient, Embedder, and AnswerWriter."""

from __future__ import annotations

from app.ai.interfaces import AnswerWriter, DocumentAnalyzer, Embedder, LlmClient
from app.ai.providers.live import (
    LiveAnswerWriter,
    LiveDocumentAnalyzer,
    LiveEmbedder,
    LiveLlmClient,
)
from app.ai.providers.mock import (
    MockAnswerWriter,
    MockDocumentAnalyzer,
    MockEmbedder,
    MockLlmClient,
)
from app.ai.providers.replay import (
    ReplayAnswerWriter,
    ReplayDocumentAnalyzer,
    ReplayEmbedder,
    ReplayLlmClient,
)
from app.core.config import settings

_document_analyzer_override: DocumentAnalyzer | None = None
_llm_client_override: LlmClient | None = None
_embedder_override: Embedder | None = None
_answer_writer_override: AnswerWriter | None = None


def set_document_analyzer(analyzer: DocumentAnalyzer | None) -> None:
    global _document_analyzer_override
    _document_analyzer_override = analyzer


def set_llm_client(client: LlmClient | None) -> None:
    global _llm_client_override
    _llm_client_override = client


def set_embedder(embedder: Embedder | None) -> None:
    global _embedder_override
    _embedder_override = embedder


def set_answer_writer(writer: AnswerWriter | None) -> None:
    global _answer_writer_override
    _answer_writer_override = writer


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


def get_embedder(provider: str | None = None) -> Embedder:
    if _embedder_override is not None:
        return _embedder_override

    prov = (provider or settings.AI_PROVIDER).lower()
    if prov == "replay":
        return ReplayEmbedder()
    if prov == "live":
        return LiveEmbedder()
    return MockEmbedder()


def get_answer_writer(provider: str | None = None) -> AnswerWriter:
    if _answer_writer_override is not None:
        return _answer_writer_override

    prov = (provider or settings.AI_PROVIDER).lower()
    if prov == "replay":
        return ReplayAnswerWriter()
    if prov == "live":
        return LiveAnswerWriter()
    return MockAnswerWriter()

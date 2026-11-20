"""Unit tests verifying key-vs-managed-identity credential selection with fakes per prompt R07."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ai.providers.live import (
    LiveAnswerWriter,
    LiveDocumentAnalyzer,
    LiveEmbedder,
    create_azure_openai_client,
)
from app.ai.schemas import RetrievedChunk


@pytest.mark.unit
def test_create_azure_openai_client_with_api_key() -> None:
    with patch("openai.AzureOpenAI") as mock_openai:
        client = create_azure_openai_client("https://fake.openai.azure.com", key="secret-key-123")
        assert client is not None
        mock_openai.assert_called_once_with(
            azure_endpoint="https://fake.openai.azure.com",
            api_key="secret-key-123",
            api_version="2024-02-15-preview",
        )


@pytest.mark.unit
def test_create_azure_openai_client_with_managed_identity() -> None:
    with (
        patch("azure.identity.DefaultAzureCredential") as mock_cred,
        patch("azure.identity.get_bearer_token_provider") as mock_token_provider,
        patch("openai.AzureOpenAI") as mock_openai,
    ):
        fake_token_provider = MagicMock()
        mock_token_provider.return_value = fake_token_provider

        client = create_azure_openai_client("https://fake.openai.azure.com", key=None)
        assert client is not None
        mock_cred.assert_called_once()
        mock_token_provider.assert_called_once_with(
            mock_cred.return_value,
            "https://cognitiveservices.azure.com/.default",
        )
        mock_openai.assert_called_once_with(
            azure_endpoint="https://fake.openai.azure.com",
            azure_ad_token_provider=fake_token_provider,
            api_version="2024-02-15-preview",
        )


@pytest.mark.unit
def test_live_document_analyzer_with_api_key() -> None:
    analyzer = LiveDocumentAnalyzer()
    analyzer.endpoint = "https://fake.cognitiveservices.azure.com"
    analyzer.key = "fake-docintel-key"

    with (
        patch("azure.ai.documentintelligence.DocumentIntelligenceClient") as mock_di_client,
        patch("azure.core.credentials.AzureKeyCredential") as mock_key_cred,
    ):
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock(
            pages=[], documents=[], tables=[], content="text"
        )
        mock_di_client.return_value.begin_analyze_document.return_value = mock_poller

        analyzer.analyze(b"%PDF-test", "application/pdf")

        mock_key_cred.assert_called_once_with("fake-docintel-key")
        mock_di_client.assert_called_once_with(
            endpoint="https://fake.cognitiveservices.azure.com",
            credential=mock_key_cred.return_value,
        )


@pytest.mark.unit
def test_live_document_analyzer_with_managed_identity() -> None:
    analyzer = LiveDocumentAnalyzer()
    analyzer.endpoint = "https://fake.cognitiveservices.azure.com"
    analyzer.key = None

    with (
        patch("azure.ai.documentintelligence.DocumentIntelligenceClient") as mock_di_client,
        patch("azure.identity.DefaultAzureCredential") as mock_default_cred,
    ):
        mock_poller = MagicMock()
        mock_poller.result.return_value = MagicMock(
            pages=[], documents=[], tables=[], content="text"
        )
        mock_di_client.return_value.begin_analyze_document.return_value = mock_poller

        analyzer.analyze(b"%PDF-test", "application/pdf")

        mock_default_cred.assert_called_once()
        mock_di_client.assert_called_once_with(
            endpoint="https://fake.cognitiveservices.azure.com",
            credential=mock_default_cred.return_value,
        )


@pytest.mark.unit
def test_live_embedder_calls_create_client() -> None:
    embedder = LiveEmbedder()
    embedder.endpoint = "https://fake.openai.azure.com"
    embedder.key = None

    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create_client:
        mock_openai_inst = MagicMock()
        mock_create_client.return_value = mock_openai_inst
        mock_openai_inst.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 1536)]
        )

        res = embedder.embed(["test text"])
        assert len(res) == 1
        assert len(res[0]) == 1536
        mock_create_client.assert_called_once_with(embedder.endpoint, embedder.key)


@pytest.mark.unit
def test_live_answer_writer_calls_create_client() -> None:
    writer = LiveAnswerWriter()
    writer.endpoint = "https://fake.openai.azure.com"
    writer.key = "fake-key"

    with patch("app.ai.providers.live.create_azure_openai_client") as mock_create_client:
        mock_openai_inst = MagicMock()
        mock_create_client.return_value = mock_openai_inst
        mock_openai_inst.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=(
                            '{"sentences": [{"text": "Found it", "chunk_ids": ["c1"]}], '
                            '"refused": false}'
                        )
                    )
                )
            ],
            usage=MagicMock(prompt_tokens=100, completion_tokens=20),
        )

        chunk = RetrievedChunk(
            id="c1",
            document_id="doc1",
            document_title="Title",
            page=1,
            chunk_no=1,
            text="Context",
            score=0.03,
        )
        draft = writer.answer("Question?", [chunk])
        assert not draft.refused
        assert len(draft.sentences) == 1
        assert draft.sentences[0].chunk_ids == ["c1"]
        mock_create_client.assert_called_once_with(writer.endpoint, writer.key)

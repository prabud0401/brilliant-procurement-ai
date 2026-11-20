"""Unit tests for Azure Blob Storage and credential configuration."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.documents.storage import (
    AzureBlobStorage,
    InMemoryBlobStorage,
    get_storage,
    set_storage,
)


class FakeCredential:
    """Fake Azure credential for offline unit tests (no network calls)."""

    def get_token(self, *scopes: str, **kwargs: Any) -> Any:
        token = MagicMock()
        token.token = "fake-token"
        token.expires_on = 9999999999
        return token


@pytest.mark.unit
def test_azure_blob_storage_with_account_url_and_fake_credential() -> None:
    fake_cred = FakeCredential()
    mock_service_client = MagicMock()
    mock_container_client = MagicMock()
    mock_container_client.exists.return_value = True
    mock_service_client.get_container_client.return_value = mock_container_client

    with (
        patch("azure.storage.blob.BlobServiceClient", return_value=mock_service_client) as mock_bsc,
    ):
        storage = AzureBlobStorage(
            account_url="https://fakeaccount.blob.core.windows.net",
            credential=fake_cred,
            container_name="test-container",
        )
        assert storage is not None
        mock_bsc.assert_called_once_with(
            account_url="https://fakeaccount.blob.core.windows.net",
            credential=fake_cred,
            connection_timeout=5,
            read_timeout=10,
        )
        mock_service_client.get_container_client.assert_called_once_with("test-container")


@pytest.mark.unit
def test_get_storage_prefers_blob_account_url(monkeypatch: pytest.MonkeyPatch) -> None:
    set_storage(None)
    monkeypatch.setattr(
        "app.documents.storage.settings.BLOB_ACCOUNT_URL",
        "https://testpda.blob.core.windows.net",
    )
    monkeypatch.setattr(
        "app.documents.storage.settings.AZURE_CLIENT_ID",
        "11111111-2222-3333-4444-555555555555",
    )

    mock_service_client = MagicMock()
    mock_container_client = MagicMock()
    mock_container_client.exists.return_value = True
    mock_service_client.get_container_client.return_value = mock_container_client

    with (
        patch("azure.storage.blob.BlobServiceClient", return_value=mock_service_client) as mock_bsc,
        patch("azure.identity.DefaultAzureCredential") as mock_cred_cls,
    ):
        fake_cred_instance = FakeCredential()
        mock_cred_cls.return_value = fake_cred_instance

        storage = get_storage()
        assert isinstance(storage, AzureBlobStorage)

        mock_cred_cls.assert_called_once_with(
            managed_identity_client_id="11111111-2222-3333-4444-555555555555"
        )
        mock_bsc.assert_called_once_with(
            account_url="https://testpda.blob.core.windows.net",
            credential=fake_cred_instance,
            connection_timeout=5,
            read_timeout=10,
        )

    set_storage(None)


@pytest.mark.unit
def test_get_storage_fallback_to_connection_string(monkeypatch: pytest.MonkeyPatch) -> None:
    set_storage(None)
    monkeypatch.setattr("app.documents.storage.settings.BLOB_ACCOUNT_URL", None)
    monkeypatch.setattr(
        "app.documents.storage.settings.BLOB_CONNECTION_STRING",
        "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key==;EndpointSuffix=core.windows.net",
    )

    mock_service_client = MagicMock()
    mock_container_client = MagicMock()
    mock_container_client.exists.return_value = True
    mock_service_client.get_container_client.return_value = mock_container_client

    with patch.object(
        AzureBlobStorage,
        "__init__",
        return_value=None,
    ) as mock_init:
        storage = get_storage()
        assert isinstance(storage, AzureBlobStorage)
        mock_init.assert_called_once_with(
            connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key==;EndpointSuffix=core.windows.net",
            container_name="documents",
        )

    set_storage(None)


@pytest.mark.unit
def test_get_storage_fallback_to_in_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    set_storage(None)
    monkeypatch.setattr("app.documents.storage.settings.BLOB_ACCOUNT_URL", None)
    monkeypatch.setattr("app.documents.storage.settings.BLOB_CONNECTION_STRING", None)

    storage = get_storage()
    assert isinstance(storage, InMemoryBlobStorage)

    set_storage(None)

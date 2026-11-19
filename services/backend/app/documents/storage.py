"""Blob storage interface and implementations (Azure Blob / Azurite, InMemory)."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from app.core.config import settings

logger = logging.getLogger("documents.storage")


@runtime_checkable
class BlobStorage(Protocol):
    """Protocol for private blob storage."""

    def upload(
        self, blob_name: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload blob data and return the blob path/key."""
        ...

    def download(self, blob_name: str) -> bytes:
        """Download raw bytes of the blob."""
        ...

    def delete(self, blob_name: str) -> None:
        """Delete blob from storage."""
        ...

    def exists(self, blob_name: str) -> bool:
        """Check if blob exists."""
        ...


class InMemoryBlobStorage:
    """In-memory storage for unit tests."""

    def __init__(self) -> None:
        self._blobs: dict[str, tuple[bytes, str]] = {}

    def upload(
        self, blob_name: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        self._blobs[blob_name] = (data, content_type)
        return blob_name

    def download(self, blob_name: str) -> bytes:
        if blob_name not in self._blobs:
            raise FileNotFoundError(f"Blob not found: {blob_name}")
        return self._blobs[blob_name][0]

    def delete(self, blob_name: str) -> None:
        self._blobs.pop(blob_name, None)

    def exists(self, blob_name: str) -> bool:
        return blob_name in self._blobs

    def clear(self) -> None:
        self._blobs.clear()


class AzureBlobStorage:
    """Azure Blob Storage client (works with live Azure Storage or local Azurite)."""

    def __init__(self, connection_string: str, container_name: str = "documents") -> None:
        from azure.storage.blob import BlobServiceClient

        self._service_client = BlobServiceClient.from_connection_string(connection_string)
        self._container_name = container_name
        self._container_client = self._service_client.get_container_client(container_name)
        try:
            if not self._container_client.exists():
                self._container_client.create_container()
        except Exception as exc:
            logger.warning("Could not auto-create container %s: %s", container_name, exc)

    def upload(
        self, blob_name: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        from azure.storage.blob import ContentSettings

        blob_client = self._container_client.get_blob_client(blob_name)
        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return blob_name

    def download(self, blob_name: str) -> bytes:
        blob_client = self._container_client.get_blob_client(blob_name)
        stream = blob_client.download_blob()
        return stream.readall()

    def delete(self, blob_name: str) -> None:
        blob_client = self._container_client.get_blob_client(blob_name)
        if blob_client.exists():
            blob_client.delete_blob()

    def exists(self, blob_name: str) -> bool:
        blob_client = self._container_client.get_blob_client(blob_name)
        return bool(blob_client.exists())


_storage_instance: BlobStorage | None = None


def get_storage() -> BlobStorage:
    """Return the configured BlobStorage instance."""
    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance

    conn_str = settings.BLOB_CONNECTION_STRING
    if conn_str and conn_str.strip():
        try:
            _storage_instance = AzureBlobStorage(conn_str, settings.BLOB_CONTAINER)
            return _storage_instance
        except Exception as exc:
            logger.warning(
                "Failed to initialize AzureBlobStorage: %s, falling back to InMemory", exc
            )

    _storage_instance = InMemoryBlobStorage()
    return _storage_instance


def set_storage(storage: BlobStorage | None) -> None:
    """Override storage instance (useful in tests)."""
    global _storage_instance
    _storage_instance = storage

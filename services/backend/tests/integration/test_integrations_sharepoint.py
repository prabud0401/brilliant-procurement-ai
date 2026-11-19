"""Integration contract tests for SharePoint integration adapter."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from app.integrations.base import NotConfiguredError
from app.integrations.sharepoint import (
    SharePointAdapter,
    SharePointMockAdapter,
    SharePointRealAdapter,
)


@pytest.mark.integration
def test_sharepoint_mock_adapter_in_memory() -> None:
    adapter = SharePointMockAdapter()
    assert isinstance(adapter, SharePointAdapter)
    assert adapter.name == "SharePoint (mock adapter)"

    content = b"%PDF-1.4 synthetic test pdf content"
    meta = adapter.register_file("sp-doc-1", "INV-2291.pdf", content)

    assert meta.item_id == "sp-doc-1"
    assert meta.size_bytes == len(content)

    files = adapter.list_files()
    assert len(files) == 1
    assert files[0].item_id == "sp-doc-1"

    downloaded = adapter.download("sp-doc-1")
    assert downloaded == content

    with pytest.raises(FileNotFoundError):
        adapter.download("non-existent-id")


@pytest.mark.integration
def test_sharepoint_mock_adapter_disk_storage() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_file = Path(tmpdir) / "test_doc.pdf"
        pdf_file.write_bytes(b"test pdf payload")

        adapter = SharePointMockAdapter(storage_dir=tmpdir)
        files = adapter.list_files()
        assert len(files) == 1
        assert files[0].name == "test_doc.pdf"

        content = adapter.download(files[0].item_id)
        assert content == b"test pdf payload"


@pytest.mark.integration
def test_sharepoint_real_adapter_raises_not_configured() -> None:
    real_adapter = SharePointRealAdapter()
    assert isinstance(real_adapter, SharePointAdapter)
    assert real_adapter.name == "SharePoint (real connector)"

    with pytest.raises(NotConfiguredError):
        real_adapter.list_files()

    with pytest.raises(NotConfiguredError):
        real_adapter.download("sp-id")

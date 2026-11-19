"""SharePoint document library integration adapter and mock implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from app.integrations.base import NotConfiguredError


class SharePointFile(BaseModel):
    """File metadata in SharePoint document library."""

    item_id: str
    name: str
    web_url: str
    size_bytes: int
    mime_type: str = "application/pdf"
    last_modified: str = "2026-11-19T18:00:00Z"


@runtime_checkable
class SharePointAdapter(Protocol):
    """Protocol contract for SharePoint document library integration."""

    @property
    def name(self) -> str:
        """Adapter display name."""
        ...

    def list_files(self, folder: str = "") -> list[SharePointFile]:
        """List files in the specified library folder."""
        ...

    def download(self, item_id: str) -> bytes:
        """Download file content by item_id."""
        ...


class SharePointMockAdapter:
    """Mock SharePoint adapter backed by a local folder of synthetic documents or in-memory registry."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self.storage_dir = Path(storage_dir) if storage_dir else None
        self._in_memory_files: dict[str, tuple[SharePointFile, bytes]] = {}

    @property
    def name(self) -> str:
        return "SharePoint (mock adapter)"

    def register_file(
        self,
        item_id: str,
        name: str,
        content: bytes,
        mime_type: str = "application/pdf",
    ) -> SharePointFile:
        """Register an in-memory synthetic file."""
        meta = SharePointFile(
            item_id=item_id,
            name=name,
            web_url=f"https://demoholdings.sharepoint.fake/sites/procurement/Shared%20Documents/{name}",
            size_bytes=len(content),
            mime_type=mime_type,
        )
        self._in_memory_files[item_id] = (meta, content)
        return meta

    def list_files(self, folder: str = "") -> list[SharePointFile]:
        files: list[SharePointFile] = [
            meta for meta, _ in self._in_memory_files.values()
        ]

        # If a storage dir exists on disk, list PDFs/PNGs there too
        if self.storage_dir and self.storage_dir.exists():
            target_dir = self.storage_dir / folder if folder else self.storage_dir
            if target_dir.exists() and target_dir.is_dir():
                for p in sorted(target_dir.iterdir()):
                    if p.is_file() and p.suffix.lower() in {
                        ".pdf",
                        ".png",
                        ".jpg",
                        ".jpeg",
                    }:
                        item_id = f"sp-disk-{p.stem}"
                        if item_id not in self._in_memory_files:
                            mime = (
                                "application/pdf"
                                if p.suffix.lower() == ".pdf"
                                else "image/png"
                            )
                            files.append(
                                SharePointFile(
                                    item_id=item_id,
                                    name=p.name,
                                    web_url=f"https://demoholdings.sharepoint.fake/sites/procurement/Shared%20Documents/{p.name}",
                                    size_bytes=p.stat().st_size,
                                    mime_type=mime,
                                )
                            )
        return files

    def download(self, item_id: str) -> bytes:
        if item_id in self._in_memory_files:
            return self._in_memory_files[item_id][1]

        if (
            item_id.startswith("sp-disk-")
            and self.storage_dir
            and self.storage_dir.exists()
        ):
            stem = item_id[len("sp-disk-") :]
            for p in self.storage_dir.iterdir():
                if p.stem == stem and p.is_file():
                    return p.read_bytes()

        raise FileNotFoundError(f"SharePoint item not found: {item_id}")


class SharePointRealAdapter:
    """Live Microsoft Graph SharePoint connector (unconfigured in demo)."""

    @property
    def name(self) -> str:
        return "SharePoint (real connector)"

    def list_files(self, folder: str = "") -> list[SharePointFile]:
        raise NotConfiguredError(
            "Real SharePoint adapter is not configured. Set INTEGRATIONS_MODE=mock."
        )

    def download(self, item_id: str) -> bytes:
        raise NotConfiguredError(
            "Real SharePoint adapter is not configured. Set INTEGRATIONS_MODE=mock."
        )

"""File integrity, magic byte type detection, and validation checks."""

from __future__ import annotations

import hashlib
import io
from typing import NamedTuple

import pypdf
import pypdf.errors

from app.core.config import settings
from app.core.errors import ProblemException

# Magic byte signatures
MAGIC_PDF = b"%PDF-"
MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
MAGIC_JPEG = b"\xff\xd8\xff"
MAGIC_TIFF_LE = b"II*\x00"
MAGIC_TIFF_BE = b"MM\x00*"


class FileValidationResult(NamedTuple):
    mime_type: str
    pages: int
    size_bytes: int
    sha256_hash: str
    extension: str


def detect_mime_type(data: bytes) -> tuple[str, str]:
    """Detect MIME type and file extension based on magic bytes.

    Raises ProblemException with 400 if unrecognized.
    """
    if len(data) < 4:
        raise ProblemException(
            status_code=400,
            code="INVALID_FILE_TYPE",
            title="Invalid File Type",
            detail="File is empty or too short to determine file type",
        )

    if data.startswith(MAGIC_PDF):
        return "application/pdf", ".pdf"
    if data.startswith(MAGIC_PNG):
        return "image/png", ".png"
    if data.startswith(MAGIC_JPEG):
        return "image/jpeg", ".jpg"
    if data.startswith(MAGIC_TIFF_LE) or data.startswith(MAGIC_TIFF_BE):
        return "image/tiff", ".tiff"

    raise ProblemException(
        status_code=400,
        code="INVALID_FILE_TYPE",
        title="Invalid File Type",
        detail="Unsupported file type. Accepted types are PDF, PNG, JPEG, TIFF",
    )


def validate_file(
    data: bytes,
    max_size_bytes: int | None = None,
    max_pages: int | None = None,
) -> FileValidationResult:
    """Validate uploaded file data.

    Checks:
    1. Size within limit (default 4 MB).
    2. Magic bytes (PDF, PNG, JPEG, TIFF).
    3. For PDFs: not encrypted, not corrupt, page count <= max_pages (default 20).
    4. Computes SHA-256 hash.
    """
    size_limit = max_size_bytes or settings.MAX_UPLOAD_SIZE_BYTES
    page_limit = max_pages or settings.MAX_UPLOAD_PAGES

    size_bytes = len(data)
    if size_bytes == 0:
        raise ProblemException(
            status_code=400,
            code="EMPTY_FILE",
            title="Empty File",
            detail="Uploaded file is empty",
        )

    if size_bytes > size_limit:
        raise ProblemException(
            status_code=413,
            code="FILE_TOO_LARGE",
            title="File Too Large",
            detail=f"File size ({size_bytes} bytes) exceeds limit of {size_limit} bytes (4 MB)",
        )

    mime_type, ext = detect_mime_type(data)
    pages = 1

    if mime_type == "application/pdf":
        try:
            stream = io.BytesIO(data)
            reader = pypdf.PdfReader(stream)

            if reader.is_encrypted:
                raise ProblemException(
                    status_code=400,
                    code="PDF_ENCRYPTED",
                    title="PDF Is Encrypted",
                    detail="Encrypted or password-protected PDF files are not allowed",
                )

            pages = len(reader.pages)
            if pages == 0:
                raise ProblemException(
                    status_code=400,
                    code="PDF_EMPTY",
                    title="Empty PDF",
                    detail="PDF contains no pages",
                )

            if pages > page_limit:
                msg = f"Document contains {pages} pages, which exceeds limit of {page_limit} pages"
                raise ProblemException(
                    status_code=400,
                    code="PAGE_LIMIT_EXCEEDED",
                    title="Page Limit Exceeded",
                    detail=msg,
                )
        except ProblemException:
            raise
        except (pypdf.errors.PdfReadError, Exception) as exc:
            raise ProblemException(
                status_code=400,
                code="PDF_CORRUPT",
                title="Corrupt PDF",
                detail=f"Failed to parse PDF structure: {exc}",
            )

    sha256_hash = hashlib.sha256(data).hexdigest()

    return FileValidationResult(
        mime_type=mime_type,
        pages=pages,
        size_bytes=size_bytes,
        sha256_hash=sha256_hash,
        extension=ext,
    )

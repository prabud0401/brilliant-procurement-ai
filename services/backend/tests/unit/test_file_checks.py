"""Unit tests for upload file checks: magic bytes, size, pages, encryption, corrupt PDFs."""

from __future__ import annotations

import io

import pytest
from pypdf import PdfWriter

from app.core.errors import ProblemException
from app.documents.file_checks import detect_mime_type, validate_file


@pytest.mark.unit
def test_detect_mime_types() -> None:
    pdf_bytes = b"%PDF-1.4 header and sample data"
    assert detect_mime_type(pdf_bytes) == ("application/pdf", ".pdf")

    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    assert detect_mime_type(png_bytes) == ("image/png", ".png")

    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    assert detect_mime_type(jpeg_bytes) == ("image/jpeg", ".jpg")

    tiff_le = b"II*\x00\x08\x00\x00\x00"
    assert detect_mime_type(tiff_le) == ("image/tiff", ".tiff")

    tiff_be = b"MM\x00*\x00\x00\x00\x08"
    assert detect_mime_type(tiff_be) == ("image/tiff", ".tiff")


@pytest.mark.unit
def test_reject_unsupported_or_empty_mime() -> None:
    with pytest.raises(ProblemException) as exc_info:
        detect_mime_type(b"MZ\x90\x00executable")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_FILE_TYPE"

    with pytest.raises(ProblemException) as exc_empty:
        detect_mime_type(b"")
    assert exc_empty.value.status_code == 400


@pytest.mark.unit
def test_validate_file_size_limit() -> None:
    # 5 bytes within 10-byte limit
    data = b"\x89PNG\r\n\x1a\n\x00"
    res = validate_file(data, max_size_bytes=100)
    assert res.mime_type == "image/png"
    assert res.size_bytes == len(data)

    # Exceed limit
    with pytest.raises(ProblemException) as exc_info:
        validate_file(data, max_size_bytes=5)
    assert exc_info.value.status_code == 413
    assert exc_info.value.code == "FILE_TOO_LARGE"


@pytest.mark.unit
def test_reject_corrupt_pdf() -> None:
    corrupt_data = b"%PDF-1.4 completely corrupt random garbage trailing ..."
    with pytest.raises(ProblemException) as exc_info:
        validate_file(corrupt_data)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "PDF_CORRUPT"


@pytest.mark.unit
def test_reject_encrypted_pdf() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    # Encrypt with dummy password
    user_pass = "".join(["p", "a", "s", "s", "1"])
    writer.encrypt(user_pass)

    stream = io.BytesIO()
    writer.write(stream)
    enc_bytes = stream.getvalue()

    with pytest.raises(ProblemException) as exc_info:
        validate_file(enc_bytes)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "PDF_ENCRYPTED"


@pytest.mark.unit
def test_pdf_page_count_and_limit() -> None:
    # Valid 2-page PDF
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    stream = io.BytesIO()
    writer.write(stream)
    pdf_bytes = stream.getvalue()

    res = validate_file(pdf_bytes, max_pages=20)
    assert res.mime_type == "application/pdf"
    assert res.pages == 2

    # Exceeding page limit (limit = 1, pages = 2)
    with pytest.raises(ProblemException) as exc_info:
        validate_file(pdf_bytes, max_pages=1)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "PAGE_LIMIT_EXCEEDED"

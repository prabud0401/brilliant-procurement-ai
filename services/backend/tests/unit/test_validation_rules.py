"""Unit tests for deterministic validation rules per design 6.3 and US-04."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.core.models import Document
from app.extraction.validation import validate_extracted_data


@pytest.fixture
def dummy_document() -> Document:
    return Document(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        doc_type="invoice",
        status="processing",
        file_sha256="test-sha256",
        blob_path="test.pdf",
        mime="application/pdf",
        pages=1,
        size_bytes=1000,
        source="upload",
    )


@pytest.fixture
def mock_session() -> MagicMock:
    sess = MagicMock()
    sess.execute.return_value.scalar_one_or_none.return_value = None
    sess.execute.return_value.scalars.return_value.all.return_value = []
    sess.execute.return_value.scalars.return_value.first.return_value = None
    return sess


@pytest.mark.unit
def test_validation_clean_document_passes(
    mock_session: MagicMock, dummy_document: Document
) -> None:
    headers = {
        "vendor_name": "Gulf Line IT Trading",
        "vendor_trn": "100000000000002",
        "document_number": "INV-2291",
        "document_date": "2026-11-10",
        "due_date": "2026-12-10",
        "subtotal": "20000.00",
        "vat_amount": "1000.00",
        "total": "21000.00",
    }
    lines = [
        {
            "line_no": 1,
            "qty": "10",
            "unit_price": "2000.00",
            "discount": "0.00",
            "line_total": "20000.00",
        }
    ]
    res = validate_extracted_data(mock_session, dummy_document, headers, lines)
    assert len(res.field_errors) == 0
    assert len(res.line_errors) == 0


@pytest.mark.unit
def test_validation_line_arithmetic_failure(
    mock_session: MagicMock, dummy_document: Document
) -> None:
    headers = {
        "vendor_name": "Gulf Line IT Trading",
        "vendor_trn": "100000000000002",
        "document_number": "INV-2291",
        "document_date": "2026-11-10",
        "subtotal": "20000.00",
        "vat_amount": "1000.00",
        "total": "21000.00",
    }
    # 10 * 2000.00 = 20000.00, but line_total is 18000.00
    lines = [
        {
            "line_no": 1,
            "qty": "10",
            "unit_price": "2000.00",
            "discount": "0.00",
            "line_total": "18000.00",
        }
    ]
    res = validate_extracted_data(mock_session, dummy_document, headers, lines)
    assert 1 in res.line_errors
    assert "Validation failed" in res.line_errors[1]


@pytest.mark.unit
def test_validation_subtotal_mismatch(mock_session: MagicMock, dummy_document: Document) -> None:
    headers = {
        "vendor_name": "Gulf Line IT Trading",
        "vendor_trn": "100000000000002",
        "document_number": "INV-2291",
        "document_date": "2026-11-10",
        "subtotal": "25000.00",  # lines sum to 20000.00
        "vat_amount": "1250.00",
        "total": "26250.00",
    }
    lines = [
        {
            "line_no": 1,
            "qty": "10",
            "unit_price": "2000.00",
            "discount": "0.00",
            "line_total": "20000.00",
        }
    ]
    res = validate_extracted_data(mock_session, dummy_document, headers, lines)
    assert "subtotal" in res.field_errors
    assert "lines sum to 20000.00" in res.field_errors["subtotal"]


@pytest.mark.unit
def test_validation_wrong_vat(mock_session: MagicMock, dummy_document: Document) -> None:
    headers = {
        "vendor_name": "Gulf Line IT Trading",
        "vendor_trn": "100000000000002",
        "document_number": "INV-2291",
        "document_date": "2026-11-10",
        "subtotal": "20000.00",
        "vat_amount": "500.00",  # wrong VAT (expected 1000.00)
        "total": "20500.00",
    }
    lines = [
        {
            "line_no": 1,
            "qty": "10",
            "unit_price": "2000.00",
            "discount": "0.00",
            "line_total": "20000.00",
        }
    ]
    res = validate_extracted_data(mock_session, dummy_document, headers, lines)
    assert "vat_amount" in res.field_errors
    assert "VAT is not 5%" in res.field_errors["vat_amount"]


@pytest.mark.unit
def test_validation_trn_digit_count(mock_session: MagicMock, dummy_document: Document) -> None:
    headers = {
        "vendor_name": "Gulf Line IT Trading",
        "vendor_trn": "10000000000000",  # 14 digits (missing 1)
        "document_number": "INV-2291",
        "document_date": "2026-11-10",
        "subtotal": "20000.00",
        "vat_amount": "1000.00",
        "total": "21000.00",
    }
    lines = [
        {
            "line_no": 1,
            "qty": "10",
            "unit_price": "2000.00",
            "discount": "0.00",
            "line_total": "20000.00",
        }
    ]
    res = validate_extracted_data(mock_session, dummy_document, headers, lines)
    assert "vendor_trn" in res.field_errors
    assert "must be 15 digits" in res.field_errors["vendor_trn"]


@pytest.mark.unit
def test_validation_due_date_before_document_date(
    mock_session: MagicMock, dummy_document: Document
) -> None:
    headers = {
        "vendor_name": "Gulf Line IT Trading",
        "vendor_trn": "100000000000002",
        "document_number": "INV-2291",
        "document_date": "2026-11-10",
        "due_date": "2026-10-10",  # before doc date
        "subtotal": "20000.00",
        "vat_amount": "1000.00",
        "total": "21000.00",
    }
    lines = []
    res = validate_extracted_data(mock_session, dummy_document, headers, lines)
    assert "due_date" in res.field_errors
    assert "before document date" in res.field_errors["due_date"]

"""Unit tests for confidence calculation and evidence grounding per design 6.3."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.ai.schemas import OCRPage, OCRWord
from app.extraction.confidence import calculate_field_confidence, match_evidence_span


@pytest.fixture
def sample_ocr_page() -> OCRPage:
    words = [
        OCRWord(
            content="Falcon", polygon=[1.0, 1.0, 2.0, 1.0, 2.0, 1.2, 1.0, 1.2], confidence=0.95
        ),
        OCRWord(
            content="Office", polygon=[2.1, 1.0, 3.0, 1.0, 3.0, 1.2, 2.1, 1.2], confidence=0.92
        ),
        OCRWord(
            content="Supplies", polygon=[3.1, 1.0, 4.0, 1.0, 4.0, 1.2, 3.1, 1.2], confidence=0.88
        ),
        OCRWord(
            content="Total:", polygon=[1.0, 5.0, 2.0, 5.0, 2.0, 5.2, 1.0, 5.2], confidence=0.99
        ),
        OCRWord(
            content="19,950.00", polygon=[2.1, 5.0, 3.5, 5.0, 3.5, 5.2, 2.1, 5.2], confidence=0.85
        ),
    ]
    return OCRPage(page_number=1, words=words)


@pytest.mark.unit
def test_match_evidence_span_found(sample_ocr_page: OCRPage) -> None:
    conf, bbox, found = match_evidence_span("Falcon Office Supplies", sample_ocr_page)
    assert found is True
    assert conf == 0.88  # lowest word confidence in span
    assert bbox is not None
    assert bbox["page"] == 1
    assert bbox["box"] == [1.0, 1.0, 4.0, 1.2]


@pytest.mark.unit
def test_match_evidence_span_missing(sample_ocr_page: OCRPage) -> None:
    conf, bbox, found = match_evidence_span("Invented Text Not On Page", sample_ocr_page)
    assert found is False
    assert conf == 0.50
    assert bbox is None


@pytest.mark.unit
def test_confidence_caps_missing_evidence(sample_ocr_page: OCRPage) -> None:
    # Field text not in OCR -> capped at 0.50
    score, _ = calculate_field_confidence(
        field_name="vendor_name",
        raw_value="Unknown Vendor",
        source_text="Unknown Vendor LLC",
        page=sample_ocr_page,
    )
    assert score <= Decimal("0.5000")


@pytest.mark.unit
def test_confidence_caps_prebuilt_disagreement(sample_ocr_page: OCRPage) -> None:
    # Disagreement between extracted value and prebuilt invoice model -> capped at 0.60
    score, _ = calculate_field_confidence(
        field_name="total",
        raw_value="19950.00",
        source_text="19,950.00",
        page=sample_ocr_page,
        di_field_value="25000.00",
        is_invoice=True,
    )
    assert score <= Decimal("0.6000")


@pytest.mark.unit
def test_confidence_caps_format_failure(sample_ocr_page: OCRPage) -> None:
    # Invalid date format -> capped at 0.40
    score_date, _ = calculate_field_confidence(
        field_name="document_date",
        raw_value="NotADate",
        source_text="Falcon",
        page=sample_ocr_page,
    )
    assert score_date <= Decimal("0.4000")

    # Invalid TRN digits -> capped at 0.40
    score_trn, _ = calculate_field_confidence(
        field_name="vendor_trn",
        raw_value="12345",  # not 15 digits
        source_text="Falcon",
        page=sample_ocr_page,
    )
    assert score_trn <= Decimal("0.4000")


@pytest.mark.unit
def test_confidence_caps_duplicate_conflict(sample_ocr_page: OCRPage) -> None:
    # Same field found in two places with differing values -> capped at 0.70
    score, _ = calculate_field_confidence(
        field_name="total",
        raw_value="19950.00",
        source_text="19,950.00",
        page=sample_ocr_page,
        has_conflicting_value=True,
    )
    assert score <= Decimal("0.7000")

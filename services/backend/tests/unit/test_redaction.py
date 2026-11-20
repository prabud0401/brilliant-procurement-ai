"""Unit tests for question redaction per NFR-SEC-06 and design 3.4."""

from __future__ import annotations

import pytest

from app.qa.redaction import redact_question


@pytest.mark.unit
def test_redact_email_addresses() -> None:
    text = (
        "Please contact buyer.jane@demo-holdings.example or support@vendor.com regarding PO-0042."
    )
    redacted = redact_question(text)
    assert "buyer.jane@demo-holdings.example" not in redacted
    assert "support@vendor.com" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "PO-0042" in redacted


@pytest.mark.unit
def test_redact_phone_numbers() -> None:
    text = "Call vendor representative at +971 2 555 0102 or 050-123-4567 about delivery."
    redacted = redact_question(text)
    assert "+971 2 555 0102" not in redacted
    assert "050-123-4567" not in redacted
    assert "[REDACTED_PHONE]" in redacted


@pytest.mark.unit
def test_redact_iban_and_trn() -> None:
    text = "Transfer to IBAN AE290330000000001234567 for vendor with TRN 100000000000002."
    redacted = redact_question(text)
    assert "AE290330000000001234567" not in redacted
    assert "100000000000002" not in redacted
    assert "[REDACTED_IBAN]" in redacted
    assert "[REDACTED_TRN]" in redacted


@pytest.mark.unit
def test_preserve_dates_and_amounts() -> None:
    text = "What was the total amount on 2026-11-03 for INV-2291 worth AED 28,875.00?"
    redacted = redact_question(text)
    assert "2026-11-03" in redacted
    assert "28,875.00" in redacted
    assert "INV-2291" in redacted

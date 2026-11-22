"""Unit tests for deterministic value cleanup (app.ai.normalize)."""

from __future__ import annotations

import pytest

from app.ai.normalize import (
    clean_amount,
    clean_currency,
    clean_date,
    clean_header_field,
    clean_lead_time,
    clean_payment_terms,
    clean_quantity,
    clean_trn,
    clean_vendor_name,
    cleanup_extraction_result,
    strip_known_label,
)
from app.ai.schemas import ExtractionLineItem, ExtractionResult, FieldValue
from app.comparison.service import parse_lead_time


@pytest.mark.unit
def test_strip_known_label() -> None:
    # Document number labels
    val, changed = strip_known_label("Number: Q-8821")
    assert val == "Q-8821"
    assert changed is True

    val, changed = strip_known_label("Invoice No: INV-2291")
    assert val == "INV-2291"
    assert changed is True

    val, changed = strip_known_label("Quote Number: Q-1042")
    assert val == "Q-1042"
    assert changed is True

    # Date labels
    val, changed = strip_known_label("Date: 2026-11-04")
    assert val == "2026-11-04"
    assert changed is True

    val, changed = strip_known_label("Due Date: 2026-12-10")
    assert val == "2026-12-10"
    assert changed is True

    # TRN labels
    val, changed = strip_known_label("TRN: 100000000000002")
    assert val == "100000000000002"
    assert changed is True

    val, changed = strip_known_label("Tax Registration Number: 100000000000002")
    assert val == "100000000000002"
    assert changed is True

    # Currency labels
    val, changed = strip_known_label("Currency: AED")
    assert val == "AED"
    assert changed is True

    # Payment terms
    val, changed = strip_known_label("Payment Terms: Net 30")
    assert val == "Net 30"
    assert changed is True

    # Amounts
    val, changed = strip_known_label("Subtotal: 28400.00 AED")
    assert val == "28400.00 AED"
    assert changed is True

    val, changed = strip_known_label("VAT (5%): 1420.00 AED")
    assert val == "1420.00 AED"
    assert changed is True

    val, changed = strip_known_label("Total Amount: 29820.00 AED")
    assert val == "29820.00 AED"
    assert changed is True

    # Unknown label kept untouched
    val, changed = strip_known_label("UnknownLabel: CustomValue-123")
    assert val == "UnknownLabel: CustomValue-123"
    assert changed is False

    # Already clean text
    val, changed = strip_known_label("Q-8821")
    assert val == "Q-8821"
    assert changed is False

    # Empty / whitespace
    val, changed = strip_known_label("")
    assert val == ""
    assert changed is False


@pytest.mark.unit
def test_clean_vendor_name() -> None:
    # Real live gpt-5-mini examples
    val, changed, err = clean_vendor_name(
        "Gulf Line IT Trading TRN: 100000000000002 Office 402, Tamouh Tower, "
        "Al Reem Island, Abu Dhabi, UAE"
    )
    assert val == "Gulf Line IT Trading"
    assert changed is True
    assert err is False

    val, changed, err = clean_vendor_name(
        "Falcon Office Supplies LLC TRN: 100000000000001 Warehouse 14, "
        "Sector M-9, Mussafah Industrial Area, Abu Dhabi, UAE"
    )
    assert val == "Falcon Office Supplies LLC"
    assert changed is True
    assert err is False

    val, changed, err = clean_vendor_name(
        "Oasis Facility Services TRN: 100000000000003 Building 7, ICAD 1, "
        "Musaffah South, Abu Dhabi, UAE"
    )
    assert val == "Oasis Facility Services"
    assert changed is True
    assert err is False

    # Name containing "Office" that is part of company name should NOT be stripped
    val, changed, err = clean_vendor_name("Falcon Office Supplies LLC")
    assert val == "Falcon Office Supplies LLC"
    assert changed is False
    assert err is False

    # Newline cut
    val, changed, err = clean_vendor_name("Desert Build Materials\nPlot 88, Mina Zayed Port")
    assert val == "Desert Build Materials"
    assert changed is True
    assert err is False

    # Leading label
    val, changed, err = clean_vendor_name("Vendor: Corniche Electrical Co.")
    assert val == "Corniche Electrical Co."
    assert changed is True
    assert err is False

    # None and empty
    assert clean_vendor_name(None) == (None, False, False)
    assert clean_vendor_name("") == (None, False, False)


@pytest.mark.unit
def test_clean_trn() -> None:
    val, changed, err = clean_trn("TRN: 100000000000002")
    assert val == "100000000000002"
    assert changed is True
    assert err is False

    val, changed, err = clean_trn("100000000000002")
    assert val == "100000000000002"
    assert changed is False
    assert err is False

    # Invalid TRN digits
    val, changed, err = clean_trn("TRN: 12345")
    assert err is True

    # None and empty
    assert clean_trn(None) == (None, False, False)
    assert clean_trn("") == (None, False, False)


@pytest.mark.unit
def test_clean_amount() -> None:
    # Real live examples
    val, changed, err = clean_amount("28875.00 AED")
    assert val == "28875.00"
    assert changed is True
    assert err is False

    val, changed, err = clean_amount("Subtotal: 28400.00 AED")
    assert val == "28400.00"
    assert changed is True
    assert err is False

    val, changed, err = clean_amount("VAT (5%): 1420.00 AED")
    assert val == "1420.00"
    assert changed is True
    assert err is False

    val, changed, err = clean_amount("Total Amount: 29820.00 AED")
    assert val == "29820.00"
    assert changed is True
    assert err is False

    # Commas (thousands separators)
    val, changed, err = clean_amount("AED 1,234,567.89")
    assert val == "1234567.89"
    assert changed is True
    assert err is False

    # Negative amount
    val, changed, err = clean_amount("-150.00 AED")
    assert val == "-150.00"
    assert changed is True
    assert err is False

    # Arabic currency
    val, changed, err = clean_amount("1500 د.إ")
    assert val == "1500.00"
    assert changed is True
    assert err is False

    # Already clean
    val, changed, err = clean_amount("28875.00")
    assert val == "28875.00"
    assert changed is False
    assert err is False

    # Invalid amount
    val, changed, err = clean_amount("NonNumeric")
    assert err is True

    # None and empty
    assert clean_amount(None) == (None, False, False)
    assert clean_amount("") == (None, False, False)


@pytest.mark.unit
def test_clean_currency() -> None:
    val, changed, err = clean_currency("Currency: AED")
    assert val == "AED"
    assert changed is True

    val, changed, err = clean_currency("Dhs")
    assert val == "AED"
    assert changed is True

    val, changed, err = clean_currency("د.إ")
    assert val == "AED"
    assert changed is True

    val, changed, err = clean_currency("AED")
    assert val == "AED"
    assert changed is False

    val, changed, err = clean_currency("USD")
    assert val == "USD"
    assert changed is False

    # OCR confusions (e.g. AEO -> AED, AFD -> AED)
    val, changed, err = clean_currency("AEO")
    assert val == "AED"
    assert changed is True
    assert err is False

    val, changed, err = clean_currency("AFD")
    assert val == "AED"
    assert changed is True
    assert err is False

    # AEO + text content Currency: AED -> AED
    val, changed, err = clean_currency("AEO", text_content="Currency: AED")
    assert val == "AED"
    assert changed is True
    assert err is False

    # Unknown 3-letter code not in ISO whitelist fails parse unless context confirms
    val, changed, err = clean_currency("ZZZ")
    assert val == "ZZZ"
    assert err is True

    # Unknown code with UAE context defaults to AED
    val, changed, err = clean_currency("ZZZ", text_content="TRN: 100000000000002 Abu Dhabi UAE")
    assert val == "AED"
    assert changed is True
    assert err is False

    assert clean_currency(None) == (None, False, False)
    assert clean_currency("") == (None, False, False)


@pytest.mark.unit
def test_clean_payment_terms() -> None:
    # Basic canonical normalization
    val, changed, err = clean_payment_terms("Payment Terms: Net 30")
    assert val == "Net 30"
    assert changed is True
    assert err is False

    val, changed, err = clean_payment_terms("Net 30")
    assert val == "Net 30"
    assert changed is False
    assert err is False

    val, changed, err = clean_payment_terms("net 45")
    assert val == "Net 45"
    assert changed is True
    assert err is False

    val, changed, err = clean_payment_terms("30 days")
    assert val == "Net 30"
    assert changed is True
    assert err is False

    # Digit OCR confusions resolved by text layer (0 vs 8)
    val, changed, err = clean_payment_terms("net 38", text_content="Payment Terms: Net 30")
    assert val == "Net 30"
    assert changed is True
    assert err is False

    val, changed, err = clean_payment_terms("Net 68", text_content="Net 60")
    assert val == "Net 60"
    assert changed is True
    assert err is False

    # Clean Net 30 with matching text stays Net 30
    val, changed, err = clean_payment_terms("Net 30", text_content="Payment Terms: Net 30")
    assert val == "Net 30"
    assert changed is False
    assert err is False

    # Via clean_header_field dispatch
    val_hf, _, _ = clean_header_field(
        "payment_terms", "net 38", text_content="Payment Terms: Net 30"
    )
    assert val_hf == "Net 30"
    val_curr, _, _ = clean_header_field("currency", "AEO")
    assert val_curr == "AED"
    val_lt, _, _ = clean_header_field("lead_time_days", "5 days")
    assert val_lt == "5"

    assert clean_payment_terms(None) == (None, False, False)
    assert clean_payment_terms("") == (None, False, False)


@pytest.mark.unit
def test_clean_lead_time() -> None:
    val, changed, err = clean_lead_time("Delivery Lead Time: 5 days")
    assert val == "5"
    assert changed is True
    assert err is False
    assert parse_lead_time(val) == 5

    val, changed, err = clean_lead_time("7 days")
    assert val == "7"
    assert changed is True
    assert err is False
    assert parse_lead_time(val) == 7

    val, changed, err = clean_lead_time("10 days")
    assert val == "10"
    assert changed is True
    assert err is False
    assert parse_lead_time(val) == 10

    val, changed, err = clean_lead_time("5")
    assert val == "5"
    assert changed is False
    assert err is False
    assert parse_lead_time(val) == 5

    val, changed, err = clean_lead_time("2 weeks")
    assert val == "14"
    assert changed is True
    assert err is False
    assert parse_lead_time(val) == 14

    # Missing value recovered from text layer
    val, changed, err = clean_lead_time(None, text_content="Delivery Lead Time: 5 days")
    assert val == "5"
    assert changed is True
    assert err is False
    assert parse_lead_time(val) == 5

    val, changed, err = clean_lead_time(
        None, text_content="Landscape format quote with 10-day delivery"
    )
    assert val == "10"
    assert changed is True
    assert err is False
    assert parse_lead_time(val) == 10

    assert clean_lead_time(None) == (None, False, False)
    assert clean_lead_time("") == (None, False, False)


@pytest.mark.unit
def test_clean_date() -> None:
    # ISO format with label
    val, changed, err = clean_date("Date: 2026-11-04")
    assert val == "2026-11-04"
    assert changed is True
    assert err is False

    # UAE default DD/MM/YYYY
    val, changed, err = clean_date("04/11/2026")
    assert val == "2026-11-04"
    assert changed is True
    assert err is False

    # DD-Mon-YYYY
    val, changed, err = clean_date("04-Nov-2026")
    assert val == "2026-11-04"
    assert changed is True
    assert err is False

    val, changed, err = clean_date("4 November 2026")
    assert val == "2026-11-04"
    assert changed is True
    assert err is False

    # Already clean ISO
    val, changed, err = clean_date("2026-11-04")
    assert val == "2026-11-04"
    assert changed is False
    assert err is False

    # Invalid date
    val, changed, err = clean_date("NotADate")
    assert err is True

    assert clean_date(None) == (None, False, False)
    assert clean_date("") == (None, False, False)


@pytest.mark.unit
def test_clean_quantity() -> None:
    val, changed, err = clean_quantity("15 EA")
    assert val == "15"
    assert changed is True
    assert err is False

    val, changed, err = clean_quantity("10 units")
    assert val == "10"
    assert changed is True
    assert err is False

    val, changed, err = clean_quantity("100 ROLL")
    assert val == "100"
    assert changed is True
    assert err is False

    val, changed, err = clean_quantity("10")
    assert val == "10"
    assert changed is False
    assert err is False

    assert clean_quantity(None) == (None, False, False)
    assert clean_quantity("") == (None, False, False)


@pytest.mark.unit
def test_cleanup_extraction_result() -> None:
    ext = ExtractionResult(
        doc_type="quote",
        header={
            "vendor_name": FieldValue(
                value=(
                    "Falcon Office Supplies LLC TRN: 100000000000001 "
                    "Warehouse 14, Sector M-9, Mussafah"
                ),
                page=1,
                source_text="Falcon Office Supplies LLC TRN: 100000000000001",
            ),
            "vendor_trn": FieldValue(
                value="TRN: 100000000000001", page=1, source_text="TRN: 100000000000001"
            ),
            "document_number": FieldValue(
                value="Number: Q-8821", page=1, source_text="Number: Q-8821"
            ),
            "document_date": FieldValue(
                value="Date: 2026-11-04", page=1, source_text="Date: 2026-11-04"
            ),
            "currency": FieldValue(value="Currency: AED", page=1, source_text="Currency: AED"),
            "payment_terms": FieldValue(
                value="Payment Terms: Net 30", page=1, source_text="Payment Terms: Net 30"
            ),
            "subtotal": FieldValue(
                value="Subtotal: 28400.00 AED", page=1, source_text="Subtotal: 28400.00 AED"
            ),
            "vat_amount": FieldValue(
                value="VAT (5%): 1420.00 AED", page=1, source_text="VAT (5%): 1420.00 AED"
            ),
            "total": FieldValue(
                value="Total Amount: 29820.00 AED", page=1, source_text="Total Amount: 29820.00 AED"
            ),
        },
        lines=[
            ExtractionLineItem(
                line_no=1,
                item_code="IT-01",
                description="Laptop",
                qty="10 EA",
                uom="EA",
                unit_price="1950.00 AED",
                discount="0.00",
                vat_rate="5%",
                line_total="19500.00 AED",
                page=1,
                source_text="10 EA 1950.00 19500.00",
            ),
            ExtractionLineItem(
                line_no=2,
                item_code="IT-02",
                description="Monitor",
                qty="10 EA",
                uom="EA",
                unit_price="890.00 AED",
                discount="0.00",
                vat_rate="5%",
                line_total="8900.00 AED",
                page=1,
                source_text="10 EA 890.00 8900.00",
            ),
        ],
    )

    cleaned, meta = cleanup_extraction_result(ext)

    # Check header cleaned values
    assert cleaned.header["vendor_name"].value == "Falcon Office Supplies LLC"
    assert cleaned.header["vendor_trn"].value == "100000000000001"
    assert cleaned.header["document_number"].value == "Q-8821"
    assert cleaned.header["document_date"].value == "2026-11-04"
    assert cleaned.header["currency"].value == "AED"
    assert cleaned.header["payment_terms"].value == "Net 30"
    assert cleaned.header["subtotal"].value == "28400.00"
    assert cleaned.header["vat_amount"].value == "1420.00"
    assert cleaned.header["total"].value == "29820.00"

    # Source texts are preserved untouched
    assert (
        cleaned.header["vendor_name"].source_text
        == "Falcon Office Supplies LLC TRN: 100000000000001"
    )
    assert cleaned.header["document_number"].source_text == "Number: Q-8821"

    # Lines cleaned
    assert cleaned.lines[0].qty == "10"
    assert cleaned.lines[0].unit_price == "1950.00"
    assert cleaned.lines[0].line_total == "19500.00"
    assert cleaned.lines[0].vat_rate == "5"

    assert cleaned.lines[1].qty == "10"
    assert cleaned.lines[1].unit_price == "890.00"
    assert cleaned.lines[1].line_total == "8900.00"

    # Metadata records changes
    assert meta.was_cleaned("vendor_name") is True
    assert meta.was_cleaned("vendor_trn") is True
    assert meta.was_cleaned("document_number") is True
    assert meta.was_cleaned("document_date") is True
    assert meta.was_cleaned("subtotal") is True
    assert meta.was_cleaned("lines[0].qty") is True

    # Arithmetic checks passed: 28400 + 1420 == 29820, lines sum to 28400
    assert meta.has_arithmetic_mismatch("total") is False
    assert meta.has_arithmetic_mismatch("subtotal") is False


@pytest.mark.unit
def test_cleanup_detects_arithmetic_mismatch() -> None:
    ext = ExtractionResult(
        doc_type="invoice",
        header={
            "subtotal": FieldValue(value="1000.00", page=1, source_text="1000"),
            "vat_amount": FieldValue(value="50.00", page=1, source_text="50"),
            "total": FieldValue(value="1500.00", page=1, source_text="1500"),  # Mismatch!
        },
        lines=[],
    )
    cleaned, meta = cleanup_extraction_result(ext)
    assert meta.has_arithmetic_mismatch("total") is True
    assert meta.has_arithmetic_mismatch("subtotal") is True
    assert meta.has_arithmetic_mismatch("vat_amount") is True


@pytest.mark.unit
def test_cleanup_extraction_result_recovers_lead_time_from_text() -> None:
    ext = ExtractionResult(
        doc_type="quote",
        header={
            "vendor_name": FieldValue(value="Gulf Line IT Trading", page=1),
            "document_number": FieldValue(value="Q-1042", page=1),
            "currency": FieldValue(value="AED", page=1),
            "total": FieldValue(value="28875.00", page=1),
        },
        lines=[],
    )
    page_text = (
        "Gulf Line IT Trading\n"
        "QUOTATION Number: Q-1042\n"
        "Currency: AED\n"
        "Payment Terms: Net 30\n"
        "Delivery Lead Time: 5 days\n"
        "Total: 28875.00 AED"
    )
    cleaned, meta = cleanup_extraction_result(ext, text_content=page_text)

    assert "lead_time_days" in cleaned.header
    assert cleaned.header["lead_time_days"] is not None
    assert cleaned.header["lead_time_days"].value == "5"
    assert parse_lead_time(cleaned.header["lead_time_days"].value) == 5
    assert meta.was_cleaned("lead_time_days") is True


@pytest.mark.unit
def test_cleanup_extraction_result_fixes_aeo_and_terms() -> None:
    ext = ExtractionResult(
        doc_type="quote",
        header={
            "vendor_name": FieldValue(value="Gulf Line IT Trading", page=1),
            "document_number": FieldValue(value="Q-1042", page=1),
            "currency": FieldValue(value="AEO", page=1, source_text="Currency: AEO"),
            "payment_terms": FieldValue(
                value="net 38", page=1, source_text="Payment Terms: net 38"
            ),
            "total": FieldValue(value="28875.00", page=1),
        },
        lines=[],
    )
    page_text = (
        "Gulf Line IT Trading\n"
        "QUOTATION Number: Q-1042\n"
        "Currency: AED\n"
        "Payment Terms: Net 30\n"
        "Delivery Lead Time: 5 days\n"
        "Total Amount: 28875.00 AED"
    )
    cleaned, meta = cleanup_extraction_result(ext, text_content=page_text)

    # AEO fixed to AED
    assert cleaned.header["currency"].value == "AED"
    assert meta.was_cleaned("currency") is True

    # net 38 fixed to Net 30
    assert cleaned.header["payment_terms"].value == "Net 30"
    assert meta.was_cleaned("payment_terms") is True

    # Lead time recovered
    assert cleaned.header["lead_time_days"].value == "5"
    assert parse_lead_time(cleaned.header["lead_time_days"].value) == 5
    assert meta.was_cleaned("lead_time_days") is True

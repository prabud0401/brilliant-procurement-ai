"""Deterministic business validation rules per design 6.3 and US-04."""

from __future__ import annotations

import difflib
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import Document, ExtractedField, Extraction, PurchaseOrder, Vendor


def parse_decimal(val: Any) -> Decimal | None:
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))
    cleaned = re.sub(r"[^\d\.\-]", "", str(val).strip())
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_date(val: Any) -> date | None:
    if not val:
        return None
    if isinstance(val, (date, datetime)):
        return val if isinstance(val, date) else val.date()
    s = str(val).strip()
    # Try ISO YYYY-MM-DD
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


class ValidationResult:
    def __init__(self) -> None:
        self.field_errors: dict[str, str] = {}
        self.line_errors: dict[int, str] = {}
        self.matched_vendor_id: Any | None = None
        self.duplicate_doc_id: Any | None = None


def validate_extracted_data(
    session: Session,
    document: Document,
    header_values: dict[str, str | None],
    line_items: list[dict[str, Any]],
) -> ValidationResult:
    """Run deterministic validation rules over extracted headers and lines."""
    res = ValidationResult()

    # 1. TRN validation: must be 15 digits
    trn_val = header_values.get("vendor_trn")
    if not trn_val:
        res.field_errors["vendor_trn"] = "Validation failed: TRN is missing"
    else:
        digits = re.sub(r"\D", "", trn_val)
        if len(digits) != 15:
            res.field_errors["vendor_trn"] = (
                f"Validation failed: TRN must be 15 digits (got {len(digits)})"
            )

    # 2. Line arithmetic: qty * unit_price - discount == line_total
    lines_sum = Decimal("0.00")
    for idx, line in enumerate(line_items, start=1):
        qty = parse_decimal(line.get("qty"))
        price = parse_decimal(line.get("unit_price"))
        disc = parse_decimal(line.get("discount")) or Decimal("0.00")
        total = parse_decimal(line.get("line_total"))

        if qty is not None and price is not None and total is not None:
            expected = (qty * price) - disc
            diff = abs(expected - total)
            if diff > Decimal("0.05"):
                res.line_errors[idx] = (
                    f"Validation failed: {qty} * {price} - {disc} != {total} "
                    f"(expected {expected:.2f})"
                )
            lines_sum += total
        elif total is not None:
            lines_sum += total

    # 3. Subtotal sum: sum of line totals == subtotal (within 0.05)
    subtotal = parse_decimal(header_values.get("subtotal"))
    if subtotal is not None and len(line_items) > 0:
        if abs(subtotal - lines_sum) > Decimal("0.05"):
            res.field_errors["subtotal"] = (
                f"Validation failed: lines sum to {lines_sum:.2f} (got {subtotal:.2f})"
            )

    # 4. VAT rate and amount: VAT must be 5% of taxable amount (±AED 1.00)
    vat_val = parse_decimal(header_values.get("vat_amount"))
    if subtotal is not None and vat_val is not None:
        expected_vat = (subtotal * Decimal("0.05")).quantize(Decimal("0.01"))
        diff_vat = abs(expected_vat - vat_val)
        if diff_vat > Decimal("1.00"):
            res.field_errors["vat_amount"] = (
                f"Validation failed: VAT is not 5% of taxable amount "
                f"(expected {expected_vat:.2f}, got {vat_val:.2f})"
            )

    # 5. Subtotal + VAT == Total (within 0.05)
    total_val = parse_decimal(header_values.get("total"))
    if subtotal is not None and vat_val is not None and total_val is not None:
        expected_total = subtotal + vat_val
        if abs(expected_total - total_val) > Decimal("0.05"):
            res.field_errors["total"] = (
                f"Validation failed: subtotal ({subtotal:.2f}) + VAT ({vat_val:.2f}) "
                f"!= total ({total_val:.2f})"
            )

    # 6. Date validation: document_date not far in the future, due_date >= document_date
    doc_date = parse_date(header_values.get("document_date"))
    now_date = datetime.now(timezone.utc).date()
    if doc_date is not None:
        if doc_date > now_date + timedelta(days=1):
            res.field_errors["document_date"] = (
                f"Validation failed: document date {doc_date} is in the future"
            )
    due_date = parse_date(header_values.get("due_date"))
    if doc_date is not None and due_date is not None:
        if due_date < doc_date:
            res.field_errors["due_date"] = (
                f"Validation failed: due date {due_date} is before document date {doc_date}"
            )

    # 7. PO reference check
    po_num = header_values.get("po_number")
    if po_num and po_num.strip():
        po_record = session.execute(
            select(PurchaseOrder).where(PurchaseOrder.number == po_num.strip())
        ).scalar_one_or_none()
        if not po_record and not re.match(r"^PO-\d{4,}$", po_num.strip()):
            res.field_errors["po_number"] = f"Validation failed: PO reference {po_num} not found"

    # 8. Vendor matching (US-05)
    vendor_trn = header_values.get("vendor_trn")
    vendor_name = header_values.get("vendor_name")
    if vendor_trn:
        digits_trn = re.sub(r"\D", "", vendor_trn)
        vendor = session.execute(
            select(Vendor).where(Vendor.trn == digits_trn)
        ).scalar_one_or_none()
        if vendor:
            res.matched_vendor_id = vendor.id

    if not res.matched_vendor_id and vendor_name:
        clean_name = vendor_name.strip().lower()
        all_vendors = session.execute(select(Vendor)).scalars().all()
        for v in all_vendors:
            v_clean = v.name.lower()
            ratio = difflib.SequenceMatcher(None, clean_name, v_clean).ratio()
            if ratio >= 0.80 or v_clean in clean_name or clean_name in v_clean:
                res.matched_vendor_id = v.id
                break

    # 9. Duplicate document check (US-06)
    doc_num = header_values.get("document_number")
    if doc_num and doc_num.strip():
        # Query existing documents that have the same document_number in extracted_fields
        stmt = (
            select(Extraction.document_id)
            .join(ExtractedField, ExtractedField.extraction_id == Extraction.id)
            .where(
                Extraction.document_id != document.id,
                ExtractedField.name == "document_number",
                ExtractedField.value_raw == doc_num.strip(),
            )
        )
        existing_dup = session.execute(stmt).scalars().first()
        if existing_dup:
            res.duplicate_doc_id = existing_dup

    return res

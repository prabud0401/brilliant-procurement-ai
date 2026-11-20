"""Deterministic value cleanup and normalization per design 6.3 and US-04."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.ai.schemas import ExtractionResult, FieldValue

# ---------------------------------------------------------------------------
# Known Leading Label Patterns (case-insensitive)
# ---------------------------------------------------------------------------
# Known labels for document numbers, dates, currency, terms, amounts, etc.
KNOWN_LABEL_PREFIXES = [
    r"number",
    r"no\.?",
    r"doc(?:ument)?\s*(?:no\.?|number)",
    r"invoice\s*(?:no\.?|number)",
    r"quote\s*(?:no\.?|number)",
    r"quotation\s*(?:no\.?|number)",
    r"po\s*(?:no\.?|number)",
    r"dn\s*(?:no\.?|number)",
    r"delivery\s*note\s*(?:no\.?|number)",
    r"purchase\s*order\s*(?:no\.?|number)",
    r"pr\s*(?:no\.?|number)",
    r"trn",
    r"tax\s*registration\s*number",
    r"vat\s*(?:registration\s*)?no\.?",
    r"tax\s*no\.?",
    r"date",
    r"doc(?:ument)?\s*date",
    r"invoice\s*date",
    r"quote\s*date",
    r"quotation\s*date",
    r"po\s*date",
    r"delivery\s*date",
    r"due\s*date",
    r"due",
    r"currency",
    r"curr\.?",
    r"payment\s*terms",
    r"terms\s*(?:and\s*conditions)?",
    r"subtotal",
    r"sub-total",
    r"sub\s*total",
    r"total\s*amount",
    r"total",
    r"vat\s*(?:\([^)]*\))?",
    r"vat\s*amount",
    r"tax\s*(?:\([^)]*\))?",
    r"unit\s*price",
    r"line\s*total",
    r"quantity",
    r"qty",
    r"discount",
]

_LEADING_LABEL_REGEX = re.compile(
    r"^\s*(?:" + "|".join(KNOWN_LABEL_PREFIXES) + r")\s*[:#-]?\s*",
    re.IGNORECASE,
)

# Currency symbol and code mappings to ISO 4217
_CURRENCY_MAP: dict[str, str] = {
    "aed": "AED",
    "dhs": "AED",
    "dh": "AED",
    "dirham": "AED",
    "dirhams": "AED",
    "د.إ": "AED",
    "درهم": "AED",
    "درهم إماراتي": "AED",
    "usd": "USD",
    "$": "USD",
    "us dollar": "USD",
    "eur": "EUR",
    "€": "EUR",
    "euro": "EUR",
    "gbp": "GBP",
    "£": "GBP",
    "pound": "GBP",
    "sar": "SAR",
    "sr": "SAR",
    "saudi riyal": "SAR",
}

# Regex to detect vendor name cutoff markers (TRN, structured address, phone, email)
_VENDOR_NAME_CUTOFF_REGEX = re.compile(
    r"\b(?:"
    r"TRN|Tax\s*Registration\s*Number|VAT\s*(?:Registration\s*)?No\.?|"
    r"Warehouse\s+\d+|Office\s+\d+|Building\s+\d+|Sector\s+[A-Za-z0-9\-]+|Plot\s+\d+|"
    r"P\.?O\.?\s*Box\s*\d+|"
    r"Phone|Tel|Telephone|Mobile|Fax|Email|E-mail|\+971"
    r")\b",
    re.IGNORECASE,
)


def strip_known_label(val: str) -> tuple[str, bool]:
    """Strip known leading labels (with :/#/-) from text.

    If the label is not in the known list, the original text is preserved.
    Returns (cleaned_str, was_changed).
    """
    if not val:
        return val, False
    m = _LEADING_LABEL_REGEX.match(val)
    if m:
        cleaned = val[m.end() :].strip()
        return cleaned, (cleaned != val)
    return val, False


def clean_trn(val: str | None) -> tuple[str | None, bool, bool]:
    """Extract 15-digit TRN, stripping labels and formatting.

    Returns (cleaned_val, was_changed, parse_failed).
    """
    if val is None:
        return None, False, False
    s = val.strip()
    if not s:
        return None, False, False

    stripped, label_stripped = strip_known_label(s)
    digits = re.sub(r"\D", "", stripped)
    if len(digits) == 15:
        changed = s != digits
        return digits, changed, False

    # Does not form a valid 15-digit TRN
    changed = s != stripped
    return stripped, changed, True


def clean_vendor_name(val: str | None) -> tuple[str | None, bool, bool]:
    """Clean vendor name by stripping leading labels and cutting at TRN/address/email/phone.

    Returns (cleaned_val, was_changed, parse_failed).
    """
    if val is None:
        return None, False, False
    s = val.strip()
    if not s:
        return None, False, False

    # 1. Cut at first newline
    first_line = s.splitlines()[0].strip()

    # 2. Strip leading labels e.g. "Vendor:", "Supplier:"
    label_cut = re.sub(
        r"^\s*(?:Vendor(?:\s*Name)?|Supplier|Company)\s*[:#-]?\s*",
        "",
        first_line,
        flags=re.IGNORECASE,
    ).strip()

    # 3. Cut at TRN / address / phone / email marker
    m = _VENDOR_NAME_CUTOFF_REGEX.search(label_cut)
    if m:
        cleaned = label_cut[: m.start()].strip(" ,;:-")
    else:
        cleaned = label_cut.strip(" ,;:-")

    changed = s != cleaned
    return cleaned, changed, False


def clean_amount(val: str | None) -> tuple[str | None, bool, bool]:
    """Parse amount to Decimal text (e.g. '28875.00'), removing currency codes and commas.

    Preserves sign (+/-). Returns (cleaned_val, was_changed, parse_failed).
    """
    if val is None:
        return None, False, False
    s = val.strip()
    if not s:
        return None, False, False

    # 1. Strip known leading label (e.g. Subtotal:, Total:, VAT (5%):)
    stripped, _ = strip_known_label(s)

    # 2. Strip currency symbols and names
    clean = re.sub(
        r"(?i)\b(?:AED|DHS|DIRHAMS?|USD|EUR|GBP|SAR)\b",
        "",
        stripped,
    )
    clean = re.sub(r"[^\d\.\-\+]", "", clean).strip()

    if not clean or clean in ("-", "+", "."):
        return s, False, True

    try:
        d = Decimal(clean).quantize(Decimal("0.01"))
        formatted = f"{d:.2f}"
        changed = s != formatted
        return formatted, changed, False
    except (InvalidOperation, ValueError):
        return s, False, True


def clean_currency(val: str | None) -> tuple[str | None, bool, bool]:
    """Map currency string to ISO 4217 code (AED, USD, EUR, etc.).

    Returns (cleaned_val, was_changed, parse_failed).
    """
    if val is None:
        return None, False, False
    s = val.strip()
    if not s:
        return None, False, False

    # Strip leading label e.g. "Currency:", "Curr:"
    stripped, _ = strip_known_label(s)
    clean_lower = stripped.lower().strip()

    for k, iso in _CURRENCY_MAP.items():
        if k in clean_lower:
            changed = s != iso
            return iso, changed, False

    # If already a 3-letter code, uppercase it
    if re.match(r"^[a-zA-Z]{3}$", stripped):
        iso_val = stripped.upper()
        changed = s != iso_val
        return iso_val, changed, False

    return stripped, (s != stripped), False


def clean_date(val: str | None) -> tuple[str | None, bool, bool]:
    """Parse common date formats (UAE DD/MM/YYYY, DD-Mon-YYYY, ISO) to ISO YYYY-MM-DD.

    Returns (cleaned_val, was_changed, parse_failed).
    """
    if val is None:
        return None, False, False
    s = val.strip()
    if not s:
        return None, False, False

    stripped, _ = strip_known_label(s)

    # Common formats: ISO, UAE DD/MM/YYYY, DD-Mon-YYYY
    formats = (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%Y/%m/%d",
    )
    for fmt in formats:
        try:
            dt = datetime.strptime(stripped, fmt)
            iso = dt.strftime("%Y-%m-%d")
            changed = s != iso
            return iso, changed, False
        except ValueError:
            pass

    # Regex fallback for YYYY-MM-DD or DD/MM/YYYY
    m1 = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", stripped)
    if m1:
        y, m, d = m1.groups()
        iso = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        return iso, (s != iso), False

    m2 = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", stripped)
    if m2:
        d, m, y = m2.groups()
        iso = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        return iso, (s != iso), False

    return stripped, (s != stripped), True


def clean_quantity(val: str | None) -> tuple[str | None, bool, bool]:
    """Clean line-item quantity: strip leading label, remove trailing UOM/units.

    Returns (cleaned_val, was_changed, parse_failed).
    """
    if val is None:
        return None, False, False
    s = val.strip()
    if not s:
        return None, False, False

    stripped, _ = strip_known_label(s)

    # Remove trailing UOM words (e.g. EA, units, PCS, roll, boxes, etc.)
    cleaned = re.sub(
        r"(?i)\s+(?:EA|PCS|PIECES?|UNITS?|ROLLS?|BOXES?|SETS?|ITEMS?)$",
        "",
        stripped,
    ).strip()
    cleaned = cleaned.replace(",", "")

    try:
        d = Decimal(cleaned)
        # If integer quantity, format as int without decimal point
        if d == d.to_integral():
            result = str(int(d))
        else:
            result = f"{d:.2f}"
        changed = s != result
        return result, changed, False
    except (InvalidOperation, ValueError):
        return stripped, (s != stripped), True


def clean_header_field(fname: str, val: str | None) -> tuple[str | None, bool, bool]:
    """Dispatch cleanup for a specific header field.

    Returns (cleaned_val, was_changed, parse_failed).
    """
    if val is None:
        return None, False, False

    if fname == "vendor_name":
        return clean_vendor_name(val)
    if fname == "vendor_trn":
        return clean_trn(val)
    if fname in ("subtotal", "vat_amount", "total"):
        return clean_amount(val)
    if fname in ("document_date", "due_date"):
        return clean_date(val)
    if fname == "currency":
        return clean_currency(val)
    if fname in ("document_number", "po_number", "payment_terms"):
        stripped, changed = strip_known_label(val)
        return stripped, changed, False

    # Default fallback: strip known label
    stripped, changed = strip_known_label(val)
    return stripped, changed, False


@dataclass
class CleanupMetadata:
    """Records which fields were modified, failed parsing, or had arithmetic mismatches."""

    changed_fields: set[str] = field(default_factory=set)
    failed_fields: set[str] = field(default_factory=set)
    arithmetic_mismatches: set[str] = field(default_factory=set)

    def was_cleaned(self, field_name: str) -> bool:
        return field_name in self.changed_fields

    def parse_failed(self, field_name: str) -> bool:
        return field_name in self.failed_fields

    def has_arithmetic_mismatch(self, field_name: str) -> bool:
        return field_name in self.arithmetic_mismatches

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed_fields": sorted(self.changed_fields),
            "failed_fields": sorted(self.failed_fields),
            "arithmetic_mismatches": sorted(self.arithmetic_mismatches),
        }


def cleanup_extraction_result(
    result: ExtractionResult,
) -> tuple[ExtractionResult, CleanupMetadata]:
    """Apply deterministic value cleanup across all header fields and line items.

    Preserves source_text verbatim. Updates values in place and returns
    (result, cleanup_metadata).
    """
    meta = CleanupMetadata()

    # 1. Clean header fields
    for fname, draft_field in result.header.items():
        if draft_field is None or draft_field.value is None:
            continue
        cleaned_val, was_changed, parse_err = clean_header_field(fname, draft_field.value)
        draft_field.value = cleaned_val
        if was_changed:
            meta.changed_fields.add(fname)
        if parse_err:
            meta.failed_fields.add(fname)

    # 1b. Fallback: for purchase orders, if document_number is missing but po_number exists
    if result.doc_type in ("purchase_order", "po") or "purchase" in result.doc_type:
        doc_num_field = result.header.get("document_number")
        po_num_field = result.header.get("po_number")
        if (not doc_num_field or not doc_num_field.value) and po_num_field and po_num_field.value:
            if doc_num_field is None:
                result.header["document_number"] = FieldValue(
                    value=po_num_field.value,
                    page=po_num_field.page,
                    source_text=po_num_field.source_text,
                )
            else:
                doc_num_field.value = po_num_field.value
                doc_num_field.source_text = po_num_field.source_text
            meta.changed_fields.add("document_number")

    # 2. Clean line items
    for idx, line in enumerate(result.lines):
        line_prefix = f"lines[{idx}]"

        # Quantity
        if line.qty is not None:
            c_qty, q_changed, q_err = clean_quantity(line.qty)
            line.qty = c_qty
            if q_changed:
                meta.changed_fields.add(f"{line_prefix}.qty")
            if q_err:
                meta.failed_fields.add(f"{line_prefix}.qty")

        # Unit price
        if line.unit_price is not None:
            c_price, p_changed, p_err = clean_amount(line.unit_price)
            line.unit_price = c_price
            if p_changed:
                meta.changed_fields.add(f"{line_prefix}.unit_price")
            if p_err:
                meta.failed_fields.add(f"{line_prefix}.unit_price")

        # Line total
        if line.line_total is not None:
            c_tot, t_changed, t_err = clean_amount(line.line_total)
            line.line_total = c_tot
            if t_changed:
                meta.changed_fields.add(f"{line_prefix}.line_total")
                meta.changed_fields.add("line_total")
            if t_err:
                meta.failed_fields.add(f"{line_prefix}.line_total")

        # Discount
        if line.discount is not None:
            c_disc, d_changed, d_err = clean_amount(line.discount)
            line.discount = c_disc
            if d_changed:
                meta.changed_fields.add(f"{line_prefix}.discount")
            if d_err:
                meta.failed_fields.add(f"{line_prefix}.discount")

        # VAT rate
        if line.vat_rate is not None:
            stripped_vr, _ = strip_known_label(str(line.vat_rate))
            cleaned_vr = stripped_vr.rstrip("%").strip()
            if cleaned_vr != str(line.vat_rate):
                meta.changed_fields.add(f"{line_prefix}.vat_rate")
            line.vat_rate = cleaned_vr

    # 3. Arithmetic checks
    # Subtotal + VAT == Total
    sub_f = result.header.get("subtotal")
    vat_f = result.header.get("vat_amount")
    tot_f = result.header.get("total")

    sub_val = None
    vat_val = None
    tot_val = None
    if sub_f and sub_f.value:
        try:
            sub_val = Decimal(sub_f.value)
        except InvalidOperation:
            pass
    if vat_f and vat_f.value:
        try:
            vat_val = Decimal(vat_f.value)
        except InvalidOperation:
            pass
    if tot_f and tot_f.value:
        try:
            tot_val = Decimal(tot_f.value)
        except InvalidOperation:
            pass

    if sub_val is not None and vat_val is not None and tot_val is not None:
        expected_total = sub_val + vat_val
        if abs(expected_total - tot_val) > Decimal("0.05"):
            meta.arithmetic_mismatches.add("subtotal")
            meta.arithmetic_mismatches.add("vat_amount")
            meta.arithmetic_mismatches.add("total")

    # Line sums vs subtotal
    if result.lines and sub_val is not None:
        line_sum = Decimal("0.00")
        all_lines_have_total = True
        for line in result.lines:
            if line.line_total:
                try:
                    line_sum += Decimal(line.line_total)
                except InvalidOperation:
                    all_lines_have_total = False
            else:
                all_lines_have_total = False

        if all_lines_have_total and abs(sub_val - line_sum) > Decimal("0.05"):
            meta.arithmetic_mismatches.add("subtotal")

    # Line internal arithmetic: qty * unit_price - discount == line_total
    for idx, line in enumerate(result.lines):
        line_prefix = f"lines[{idx}]"
        try:
            if line.qty and line.unit_price and line.line_total:
                l_q = Decimal(line.qty)
                l_p = Decimal(line.unit_price)
                l_d = Decimal(line.discount) if line.discount else Decimal("0.00")
                l_t = Decimal(line.line_total)
                expected_line = (l_q * l_p) - l_d
                if abs(expected_line - l_t) > Decimal("0.05"):
                    meta.arithmetic_mismatches.add(f"{line_prefix}.line_total")
                    meta.arithmetic_mismatches.add("line_total")
        except InvalidOperation:
            pass

    return result, meta

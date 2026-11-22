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
    r"delivery\s*(?:lead\s*)?time",
    r"lead\s*time",
    r"delivery\s*time",
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

# Whitelist of allowed ISO 4217 currency codes
ISO_4217_WHITELIST: set[str] = {
    "AED",
    "USD",
    "EUR",
    "GBP",
    "SAR",
    "QAR",
    "OMR",
    "BHD",
    "KWD",
    "CAD",
    "AUD",
    "JPY",
    "CNY",
    "CHF",
    "INR",
    "SGD",
    "NZD",
    "ZAR",
}

# Known OCR character confusions for AED (e.g. D -> O, D -> F, etc.)
_AED_OCR_CONFUSIONS: set[str] = {
    "aeo",
    "afd",
    "aee",
    "aeb",
    "aep",
    "aed",
    "aed.",
    "aed:",
}

_COMMERCIAL_NET_TERMS: tuple[int, ...] = (15, 30, 45, 60, 90)
_ALL_VALID_NET_TERMS: tuple[int, ...] = (7, 10, 14, 15, 30, 45, 60, 90, 120)


def _is_uae_context(text: str | None) -> bool:
    """Check if text contains UAE indicators (15-digit TRN, UAE cities/emirates, AED)."""
    if not text:
        return False
    patterns = [
        r"\b100\d{12}\b",
        r"\b(?:Abu\s*Dhabi|Dubai|Sharjah|Ajman|Umm\s*Al\s*Quwain|Ras\s*Al\s*Khaimah|Fujairah|UAE|U\.A\.E\.?|United\s*Arab\s*Emirates)\b",
        r"(?i)\b(?:AED|Dhs|Dirham|Dirhams|د\.إ|درهم)\b",
    ]
    return any(re.search(pat, text, re.IGNORECASE) for pat in patterns)


def _extract_currency_from_text(text: str | None) -> str | None:
    """Extract and validate ISO 4217 currency code from document / page text."""
    if not text:
        return None
    # 1. Explicit label e.g. "Currency: AED", "Currency: USD"
    m = re.search(
        r"(?i)\b(?:currency|curr\.?)\s*[:#-]?\s*([a-zA-Z]{3}|د\.إ|درهم|dhs?|dirhams?)\b",
        text,
    )
    if m:
        token = m.group(1).strip()
        token_lower = token.lower()
        if token_lower in _CURRENCY_MAP:
            return _CURRENCY_MAP[token_lower]
        if token_lower in _AED_OCR_CONFUSIONS:
            return "AED"
        if token.upper() in ISO_4217_WHITELIST:
            return token.upper()

    # 2. If text contains obvious UAE indicators, default to AED
    if _is_uae_context(text):
        return "AED"

    return None


def _extract_payment_terms_from_text(text: str | None) -> int | None:
    """Extract standard payment terms days from document / page text."""
    if not text:
        return None
    # 1. Explicit "Payment Terms: Net X" or "Payment Terms: X days"
    m = re.search(
        r"(?i)\b(?:payment\s*terms?|terms?)\s*[:#-]?\s*net\s*(\d{1,3})\b",
        text,
    )
    if m:
        return int(m.group(1))

    # 2. "Net 30", "Net 60", etc. in text
    all_net = re.findall(r"(?i)\bnet\s*(\d{1,3})\b", text)
    for n_str in all_net:
        n = int(n_str)
        if n in _COMMERCIAL_NET_TERMS:
            return n
    if all_net:
        return int(all_net[0])

    return None


def _extract_lead_time_from_text(text: str | None) -> int | None:
    """Extract delivery lead time in days from document / page text."""
    if not text:
        return None
    # 1. "Delivery Lead Time: N days" / "Lead Time: N days" / "Delivery Time: N days"
    m = re.search(
        r"(?i)\b(?:delivery\s*(?:lead\s*)?time|lead\s*time|delivery\s*time|delivery\s*within)\s*[:#-]?\s*(\d+)\s*(?:business\s*days?|working\s*days?|days?)?\b",
        text,
    )
    if m:
        return int(m.group(1))

    # 2. "Delivery Lead Time: N weeks"
    m_w = re.search(
        r"(?i)\b(?:delivery\s*(?:lead\s*)?time|lead\s*time|delivery\s*time)\s*[:#-]?\s*(\d+)\s*weeks?\b",
        text,
    )
    if m_w:
        return int(m_w.group(1)) * 7

    # 3. "N-day delivery" / "N days delivery"
    m_d = re.search(r"(?i)\b(\d+)[ -]day\s*delivery\b", text)
    if m_d:
        return int(m_d.group(1))

    return None


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


def clean_currency(
    val: str | None, text_content: str | None = None
) -> tuple[str | None, bool, bool]:
    """Map currency string to ISO 4217 code (AED, USD, EUR, etc.).

    Enforces ISO 4217 whitelist. Resolves OCR confusions (e.g. AEO -> AED).
    Falls back to valid ISO code or UAE context found in document text layer.
    Returns (cleaned_val, was_changed, parse_failed).
    """
    if val is None:
        if text_content:
            found = _extract_currency_from_text(text_content)
            if found:
                return found, True, False
        return None, False, False

    s = val.strip()
    if not s:
        if text_content:
            found = _extract_currency_from_text(text_content)
            if found:
                return found, True, False
        return None, False, False

    # Strip leading label e.g. "Currency:", "Curr:"
    stripped, _ = strip_known_label(s)
    clean_lower = stripped.lower().strip()

    # 1. Known symbol / word mapping
    for k, iso in _CURRENCY_MAP.items():
        if k == clean_lower or (len(k) > 2 and k in clean_lower):
            changed = s != iso
            return iso, changed, False

    # 2. Known OCR confusions for AED (e.g. AEO, AFD) -> map to AED
    if clean_lower in _AED_OCR_CONFUSIONS or stripped.upper() == "AEO":
        return "AED", (s != "AED"), False

    # 3. Check ISO 4217 whitelist
    if stripped.upper() in ISO_4217_WHITELIST:
        iso_val = stripped.upper()
        return iso_val, (s != iso_val), False

    # 4. Unknown code: check document text layer for a valid currency
    if text_content:
        found = _extract_currency_from_text(text_content)
        if found:
            return found, (s != found), False

    # 5. Fallback for UAE context or near AED
    if clean_lower.startswith("ae") or _is_uae_context(text_content) or _is_uae_context(s):
        return "AED", (s != "AED"), False

    # 6. Parse failed for unknown 3-letter code or non-currency string
    return stripped, (s != stripped), True


def clean_payment_terms(
    val: str | None, text_content: str | None = None
) -> tuple[str | None, bool, bool]:
    """Parse and normalise payment terms to canonical form e.g. 'Net 30'.

    Sanity-checks against document/page text layer to resolve OCR digit confusions
    (e.g. 'net 38' -> 'Net 30', 'Net 68' -> 'Net 60').
    Returns (cleaned_val, was_changed, parse_failed).
    """
    if val is None:
        return None, False, False

    s = val.strip()
    if not s:
        return None, False, False

    stripped, _ = strip_known_label(s)
    clean_lower = stripped.lower().strip()

    # Look for confirmed term in text_content
    confirmed_text_days = _extract_payment_terms_from_text(text_content)

    # 1. Matches "net XX" or "XX days net" or "XX days"
    m = re.search(r"(?i)\bnet\s*(\d+)\b", stripped)
    if not m:
        m = re.search(r"\b(\d+)\s*days?\b", stripped, re.IGNORECASE)

    if m:
        extracted_days = int(m.group(1))

        # Check if text layer confirms a canonical term
        if confirmed_text_days is not None:
            if extracted_days == confirmed_text_days:
                canonical = f"Net {confirmed_text_days}"
                return canonical, (s != canonical), False

            # Near miss check: digit confusion (0 vs 8: 38 vs 30, 68 vs 60, 98 vs 90)
            s_ext = str(extracted_days)
            s_conf = str(confirmed_text_days)
            is_digit_confusion = (
                s_ext.replace("8", "0") == s_conf
                or s_ext.replace("0", "8") == s_conf
                or (len(s_ext) == len(s_conf) and sum(a != b for a, b in zip(s_ext, s_conf)) <= 1)
            )
            if is_digit_confusion:
                canonical = f"Net {confirmed_text_days}"
                return canonical, True, False

        # If extracted_days is one of the valid standard terms, normalise to Net XX
        if extracted_days in _ALL_VALID_NET_TERMS:
            canonical = f"Net {extracted_days}"
            return canonical, (s != canonical), False

        # If no explicit text confirmation, check text_content for common commercial terms
        if text_content:
            for standard in _COMMERCIAL_NET_TERMS:
                s_std = str(standard)
                s_ext = str(extracted_days)
                if s_ext.replace("8", "0") == s_std and re.search(rf"\b{standard}\b", text_content):
                    canonical = f"Net {standard}"
                    return canonical, True, False

        canonical = f"Net {extracted_days}"
        return canonical, (s != canonical), False

    # Non-net phrases e.g. "immediate", "due on receipt", "advance", "cod"
    if "immediate" in clean_lower:
        return "Immediate", (s != "Immediate"), False
    if "receipt" in clean_lower or "due on" in clean_lower:
        return "Due on Receipt", (s != "Due on Receipt"), False
    if "advance" in clean_lower:
        return "Advance", (s != "Advance"), False
    if "cod" in clean_lower or "cash on delivery" in clean_lower:
        return "COD", (s != "COD"), False

    return stripped, (s != stripped), False


def clean_lead_time(
    val: str | None, text_content: str | None = None
) -> tuple[str | None, bool, bool]:
    """Parse and normalise delivery lead time in days (e.g. '5').

    Returns (cleaned_val_as_str_int, was_changed, parse_failed).
    """
    if val is not None:
        s = val.strip()
        if s and s.lower() not in (
            "none",
            "null",
            "n/a",
            "not specified",
            "unspecified",
            "unknown",
        ):
            stripped, _ = strip_known_label(s)
            m_w = re.search(r"\b(\d+)\s*weeks?\b", stripped, re.IGNORECASE)
            if m_w:
                days = int(m_w.group(1)) * 7
                result = str(days)
                return result, (s != result), False

            m = re.search(r"\b(\d+)\b", stripped)
            if m:
                days = int(m.group(1))
                if days > 0:
                    result = str(days)
                    return result, (s != result), False

    # If val is missing, empty, or unparseable, recover from text_content
    if text_content:
        extracted_days = _extract_lead_time_from_text(text_content)
        if extracted_days is not None and extracted_days > 0:
            result = str(extracted_days)
            changed = val is None or val.strip() != result
            return result, changed, False

    if val is not None and val.strip():
        return val.strip(), False, True

    return None, False, False


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


def clean_header_field(
    fname: str, val: str | None, text_content: str | None = None
) -> tuple[str | None, bool, bool]:
    """Dispatch cleanup for a specific header field.

    Returns (cleaned_val, was_changed, parse_failed).
    """
    if val is None and fname not in ("lead_time_days", "delivery_lead_time", "currency"):
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
        return clean_currency(val, text_content=text_content)
    if fname == "payment_terms":
        return clean_payment_terms(val, text_content=text_content)
    if fname in ("lead_time_days", "delivery_lead_time", "lead_time"):
        return clean_lead_time(val, text_content=text_content)
    if fname in ("document_number", "po_number"):
        stripped, changed = strip_known_label(val or "")
        return stripped, changed, False

    # Default fallback: strip known label
    stripped, changed = strip_known_label(val or "")
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
    text_content: str | None = None,
) -> tuple[ExtractionResult, CleanupMetadata]:
    """Apply deterministic value cleanup across all header fields and line items.

    Preserves source_text verbatim. Updates values in place and returns
    (result, cleanup_metadata).
    """
    meta = CleanupMetadata()

    # Collect source text snippets for fallback context
    source_texts = [
        fval.source_text for fval in result.header.values() if fval and fval.source_text
    ]
    full_context_text = f"{text_content or ''}\n" + "\n".join(source_texts)

    # 1. Clean header fields
    for fname, draft_field in result.header.items():
        if draft_field is None or draft_field.value is None:
            continue
        field_context = f"{full_context_text}\n{draft_field.source_text or ''}"
        cleaned_val, was_changed, parse_err = clean_header_field(
            fname, draft_field.value, text_content=field_context
        )
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

    # 1c. Recover lead_time_days if omitted or missing
    lead_time_field = result.header.get("lead_time_days")
    if lead_time_field is None or lead_time_field.value is None:
        lt_val, lt_changed, lt_err = clean_lead_time(None, text_content=full_context_text)
        if lt_val is not None:
            matched_snippet = f"Delivery Lead Time: {lt_val} days"
            if lead_time_field is None:
                result.header["lead_time_days"] = FieldValue(
                    value=lt_val,
                    page=1,
                    source_text=matched_snippet,
                )
            else:
                lead_time_field.value = lt_val
                if not lead_time_field.source_text:
                    lead_time_field.source_text = matched_snippet
            meta.changed_fields.add("lead_time_days")

    # 1d. Recover currency if omitted or missing and found in text
    curr_field = result.header.get("currency")
    if curr_field is None or curr_field.value is None:
        c_val, c_changed, c_err = clean_currency(None, text_content=full_context_text)
        if c_val is not None:
            if curr_field is None:
                result.header["currency"] = FieldValue(
                    value=c_val,
                    page=1,
                    source_text=f"Currency: {c_val}",
                )
            else:
                curr_field.value = c_val
            meta.changed_fields.add("currency")

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

"""Question redaction for logging per NFR-SEC-06 and design 3.4."""

from __future__ import annotations

import re

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
IBAN_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
TRN_PATTERN = re.compile(r"\b\d{15}\b")
DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?0?\d{1,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}\b"
)


def redact_question(text: str) -> str:
    """Mask emails, phone numbers, IBANs, and TRN numbers from question text."""
    if not text:
        return ""

    # 1. Mask Emails
    redacted = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)

    # 2. Mask IBANs
    redacted = IBAN_PATTERN.sub("[REDACTED_IBAN]", redacted)

    # 3. Mask TRNs (15-digit tax registration numbers)
    redacted = TRN_PATTERN.sub("[REDACTED_TRN]", redacted)

    # 4. Mask Phone numbers while preserving dates and invoice/PO numbers
    # Temporarily preserve dates
    dates: list[str] = []

    def save_date(match: re.Match[str]) -> str:
        dates.append(match.group(0))
        return f"__PRESERVED_DATE_{len(dates) - 1}__"

    redacted = DATE_PATTERN.sub(save_date, redacted)

    # Mask phone numbers that have at least 7 digits
    def mask_phone_match(match: re.Match[str]) -> str:
        val = match.group(0)
        digits = re.sub(r"\D", "", val)
        if 7 <= len(digits) <= 15:
            return "[REDACTED_PHONE]"
        return val

    redacted = PHONE_PATTERN.sub(mask_phone_match, redacted)

    # Restore preserved dates
    for idx, date_str in enumerate(dates):
        redacted = redacted.replace(f"__PRESERVED_DATE_{idx}__", date_str)

    return redacted

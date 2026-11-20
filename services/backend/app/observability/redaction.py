"""Logging filter and sanitizer for PII, secrets, and raw document text per design 7.6, 9.1."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.core.config import settings
from app.core.middleware import get_current_request_id

# Regex patterns
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
IBAN_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
TRN_PATTERN = re.compile(r"\b\d{15}\b")
BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*")
INTAKE_KEY_PATTERN = re.compile(r"(?i)\b(X-Intake-Key|intake_key)\s*[:=]\s*[^\s,]+")
JWT_PATTERN = re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b")
DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?0?\d{1,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}\b"
)

# Common sensitive keywords for document text or prompts
SENSITIVE_TEXT_KEYS = {
    "doc_text",
    "document_text",
    "raw_text",
    "ocr_content",
    "content",
    "page_text",
    "prompt",
    "prompt_text",
    "system_prompt",
    "user_prompt",
}


def redact_sensitive_text(text: str, is_dev: bool = False) -> str:
    """Mask emails, TRNs, IBANs, phone numbers, bearer tokens, and document text outside dev."""
    if not text:
        return text

    # 1. Mask Bearer, JWT, and API keys
    redacted = BEARER_PATTERN.sub("Bearer [REDACTED_TOKEN]", text)
    redacted = JWT_PATTERN.sub("[REDACTED_TOKEN]", redacted)
    redacted = INTAKE_KEY_PATTERN.sub(r"\1: [REDACTED_KEY]", redacted)

    # 2. Mask Emails
    redacted = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", redacted)

    # 3. Mask IBANs
    redacted = IBAN_PATTERN.sub("[REDACTED_IBAN]", redacted)

    # 4. Mask 15-digit TRNs (Tax Registration Numbers)
    redacted = TRN_PATTERN.sub("[REDACTED_TRN]", redacted)

    # 5. Mask Phone numbers while preserving date formats
    preserved_dates: list[str] = []

    def _preserve_date(match: re.Match[str]) -> str:
        preserved_dates.append(match.group(0))
        return f"__PRESERVED_DATE_{len(preserved_dates) - 1}__"

    redacted = DATE_PATTERN.sub(_preserve_date, redacted)

    def _mask_phone(match: re.Match[str]) -> str:
        val = match.group(0)
        digits = re.sub(r"\D", "", val)
        if 7 <= len(digits) <= 15:
            return "[REDACTED_PHONE]"
        return val

    redacted = PHONE_PATTERN.sub(_mask_phone, redacted)

    for idx, date_str in enumerate(preserved_dates):
        redacted = redacted.replace(f"__PRESERVED_DATE_{idx}__", date_str)

    # 6. Outside dev, redact document text / prompts if indicated
    if not is_dev and (
        "<chunk" in redacted or "<document" in redacted or "BEGIN INSTRUCTIONS" in redacted
    ):
        redacted = re.sub(
            r"<chunk[^>]*>.*?</chunk>", "[REDACTED_DOCUMENT_CHUNK]", redacted, flags=re.DOTALL
        )
        redacted = re.sub(
            r"<document[^>]*>.*?</document>", "[REDACTED_DOCUMENT_TEXT]", redacted, flags=re.DOTALL
        )

    return redacted


def _sanitize_obj(obj: Any, is_dev: bool) -> Any:
    """Recursively sanitize strings, dictionaries, lists, and tuples."""
    if isinstance(obj, str):
        return redact_sensitive_text(obj, is_dev=is_dev)
    if isinstance(obj, dict):
        sanitized: dict[str, Any] = {}
        for k, v in obj.items():
            k_str = str(k).lower()
            if not is_dev and k_str in SENSITIVE_TEXT_KEYS:
                sanitized[k] = "[REDACTED_DOCUMENT_TEXT]"
            else:
                sanitized[k] = _sanitize_obj(v, is_dev=is_dev)
        return sanitized
    if isinstance(obj, list):
        return [_sanitize_obj(item, is_dev=is_dev) for item in obj]
    if isinstance(obj, tuple):
        return tuple(_sanitize_obj(item, is_dev=is_dev) for item in obj)
    return obj


class RedactingFilter(logging.Filter):
    """Logging filter applied to API and worker loggers to redact PII and secrets."""

    def __init__(self, name: str = "") -> None:
        super().__init__(name)

    def filter(self, record: logging.LogRecord) -> bool:
        # Populate request_id for formatting
        if not hasattr(record, "request_id") or not record.request_id:
            record.request_id = get_current_request_id() or "-"

        is_dev = settings.APP_ENV in ("dev", "local")

        # Sanitize msg
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg, is_dev=is_dev)

        # Sanitize args
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(_sanitize_obj(arg, is_dev=is_dev) for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: _sanitize_obj(v, is_dev=is_dev) for k, v in record.args.items()}

        # Outside dev, verify no document text attributes exist
        if not is_dev:
            for key in SENSITIVE_TEXT_KEYS:
                if hasattr(record, key):
                    setattr(record, key, "[REDACTED_DOCUMENT_TEXT]")

        return True

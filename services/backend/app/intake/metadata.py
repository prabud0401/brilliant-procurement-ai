"""Metadata parsing, encoding/decoding, and sender allowlist validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.errors import ProblemException

_EMAIL_REGEX = re.compile(r"<([^>]+)>|([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")


def extract_clean_email(sender: str) -> str:
    """Extract plain email address from 'Display Name <email@example.com>' or plain email."""
    sender_stripped = sender.strip()
    match = _EMAIL_REGEX.search(sender_stripped)
    if match:
        email = match.group(1) or match.group(2)
        if email:
            return email.strip().lower()
    return sender_stripped.lower()


def parse_received_at(val: str | datetime) -> datetime:
    """Parse ISO datetime string or normalize datetime object to UTC timezone."""
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)

    s = val.strip()
    try:
        # Handle 'Z' suffix for python < 3.11 compatibility if needed
        clean_s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception as exc:
        raise ProblemException(
            status_code=400,
            code="INVALID_RECEIVED_AT",
            title="Invalid Timestamp",
            detail=f"Failed to parse received_at timestamp '{val}': {exc}",
        )


def is_sender_allowed(sender: str, allowlist: str | list[str] | set[str] | None) -> bool:
    """Check if sender is allowed against configured allowlist.

    Empty or None allowlist allows all senders.
    """
    if not allowlist:
        return True

    allowed_set: set[str] = set()
    if isinstance(allowlist, str):
        parts = [p.strip().lower() for p in allowlist.split(",") if p.strip()]
        allowed_set = set(parts)
    elif isinstance(allowlist, (list, set)):
        allowed_set = {extract_clean_email(str(item)) for item in allowlist if str(item).strip()}

    if not allowed_set:
        return True

    clean_sender = extract_clean_email(sender)
    return clean_sender in allowed_set


@dataclass(frozen=True)
class EmailMetadata:
    sender: str
    subject: str
    received_at: datetime
    message_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sender": self.sender,
            "subject": self.subject,
            "received_at": self.received_at.astimezone(timezone.utc).isoformat(),
            "message_id": self.message_id,
        }

    def to_source_url(self) -> str:
        """Serialize metadata into a JSON string stored in document.source_url."""
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_source_url(cls, source_url: str) -> EmailMetadata:
        """Deserialize EmailMetadata from document.source_url."""
        try:
            data = json.loads(source_url)
            return cls(
                sender=str(data.get("sender", "")),
                subject=str(data.get("subject", "")),
                received_at=parse_received_at(str(data.get("received_at", ""))),
                message_id=str(data.get("message_id", "")),
            )
        except Exception as exc:
            raise ValueError(f"Failed to parse EmailMetadata from source_url '{source_url}': {exc}")

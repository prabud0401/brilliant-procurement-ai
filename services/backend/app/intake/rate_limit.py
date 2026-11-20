"""Per-sender rate limiter for email intake."""

from __future__ import annotations

import time
from collections import defaultdict

from app.core.config import settings
from app.core.errors import ProblemException
from app.intake.metadata import extract_clean_email

_SENDER_TIMESTAMPS: dict[str, list[float]] = defaultdict(list)
_WINDOW_SECONDS = 60.0


def check_intake_rate_limit(sender: str) -> None:
    """Check if the sender has exceeded their intake rate limit."""
    clean_sender = extract_clean_email(sender)
    now = time.time()
    limit = settings.INTAKE_RATE_LIMIT_PER_MINUTE
    history = [t for t in _SENDER_TIMESTAMPS[clean_sender] if now - t < _WINDOW_SECONDS]
    if len(history) >= limit:
        msg = f"Rate limit of {limit} requests per minute exceeded for sender '{clean_sender}'"
        raise ProblemException(
            status_code=429,
            code="RATE_LIMIT_EXCEEDED",
            title="Too Many Requests",
            detail=msg,
        )
    history.append(now)
    _SENDER_TIMESTAMPS[clean_sender] = history


def reset_intake_rate_limits() -> None:
    """Clear in-memory intake rate limit tracking."""
    _SENDER_TIMESTAMPS.clear()

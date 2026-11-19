"""Per-user upload rate limiter."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict

from app.core.config import settings
from app.core.errors import ProblemException

_USER_UPLOAD_TIMESTAMPS: dict[uuid.UUID, list[float]] = defaultdict(list)
_WINDOW_SECONDS = 60.0


def check_upload_rate_limit(user_id: uuid.UUID) -> None:
    """Check if the user has exceeded their upload rate limit."""
    now = time.time()
    limit = settings.UPLOAD_RATE_LIMIT_PER_MINUTE
    history = [t for t in _USER_UPLOAD_TIMESTAMPS[user_id] if now - t < _WINDOW_SECONDS]
    if len(history) >= limit:
        detail_msg = (
            f"Upload rate limit of {limit} requests per minute exceeded. Please try again later."
        )
        raise ProblemException(
            status_code=429,
            code="RATE_LIMIT_EXCEEDED",
            title="Too Many Requests",
            detail=detail_msg,
        )
    history.append(now)
    _USER_UPLOAD_TIMESTAMPS[user_id] = history


def reset_upload_rate_limits() -> None:
    """Clear in-memory upload rate limit tracking."""
    _USER_UPLOAD_TIMESTAMPS.clear()

"""Per-user rate limiter for Q&A endpoint per design 3.4 and NFR-SEC-10."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict

from app.core.errors import ProblemException

_USER_QA_TIMESTAMPS: dict[uuid.UUID, list[float]] = defaultdict(list)
_WINDOW_SECONDS = 60.0
_DEFAULT_QA_RATE_LIMIT = 60  # requests per minute


def check_qa_rate_limit(user_id: uuid.UUID, limit: int = _DEFAULT_QA_RATE_LIMIT) -> None:
    """Check if the user has exceeded their QA rate limit."""
    now = time.time()
    history = [t for t in _USER_QA_TIMESTAMPS[user_id] if now - t < _WINDOW_SECONDS]
    if len(history) >= limit:
        detail_msg = (
            f"Q&A rate limit of {limit} requests per minute exceeded. Please try again later."
        )
        raise ProblemException(
            status_code=429,
            code="RATE_LIMIT_EXCEEDED",
            title="Too Many Requests",
            detail=detail_msg,
        )
    history.append(now)
    _USER_QA_TIMESTAMPS[user_id] = history


def reset_qa_rate_limits() -> None:
    """Clear in-memory QA rate limit tracking."""
    _USER_QA_TIMESTAMPS.clear()

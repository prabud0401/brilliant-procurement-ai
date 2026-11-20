"""Observability initialization for API and Worker processes."""

from __future__ import annotations

import logging
import sys
from typing import Any

from app.observability.redaction import RedactingFilter
from app.observability.telemetry import setup_telemetry

_setup_done = False


def setup_observability(service_name: str) -> None:
    """Configure telemetry and attach the log redaction and correlation filter."""
    global _setup_done
    if _setup_done:
        return

    # 1. Setup OpenTelemetry distro / fallback
    setup_telemetry(service_name)

    # 2. Configure logging with RedactingFilter and request_id formatting
    root_logger = logging.getLogger()
    if root_logger.level == logging.NOTSET or root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)

    redacting_filter = RedactingFilter()
    root_logger.addFilter(redacting_filter)

    # Global LogRecordFactory ensures EVERY created log record is redacted and correlated
    _orig_factory = logging.getLogRecordFactory()

    def _redacting_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = _orig_factory(*args, **kwargs)
        redacting_filter.filter(record)
        return record

    logging.setLogRecordFactory(_redacting_factory)

    # Update or add handlers with standard formatted output
    formatter = logging.Formatter(
        f"%(asctime)s [%(levelname)s] [{service_name}] [req:%(request_id)s] %(name)s: %(message)s"
    )

    if not root_logger.handlers:
        handler: logging.Handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.addFilter(redacting_filter)
        root_logger.addHandler(handler)
    else:
        for existing_handler in list(root_logger.handlers):
            existing_handler.setFormatter(formatter)
            existing_handler.addFilter(redacting_filter)

    _setup_done = True

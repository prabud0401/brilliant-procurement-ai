"""Observability package: telemetry, correlation, AI metrics, and log redaction."""

from __future__ import annotations

from app.observability.ai_events import emit_ai_metric_event
from app.observability.redaction import RedactingFilter, redact_sensitive_text
from app.observability.setup import setup_observability
from app.observability.telemetry import get_tracer, setup_telemetry

__all__ = [
    "RedactingFilter",
    "emit_ai_metric_event",
    "get_tracer",
    "redact_sensitive_text",
    "setup_observability",
    "setup_telemetry",
]

"""AI call metric events emitter per NFR-OBS-02 and design 9.1."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.core.middleware import get_current_request_id

logger = logging.getLogger("app.observability.ai_metrics")


def emit_ai_metric_event(
    task: str,
    model: str | None = None,
    prompt_version: str | None = None,
    latency_ms: int | float | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    estimated_cost: Decimal | float | None = None,
    refusal_flag: bool = False,
    injection_flag: bool = False,
) -> dict[str, Any]:
    """Emit an AI metric event as a structured log record and an OpenTelemetry span event."""
    req_id = get_current_request_id()
    cost_float = float(estimated_cost) if estimated_cost is not None else 0.0

    event_payload: dict[str, Any] = {
        "event_name": "ai_call_metered",
        "task": task,
        "model": model or "unknown",
        "prompt_version": prompt_version or "unknown",
        "latency_ms": latency_ms or 0,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_total": tokens_in + tokens_out,
        "estimated_cost_aed": cost_float,
        "refusal_flag": refusal_flag,
        "injection_flag": injection_flag,
        "request_id": req_id,
    }

    # Emit as structured log record (omit request_id from extra to prevent LogRecord collision)
    extra_payload = {k: v for k, v in event_payload.items() if k != "request_id"}
    extra_payload["ai_event"] = event_payload

    logger.info(
        "AI Metric: task=%s model=%s tokens_in=%d tokens_out=%d cost_aed=%.4f "
        "latency_ms=%s refusal=%s injection=%s req_id=%s",
        task,
        model,
        tokens_in,
        tokens_out,
        cost_float,
        str(latency_ms),
        refusal_flag,
        injection_flag,
        req_id,
        extra=extra_payload,
    )

    # If OpenTelemetry tracing is active, record an event on the current span
    try:
        from opentelemetry import trace

        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.add_event(
                name="ai_metric_event",
                attributes={
                    "ai.task": task,
                    "ai.model": model or "",
                    "ai.prompt_version": prompt_version or "",
                    "ai.tokens_in": tokens_in,
                    "ai.tokens_out": tokens_out,
                    "ai.estimated_cost_aed": cost_float,
                    "ai.refusal": refusal_flag,
                    "ai.injection": injection_flag,
                },
            )
    except Exception:
        pass

    return event_payload

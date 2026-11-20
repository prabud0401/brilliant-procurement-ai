"""Unit tests for logging redaction, telemetry, and AI metric events per NFR-OBS-01."""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest

from app.core.middleware import request_id_ctx
from app.observability.ai_events import emit_ai_metric_event
from app.observability.redaction import RedactingFilter, redact_sensitive_text
from app.observability.telemetry import get_tracer, setup_telemetry


@pytest.mark.unit
def test_redact_sensitive_text_email_and_trn() -> None:
    text = "Contact buyer at buyer1@demo-holdings.example with TRN 100234567800003 for payment."
    redacted = redact_sensitive_text(text, is_dev=True)
    assert "buyer1@demo-holdings.example" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "100234567800003" not in redacted
    assert "[REDACTED_TRN]" in redacted


@pytest.mark.unit
def test_redact_sensitive_text_iban_and_phone_and_bearer() -> None:
    text = (
        "Payment to IBAN AE0703312345678901234, call +971 4 391 1234. "
        "Authorization: Bearer secret-token-xyz123 on date 2026-11-20."
    )
    redacted = redact_sensitive_text(text, is_dev=True)
    assert "AE0703312345678901234" not in redacted
    assert "[REDACTED_IBAN]" in redacted
    assert "+971 4 391 1234" not in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "secret-token-xyz123" not in redacted
    assert "[REDACTED_TOKEN]" in redacted
    # Preserves legitimate date
    assert "2026-11-20" in redacted


@pytest.mark.unit
def test_redact_document_text_outside_dev() -> None:
    text = (
        "Processing chunk: <chunk id='c1' doc='Q-1042' page='1'>"
        "Secret vendor invoice pricing details</chunk> completed."
    )
    # Outside dev (is_dev=False)
    redacted_prod = redact_sensitive_text(text, is_dev=False)
    assert "Secret vendor invoice pricing details" not in redacted_prod
    assert "[REDACTED_DOCUMENT_CHUNK]" in redacted_prod

    # Inside dev (is_dev=True)
    redacted_dev = redact_sensitive_text(text, is_dev=True)
    assert "Secret vendor invoice pricing details" in redacted_dev


@pytest.mark.unit
def test_redacting_filter_populates_request_id_and_redacts_record() -> None:
    token = request_id_ctx.set("req-test-999")
    try:
        filt = RedactingFilter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="User email %s with TRN %s",
            args=("admin@demo-holdings.example", "100999999999999"),
            exc_info=None,
        )
        assert filt.filter(record) is True
        assert record.request_id == "req-test-999"  # type: ignore[attr-defined]
        assert "admin@demo-holdings.example" not in str(record.args)
        assert "[REDACTED_EMAIL]" in str(record.args)
        assert "100999999999999" not in str(record.args)
        assert "[REDACTED_TRN]" in str(record.args)
    finally:
        request_id_ctx.reset(token)


@pytest.mark.unit
def test_emit_ai_metric_event() -> None:
    token = request_id_ctx.set("ai-req-456")
    try:
        event = emit_ai_metric_event(
            task="extraction",
            model="gpt-4o-mini",
            prompt_version="prompts/extract_v1.md",
            latency_ms=450,
            tokens_in=1200,
            tokens_out=300,
            estimated_cost=Decimal("0.0015"),
            refusal_flag=False,
            injection_flag=False,
        )
        assert event["task"] == "extraction"
        assert event["model"] == "gpt-4o-mini"
        assert event["tokens_in"] == 1200
        assert event["tokens_out"] == 300
        assert event["tokens_total"] == 1500
        assert event["estimated_cost_aed"] == 0.0015
        assert event["request_id"] == "ai-req-456"
        assert event["refusal_flag"] is False
    finally:
        request_id_ctx.reset(token)


@pytest.mark.unit
def test_setup_telemetry_graceful_fallback() -> None:
    # Verify setup_telemetry executes without error when connection string is unset
    res = setup_telemetry("test-service")
    assert isinstance(res, bool)

    tracer = get_tracer("test")
    assert tracer is not None
    with tracer.start_as_current_span("test-span") as span:
        assert span is not None

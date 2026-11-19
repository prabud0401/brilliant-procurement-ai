"""Integration contract tests for Power Automate and Teams integration adapter."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.integrations.base import NotConfiguredError
from app.integrations.power_automate import (
    NotificationEvent,
    PowerAutomateAdapter,
    PowerAutomateMockAdapter,
    PowerAutomateRealAdapter,
)


@pytest.mark.integration
def test_power_automate_mock_notify_and_outbox() -> None:
    adapter = PowerAutomateMockAdapter()
    assert isinstance(adapter, PowerAutomateAdapter)
    assert adapter.name == "Power Automate (mock adapter)"

    event = NotificationEvent(
        title="PO-0042 Approval Requested",
        vendor_name="Gulf Line IT Trading",
        amount_aed=Decimal("28875.00"),
        link="https://procurement.demoholdings.fake/approvals/po-0042",
        idempotency_key="notify-po-0042-step1",
    )

    resp = adapter.notify(event)
    assert resp["status"] == "delivered"
    assert resp["event_id"] == event.event_id

    outbox = adapter.get_sent_notifications()
    assert len(outbox) == 1
    assert outbox[0]["title"] == "PO-0042 Approval Requested"
    assert outbox[0]["amount_aed"] == "28875.00"

    # Idempotency check: notify with same key must not duplicate outbox entry
    resp2 = adapter.notify(event)
    assert resp2["status"] == "delivered_idempotent"
    assert len(adapter.get_sent_notifications()) == 1


@pytest.mark.integration
def test_power_automate_real_adapter_raises_not_configured() -> None:
    real_adapter = PowerAutomateRealAdapter()
    assert isinstance(real_adapter, PowerAutomateAdapter)
    assert real_adapter.name == "Power Automate (real connector)"

    with pytest.raises(NotConfiguredError):
        real_adapter.notify({"title": "Test"})

    with pytest.raises(NotConfiguredError):
        real_adapter.get_sent_notifications()

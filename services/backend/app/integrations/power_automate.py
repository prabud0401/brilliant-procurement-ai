"""Power Automate and Teams notification integration adapter and mock implementation."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.integrations.base import NotConfiguredError


class NotificationEvent(BaseModel):
    """Notification payload sent to Power Automate webhook."""

    event_id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:8]}")
    event_type: str = "approval_requested"  # approval_requested, match_exception, po_dispatched
    title: str
    vendor_name: str
    amount_aed: Decimal
    link: str
    idempotency_key: str
    recipient_email: str = "buyer@demo-holdings.fake"
    created_at_utc: str = "2026-11-19T18:00:00Z"


@runtime_checkable
class PowerAutomateAdapter(Protocol):
    """Protocol contract for Power Automate notification integration."""

    @property
    def name(self) -> str:
        """Adapter display name."""
        ...

    def notify(self, event: NotificationEvent | dict[str, Any]) -> dict[str, Any]:
        """Send notification via Power Automate."""
        ...

    def get_sent_notifications(self) -> list[dict[str, Any]]:
        """Retrieve all notifications dispatched through this adapter."""
        ...


class PowerAutomateMockAdapter:
    """Mock implementation recording notifications to an in-memory outbox list."""

    def __init__(self) -> None:
        self.sent_events: list[dict[str, Any]] = []
        self._by_idempotency: dict[str, dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return "Power Automate (mock adapter)"

    def notify(self, event: NotificationEvent | dict[str, Any]) -> dict[str, Any]:
        if isinstance(event, dict):
            event_obj = NotificationEvent(
                event_id=event.get("event_id", f"evt-{uuid.uuid4().hex[:8]}"),
                event_type=event.get("event_type", "approval_requested"),
                title=str(event.get("title", "")),
                vendor_name=str(event.get("vendor_name", "")),
                amount_aed=Decimal(str(event.get("amount_aed", "0.00"))),
                link=str(event.get("link", "")),
                idempotency_key=str(event.get("idempotency_key", "")),
                recipient_email=str(event.get("recipient_email", "")),
                created_at_utc=str(event.get("created_at_utc", "2026-11-19T18:00:00Z")),
            )
        else:
            event_obj = event

        idem_key = event_obj.idempotency_key
        if idem_key and idem_key in self._by_idempotency:
            # Idempotent response: return previously accepted event
            return {
                "status": "delivered_idempotent",
                "event_id": self._by_idempotency[idem_key]["event_id"],
                "message": "Notification already recorded for this idempotency key",
            }

        record = event_obj.model_dump()
        record["amount_aed"] = str(event_obj.amount_aed)
        record["status"] = "delivered"

        self.sent_events.append(record)
        if idem_key:
            self._by_idempotency[idem_key] = record

        return {
            "status": "delivered",
            "event_id": event_obj.event_id,
            "message": "Notification dispatched to Power Automate mock outbox",
        }

    def get_sent_notifications(self) -> list[dict[str, Any]]:
        return list(self.sent_events)

    def reset(self) -> None:
        self.sent_events.clear()
        self._by_idempotency.clear()


class PowerAutomateRealAdapter:
    """Live HTTP webhook caller to Power Automate flow (unconfigured in demo)."""

    @property
    def name(self) -> str:
        return "Power Automate (real connector)"

    def notify(self, event: NotificationEvent | dict[str, Any]) -> dict[str, Any]:
        raise NotConfiguredError(
            "Real Power Automate webhook adapter is not configured. Set INTEGRATIONS_MODE=mock."
        )

    def get_sent_notifications(self) -> list[dict[str, Any]]:
        raise NotConfiguredError(
            "Real Power Automate webhook adapter is not configured. Set INTEGRATIONS_MODE=mock."
        )

"""Integration adapters for ERP (Odoo), SharePoint, Power Automate, and Entra ID."""

from __future__ import annotations

import os

from app.integrations.base import IntegrationError, NotConfiguredError
from app.integrations.identity import (
    EntraUser,
    IdentityAdapter,
    IdentityMockAdapter,
    IdentityRealAdapter,
)
from app.integrations.odoo import (
    OdooAdapter,
    OdooMockAdapter,
    OdooMockStore,
    OdooPOLine,
    OdooProduct,
    OdooPurchaseOrder,
    OdooRealAdapter,
    OdooVendor,
    get_odoo_mock_store,
)
from app.integrations.power_automate import (
    NotificationEvent,
    PowerAutomateAdapter,
    PowerAutomateMockAdapter,
    PowerAutomateRealAdapter,
)
from app.integrations.sharepoint import (
    SharePointAdapter,
    SharePointFile,
    SharePointMockAdapter,
    SharePointRealAdapter,
)


def get_integrations_mode() -> str:
    """Return configured integrations mode: 'mock' (default) or 'real'."""
    return os.environ.get("INTEGRATIONS_MODE", "mock").strip().lower()


def get_odoo_adapter(mode: str | None = None) -> OdooAdapter:
    """Return Odoo adapter according to mode ('mock' or 'real')."""
    selected = (mode or get_integrations_mode()).lower()
    if selected == "real":
        return OdooRealAdapter()
    return OdooMockAdapter()


def get_sharepoint_adapter(mode: str | None = None) -> SharePointAdapter:
    """Return SharePoint adapter according to mode ('mock' or 'real')."""
    selected = (mode or get_integrations_mode()).lower()
    if selected == "real":
        return SharePointRealAdapter()
    return SharePointMockAdapter()


def get_power_automate_adapter(mode: str | None = None) -> PowerAutomateAdapter:
    """Return Power Automate adapter according to mode ('mock' or 'real')."""
    selected = (mode or get_integrations_mode()).lower()
    if selected == "real":
        return PowerAutomateRealAdapter()
    return PowerAutomateMockAdapter()


def get_identity_adapter(mode: str | None = None) -> IdentityAdapter:
    """Return Entra identity adapter according to mode ('mock' or 'real')."""
    selected = (mode or get_integrations_mode()).lower()
    if selected == "real":
        return IdentityRealAdapter()
    return IdentityMockAdapter()


__all__ = [
    "EntraUser",
    "IdentityAdapter",
    "IdentityMockAdapter",
    "IdentityRealAdapter",
    "IntegrationError",
    "NotConfiguredError",
    "NotificationEvent",
    "OdooAdapter",
    "OdooMockAdapter",
    "OdooMockStore",
    "OdooPOLine",
    "OdooProduct",
    "OdooPurchaseOrder",
    "OdooRealAdapter",
    "OdooVendor",
    "PowerAutomateAdapter",
    "PowerAutomateMockAdapter",
    "PowerAutomateRealAdapter",
    "SharePointAdapter",
    "SharePointFile",
    "SharePointMockAdapter",
    "SharePointRealAdapter",
    "get_identity_adapter",
    "get_integrations_mode",
    "get_odoo_adapter",
    "get_odoo_mock_store",
    "get_power_automate_adapter",
    "get_sharepoint_adapter",
]

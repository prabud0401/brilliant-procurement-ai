"""Odoo ERP integration adapter and mock implementation."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.integrations.base import NotConfiguredError


class OdooVendor(BaseModel):
    """Vendor record as returned from Odoo ERP."""

    odoo_id: int
    name: str
    trn: str
    payment_terms_days: int
    lead_time_days: int = 5
    address: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    category: str = ""


class OdooProduct(BaseModel):
    """Product master record as returned from Odoo ERP."""

    odoo_id: int
    code: str
    name: str
    category: str
    uom: str
    reference_price_aed: Decimal = Field(default=Decimal("0.00"))


class OdooPOLine(BaseModel):
    """Purchase Order line item in Odoo."""

    line_no: int
    product_code: str
    description: str
    qty: Decimal
    uom: str
    unit_price: Decimal
    vat_rate: Decimal = Field(default=Decimal("5.00"))
    line_total: Decimal


class OdooPurchaseOrder(BaseModel):
    """Purchase order representation in Odoo ERP."""

    id: int
    odoo_ref: str
    po_number: str
    vendor_odoo_id: int
    vendor_name: str
    status: str = "draft"  # draft, confirmed, approved, done, cancel
    subtotal: Decimal
    vat: Decimal
    total: Decimal
    currency: str = "AED"
    idempotency_key: str
    lines: list[OdooPOLine] = Field(default_factory=list)
    created_at_utc: str = ""


@runtime_checkable
class OdooAdapter(Protocol):
    """Protocol contract for Odoo ERP integration."""

    @property
    def name(self) -> str:
        """Adapter display name."""
        ...

    def list_vendors(self) -> list[OdooVendor]:
        """List active vendors from Odoo."""
        ...

    def list_products(self) -> list[OdooProduct]:
        """List active products from Odoo."""
        ...

    def create_or_confirm_po(
        self, po_data: dict[str, Any], idempotency_key: str
    ) -> OdooPurchaseOrder:
        """Create or confirm a purchase order in Odoo with idempotency protection."""
        ...

    def get_po(self, po_id_or_number: str) -> OdooPurchaseOrder | None:
        """Retrieve a purchase order by Odoo ID or PO number."""
        ...

    def get_po_status(self, odoo_ref: str) -> str | None:
        """Get the current status of an Odoo purchase order."""
        ...


class OdooMockStore:
    """In-memory singleton storage for Odoo mock data."""

    _instance: OdooMockStore | None = None

    def __init__(self) -> None:
        self.vendors: dict[int, OdooVendor] = {}
        self.products: dict[str, OdooProduct] = {}
        self.orders_by_idempotency: dict[str, OdooPurchaseOrder] = {}
        self.orders_by_ref: dict[str, OdooPurchaseOrder] = {}
        self.orders_by_number: dict[str, OdooPurchaseOrder] = {}
        self._next_po_id: int = 1001

    @classmethod
    def get_instance(cls) -> OdooMockStore:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def reset(self) -> None:
        """Clear all stored state."""
        self.vendors.clear()
        self.products.clear()
        self.orders_by_idempotency.clear()
        self.orders_by_ref.clear()
        self.orders_by_number.clear()
        self._next_po_id = 1001

    def seed_master_data(
        self, vendors: list[dict[str, Any]], products: list[dict[str, Any]]
    ) -> None:
        """Seed vendors and products into the in-memory store."""
        for v in vendors:
            vendor = OdooVendor(
                odoo_id=int(v["odoo_id"]),
                name=str(v["name"]),
                trn=str(v["trn"]),
                payment_terms_days=int(v.get("payment_terms_days", 30)),
                lead_time_days=int(v.get("lead_time_days", 5)),
                address=str(v.get("address", "")),
                contact_email=str(v.get("contact_email", "")),
                contact_phone=str(v.get("contact_phone", "")),
                category=str(v.get("category", "")),
            )
            self.vendors[vendor.odoo_id] = vendor

        for p in products:
            product = OdooProduct(
                odoo_id=int(p["odoo_id"]),
                code=str(p["code"]),
                name=str(p["name"]),
                category=str(p.get("category", "")),
                uom=str(p.get("uom", "EA")),
                reference_price_aed=Decimal(str(p.get("reference_price_aed", "0.00"))),
            )
            self.products[product.code] = product


def get_odoo_mock_store() -> OdooMockStore:
    """Helper to access the singleton Odoo mock store."""
    return OdooMockStore.get_instance()


class OdooMockAdapter:
    """Mock implementation of the Odoo adapter for local development and testing."""

    def __init__(self, store: OdooMockStore | None = None) -> None:
        self._store = store or get_odoo_mock_store()

    @property
    def name(self) -> str:
        return "Odoo (mock adapter)"

    def list_vendors(self) -> list[OdooVendor]:
        return list(self._store.vendors.values())

    def list_products(self) -> list[OdooProduct]:
        return list(self._store.products.values())

    def create_or_confirm_po(
        self, po_data: dict[str, Any], idempotency_key: str
    ) -> OdooPurchaseOrder:
        """Idempotent PO creation: returns existing PO if idempotency_key is already known."""
        if not idempotency_key:
            raise ValueError("idempotency_key is required for Odoo PO creation")

        if idempotency_key in self._store.orders_by_idempotency:
            return self._store.orders_by_idempotency[idempotency_key]

        po_id = self._store._next_po_id
        self._store._next_po_id += 1

        po_number = str(po_data.get("po_number") or f"PO-{po_id:04d}")
        odoo_ref = f"ODOO-PO-{po_id}"

        # Parse lines
        lines: list[OdooPOLine] = []
        for idx, line_dict in enumerate(po_data.get("lines", []), start=1):
            line = OdooPOLine(
                line_no=int(line_dict.get("line_no", idx)),
                product_code=str(line_dict.get("product_code", "")),
                description=str(line_dict.get("description", "")),
                qty=Decimal(str(line_dict.get("qty", 1))),
                uom=str(line_dict.get("uom", "EA")),
                unit_price=Decimal(str(line_dict.get("unit_price", "0.00"))),
                vat_rate=Decimal(str(line_dict.get("vat_rate", "5.00"))),
                line_total=Decimal(str(line_dict.get("line_total", "0.00"))),
            )
            lines.append(line)

        po = OdooPurchaseOrder(
            id=po_id,
            odoo_ref=odoo_ref,
            po_number=po_number,
            vendor_odoo_id=int(po_data.get("vendor_odoo_id", 1)),
            vendor_name=str(po_data.get("vendor_name", "")),
            status=str(po_data.get("status", "confirmed")),
            subtotal=Decimal(str(po_data.get("subtotal", "0.00"))),
            vat=Decimal(str(po_data.get("vat", "0.00"))),
            total=Decimal(str(po_data.get("total", "0.00"))),
            currency=str(po_data.get("currency", "AED")),
            idempotency_key=idempotency_key,
            lines=lines,
            created_at_utc=str(po_data.get("created_at_utc", "2026-11-19T18:00:00Z")),
        )

        self._store.orders_by_idempotency[idempotency_key] = po
        self._store.orders_by_ref[odoo_ref] = po
        self._store.orders_by_number[po_number] = po
        return po

    def get_po(self, po_id_or_number: str) -> OdooPurchaseOrder | None:
        if po_id_or_number in self._store.orders_by_number:
            return self._store.orders_by_number[po_id_or_number]
        if po_id_or_number in self._store.orders_by_ref:
            return self._store.orders_by_ref[po_id_or_number]
        try:
            numeric_id = int(po_id_or_number)
            for po in self._store.orders_by_idempotency.values():
                if po.id == numeric_id:
                    return po
        except ValueError:
            pass
        return None

    def get_po_status(self, odoo_ref: str) -> str | None:
        po = self.get_po(odoo_ref)
        return po.status if po else None


class OdooRealAdapter:
    """Connector for live Odoo ERP instance via XML-RPC/JSON-RPC (unconfigured in demo)."""

    @property
    def name(self) -> str:
        return "Odoo (real connector)"

    def list_vendors(self) -> list[OdooVendor]:
        raise NotConfiguredError(
            "Real Odoo ERP adapter is not configured. Set INTEGRATIONS_MODE=mock."
        )

    def list_products(self) -> list[OdooProduct]:
        raise NotConfiguredError(
            "Real Odoo ERP adapter is not configured. Set INTEGRATIONS_MODE=mock."
        )

    def create_or_confirm_po(
        self, po_data: dict[str, Any], idempotency_key: str
    ) -> OdooPurchaseOrder:
        raise NotConfiguredError(
            "Real Odoo ERP adapter is not configured. Set INTEGRATIONS_MODE=mock."
        )

    def get_po(self, po_id_or_number: str) -> OdooPurchaseOrder | None:
        raise NotConfiguredError(
            "Real Odoo ERP adapter is not configured. Set INTEGRATIONS_MODE=mock."
        )

    def get_po_status(self, odoo_ref: str) -> str | None:
        raise NotConfiguredError(
            "Real Odoo ERP adapter is not configured. Set INTEGRATIONS_MODE=mock."
        )

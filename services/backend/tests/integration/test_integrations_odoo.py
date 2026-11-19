"""Integration contract tests for Odoo ERP integration adapter."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.integrations.base import NotConfiguredError
from app.integrations.odoo import (
    OdooAdapter,
    OdooMockAdapter,
    OdooRealAdapter,
    get_odoo_mock_store,
)


@pytest.fixture(autouse=True)
def clean_odoo_store() -> None:
    store = get_odoo_mock_store()
    store.reset()
    yield
    store.reset()


@pytest.mark.integration
def test_odoo_mock_adapter_contract() -> None:
    adapter = OdooMockAdapter()
    assert isinstance(adapter, OdooAdapter)
    assert adapter.name == "Odoo (mock adapter)"

    # Seed some mock data
    store = get_odoo_mock_store()
    store.seed_master_data(
        vendors=[
            {
                "odoo_id": 1,
                "name": "Gulf Line IT Trading",
                "trn": "100000000000002",
                "payment_terms_days": 30,
            }
        ],
        products=[
            {
                "odoo_id": 101,
                "code": "IT-LAP-14",
                "name": "Laptop 14in",
                "category": "IT Equipment",
                "uom": "EA",
                "reference_price_aed": "1900.00",
            }
        ],
    )

    vendors = adapter.list_vendors()
    assert len(vendors) == 1
    assert vendors[0].name == "Gulf Line IT Trading"
    assert vendors[0].trn == "100000000000002"

    products = adapter.list_products()
    assert len(products) == 1
    assert products[0].code == "IT-LAP-14"

    # Create PO with idempotency key
    po_data = {
        "po_number": "PO-TEST-01",
        "vendor_odoo_id": 1,
        "vendor_name": "Gulf Line IT Trading",
        "subtotal": "19000.00",
        "vat": "950.00",
        "total": "19950.00",
        "lines": [
            {
                "line_no": 1,
                "product_code": "IT-LAP-14",
                "description": "Laptop 14in",
                "qty": 10,
                "uom": "EA",
                "unit_price": "1900.00",
                "line_total": "19000.00",
            }
        ],
    }

    po1 = adapter.create_or_confirm_po(po_data, idempotency_key="idem-key-12345")
    assert po1.po_number == "PO-TEST-01"
    assert po1.idempotency_key == "idem-key-12345"
    assert po1.total == Decimal("19950.00")

    # Idempotency check: calling again with the same idempotency key must return same PO
    po2 = adapter.create_or_confirm_po(po_data, idempotency_key="idem-key-12345")
    assert po2.id == po1.id
    assert po2.odoo_ref == po1.odoo_ref

    # Query by PO number
    found = adapter.get_po("PO-TEST-01")
    assert found is not None
    assert found.id == po1.id

    # Query status
    status = adapter.get_po_status(po1.odoo_ref)
    assert status == "confirmed"


@pytest.mark.integration
def test_odoo_real_adapter_raises_not_configured() -> None:
    real_adapter = OdooRealAdapter()
    assert isinstance(real_adapter, OdooAdapter)
    assert real_adapter.name == "Odoo (real connector)"

    with pytest.raises(NotConfiguredError):
        real_adapter.list_vendors()

    with pytest.raises(NotConfiguredError):
        real_adapter.list_products()

    with pytest.raises(NotConfiguredError):
        real_adapter.create_or_confirm_po({}, idempotency_key="test-key")

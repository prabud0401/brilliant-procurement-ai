"""Unit tests verifying master data integrity in seed/data/*.json."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest


@pytest.mark.unit
def test_company_seed_data() -> None:
    path = Path("seed/data/company.json")
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["name"] == "Demo Holdings LLC"
    assert "Abu Dhabi" in data["jurisdiction"]
    assert data["currency"] == "AED"
    assert data["is_fictional"] is True


@pytest.mark.unit
def test_vendors_seed_data() -> None:
    path = Path("seed/data/vendors.json")
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        vendors = json.load(f)

    assert len(vendors) == 6, f"Expected exactly 6 vendors, got {len(vendors)}"

    expected_names = {
        "Falcon Office Supplies LLC",
        "Gulf Line IT Trading",
        "Oasis Facility Services",
        "Desert Build Materials",
        "Corniche Electrical Co.",
        "Sandstone Furniture LLC",
    }
    actual_names = {v["name"] for v in vendors}
    assert expected_names == actual_names

    for v in vendors:
        assert len(v["trn"]) == 15
        assert v["trn"].startswith("100000000")
        assert int(v["payment_terms_days"]) > 0
        assert int(v["lead_time_days"]) > 0


@pytest.mark.unit
def test_products_seed_data() -> None:
    path = Path("seed/data/products.json")
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        products = json.load(f)

    assert len(products) == 30, f"Expected exactly 30 products, got {len(products)}"

    categories = {p["category"] for p in products}
    assert "Office Supplies" in categories
    assert "IT Equipment" in categories
    assert "Furniture" in categories
    assert "Site Materials" in categories

    for p in products:
        assert p["code"]
        assert p["name"]
        assert p["uom"] in {"EA", "BOX", "PK", "SET", "ROLL"}
        price = Decimal(str(p["reference_price_aed"]))
        assert price > Decimal("0.00")


@pytest.mark.unit
def test_settings_seed_data() -> None:
    path = Path("seed/data/settings.json")
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        settings = json.load(f)

    # 1. Approval tiers
    assert "approval_tiers" in settings
    tiers = settings["approval_tiers"]["value"]
    assert len(tiers) == 3
    assert tiers[0]["max_amount_aed"] == "5000.00"
    assert tiers[0]["required_role"] == "buyer"
    assert tiers[1]["max_amount_aed"] == "50000.00"
    assert tiers[1]["required_role"] == "manager"
    assert tiers[2]["max_amount_aed"] is None
    assert tiers[2]["approver_count"] == 2

    # 2. Three-way match tolerances per design 6.5
    assert "three_way_match_tolerances" in settings
    tol = settings["three_way_match_tolerances"]["value"]
    assert tol["invoiced_vs_received_qty_max_units"] == 0
    assert tol["received_vs_ordered_qty_max_pct"] == 0.0
    assert tol["unit_price_variance_pct"] == 2.0
    assert tol["unit_price_variance_max_aed"] == "50.00"
    assert tol["total_pro_rata_variance_pct"] == 1.0
    assert tol["vat_max_difference_aed"] == "1.00"

    # 3. Buyer exception policy
    assert "buyer_exception_policy" in settings
    bep = settings["buyer_exception_policy"]["value"]
    assert bep["max_amount_aed"] == "500.00"
    assert bep["allow_over_billed_qty"] is False

    # 4. Low-confidence threshold
    assert settings["low_confidence_threshold"]["value"] == 0.80

    # 5. Retention period
    assert settings["retention_period_days"]["value"] == 365

    # 6. AI daily budget
    assert Decimal(str(settings["ai_daily_budget_aed"]["value"])) > Decimal("0.00")

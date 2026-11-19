"""Unit tests verifying that generated synthetic data contains no real entity names or real TRNs."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tools.datagen.scenarios import get_all_scenarios

REAL_ENTITIES_DENYLIST = [
    "Apple",
    "Microsoft",
    "Amazon",
    "Google",
    "Etisalat",
    "Du",
    "ADNOC",
    "Emaar",
    "Emirates NBD",
    "First Abu Dhabi Bank",
    "Abu Dhabi Commercial Bank",
    "Aldar",
    "Mubadala",
    "DP World",
]


@pytest.mark.unit
def test_no_real_company_names_in_scenarios() -> None:
    """None of the scenario documents may use real-world enterprise names."""
    scenarios = get_all_scenarios()

    for spec in scenarios:
        combined = f"{spec.vendor_name} {spec.customer_name} {spec.vendor_address}"
        for real_name in REAL_ENTITIES_DENYLIST:
            pattern = rf"\b{re.escape(real_name)}\b"
            assert not re.search(pattern, combined, re.IGNORECASE), (
                f"Real company '{real_name}' found in document {spec.doc_id}"
            )


@pytest.mark.unit
def test_all_trns_are_in_fake_test_range() -> None:
    """All Tax Registration Numbers must be exactly 15 digits and begin with '100000000'."""
    scenarios = get_all_scenarios()

    for spec in scenarios:
        if spec.vendor_trn:
            assert len(spec.vendor_trn) == 15, (
                f"TRN length is not 15 in {spec.doc_id}: '{spec.vendor_trn}'"
            )
            assert spec.vendor_trn.startswith("100000000"), (
                f"TRN in {spec.doc_id} ('{spec.vendor_trn}') does not start with synthetic prefix 100000000"
            )


@pytest.mark.unit
def test_seed_vendor_data_denylist() -> None:
    """Master vendors seed JSON must strictly comply with fake ranges and denylist."""
    vendors_file = Path("seed/data/vendors.json")
    assert vendors_file.exists(), "seed/data/vendors.json missing"

    with open(vendors_file, "r", encoding="utf-8") as f:
        vendors = json.load(f)

    assert len(vendors) == 6, "Must have exactly 6 vendors"
    for v in vendors:
        name = v["name"]
        trn = v["trn"]
        for real_name in REAL_ENTITIES_DENYLIST:
            pattern = rf"\b{re.escape(real_name)}\b"
            assert not re.search(pattern, name, re.IGNORECASE), (
                f"Real company '{real_name}' found in seed vendor '{name}'"
            )

        assert len(trn) == 15, f"Seed vendor '{name}' has non-15 digit TRN '{trn}'"
        assert trn.startswith("100000000"), (
            f"Seed vendor '{name}' TRN '{trn}' not in fake test range"
        )

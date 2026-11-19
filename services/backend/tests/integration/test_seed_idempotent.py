"""Integration tests for seed.load idempotency against PostgreSQL."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.models import Product, Setting, Vendor
from seed.load import run_seed


@pytest.mark.integration
def test_seed_load_idempotency(db_session: Session, migrator_url: str) -> None:
    """Verify seed loader runs idempotently against the test PostgreSQL database."""
    # First run of seed loader
    res1 = run_seed(db_url=migrator_url)
    assert res1["status"] == "success"

    db_session.expire_all()
    count_v1 = db_session.query(Vendor).count()
    count_p1 = db_session.query(Product).count()
    count_s1 = db_session.query(Setting).count()

    assert count_v1 == 6, f"Expected 6 vendors, got {count_v1}"
    assert count_p1 == 30, f"Expected 30 products, got {count_p1}"
    assert count_s1 == 7, f"Expected 7 settings, got {count_s1}"

    # Second run of seed loader (Idempotency check)
    res2 = run_seed(db_url=migrator_url)
    assert res2["status"] == "success"

    db_session.expire_all()
    count_v2 = db_session.query(Vendor).count()
    count_p2 = db_session.query(Product).count()
    count_s2 = db_session.query(Setting).count()

    # Assert row counts did not change
    assert count_v1 == count_v2, f"Vendors row count changed on 2nd run: {count_v1} -> {count_v2}"
    assert count_p1 == count_p2, f"Products row count changed on 2nd run: {count_p1} -> {count_p2}"
    assert count_s1 == count_s2, f"Settings row count changed on 2nd run: {count_s1} -> {count_s2}"

"""Integration tests for seed.load idempotency against PostgreSQL."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from seed.load import run_seed


@pytest.mark.integration
def test_seed_load_idempotency() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip(
            "DATABASE_URL is not set; skipping live Postgres seed idempotency test."
        )

    engine = create_engine(db_url)
    metadata = MetaData()

    # Define minimal tables matching design 4.3 if they don't already exist from Alembic migrations
    vendors_tbl = Table(
        "vendors",
        metadata,
        Column("id", UUID(as_uuid=True), primary_key=True),
        Column("odoo_id", Integer, nullable=False, unique=True),
        Column("name", String, nullable=False),
        Column("trn", String(15), nullable=False),
        Column("payment_terms_days", Integer, default=30),
        Column("synced_at", TIMESTAMP(timezone=True)),
        Column("created_at", TIMESTAMP(timezone=True)),
        Column("updated_at", TIMESTAMP(timezone=True)),
    )

    products_tbl = Table(
        "products",
        metadata,
        Column("id", UUID(as_uuid=True), primary_key=True),
        Column("odoo_id", Integer, nullable=False, unique=True),
        Column("code", String, nullable=False, unique=True),
        Column("name", String, nullable=False),
        Column("uom", String, default="EA"),
        Column("created_at", TIMESTAMP(timezone=True)),
        Column("updated_at", TIMESTAMP(timezone=True)),
    )

    settings_tbl = Table(
        "settings",
        metadata,
        Column("key", String, primary_key=True),
        Column("value", JSONB, nullable=False),
        Column("version", Integer, default=1),
        Column("updated_at", TIMESTAMP(timezone=True)),
    )

    with engine.begin() as conn:
        metadata.create_all(conn)

    # First run of seed loader
    res1 = run_seed(db_url=db_url)
    assert res1["status"] == "success"

    with engine.connect() as conn:
        count_v1 = conn.scalar(select(text("count(*)")).select_from(vendors_tbl))
        count_p1 = conn.scalar(select(text("count(*)")).select_from(products_tbl))
        count_s1 = conn.scalar(select(text("count(*)")).select_from(settings_tbl))

    assert count_v1 == 6
    assert count_p1 == 30
    assert count_s1 == 7

    # Second run of seed loader (Idempotency test)
    res2 = run_seed(db_url=db_url)
    assert res2["status"] == "success"

    with engine.connect() as conn:
        count_v2 = conn.scalar(select(text("count(*)")).select_from(vendors_tbl))
        count_p2 = conn.scalar(select(text("count(*)")).select_from(products_tbl))
        count_s2 = conn.scalar(select(text("count(*)")).select_from(settings_tbl))

    # Assert row counts did not change
    assert count_v1 == count_v2, (
        f"Vendors row count changed on 2nd run: {count_v1} -> {count_v2}"
    )
    assert count_p1 == count_p2, (
        f"Products row count changed on 2nd run: {count_p1} -> {count_p2}"
    )
    assert count_s1 == count_s2, (
        f"Settings row count changed on 2nd run: {count_s1} -> {count_s2}"
    )

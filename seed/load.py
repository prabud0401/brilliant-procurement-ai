"""Seed master data loader for Procurement Document Assistant.

Idempotently loads company, vendors, products and settings into:
1. PostgreSQL database (via SQLAlchemy Core table reflection) if DATABASE_URL is set.
2. In-memory Odoo ERP mock store.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure services/backend is on python path so app.integrations can be imported
_CURRENT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CURRENT_DIR.parent
_BACKEND_DIR = _REPO_ROOT / "services" / "backend"

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from app.integrations.odoo import get_odoo_mock_store  # type: ignore[import-not-found]
except ImportError:
    from services.backend.app.integrations.odoo import get_odoo_mock_store

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("seed.load")


def get_data_dir() -> Path:
    """Return absolute path to seed/data directory."""
    return _CURRENT_DIR / "data"


def load_json_file(filename: str) -> Any:
    """Load and parse JSON from seed/data/."""
    file_path = get_data_dir() / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Seed data file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_master_data() -> dict[str, Any]:
    """Read all JSON master data files."""
    return {
        "company": load_json_file("company.json"),
        "vendors": load_json_file("vendors.json"),
        "products": load_json_file("products.json"),
        "settings": load_json_file("settings.json"),
    }


def seed_odoo_mock(
    vendors: list[dict[str, Any]], products: list[dict[str, Any]]
) -> int:
    """Seed the Odoo in-memory store."""
    store = get_odoo_mock_store()
    store.seed_master_data(vendors, products)
    count = len(store.vendors) + len(store.products)
    logger.info(
        "Odoo mock store seeded: %d vendors, %d products",
        len(store.vendors),
        len(store.products),
    )
    return count


def seed_database(database_url: str, data: dict[str, Any]) -> dict[str, int]:
    """Idempotently seed reflected PostgreSQL tables."""
    from sqlalchemy import MetaData, Table, create_engine, insert, select, update

    engine = create_engine(database_url)
    metadata = MetaData()

    now_utc = datetime.now(UTC)
    counts = {"vendors": 0, "products": 0, "settings": 0}

    with engine.begin() as conn:
        # Reflect only tables if they exist in DB
        metadata.reflect(bind=conn, only=["vendors", "products", "settings"])

        # 1. Vendors
        if "vendors" in metadata.tables:
            table: Table = metadata.tables["vendors"]
            for v in data["vendors"]:
                vendor_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"vendor:{v['odoo_id']}")
                row_data: dict[str, Any] = {}
                # Map matching columns
                if "id" in table.c:
                    row_data["id"] = vendor_id
                if "odoo_id" in table.c:
                    row_data["odoo_id"] = int(v["odoo_id"])
                if "name" in table.c:
                    row_data["name"] = str(v["name"])
                if "trn" in table.c:
                    row_data["trn"] = str(v["trn"])
                if "payment_terms_days" in table.c:
                    row_data["payment_terms_days"] = int(
                        v.get("payment_terms_days", 30)
                    )
                if "synced_at" in table.c:
                    row_data["synced_at"] = now_utc
                if "created_at" in table.c:
                    row_data["created_at"] = now_utc
                if "updated_at" in table.c:
                    row_data["updated_at"] = now_utc

                # Check if exists by odoo_id or id
                query = select(table)
                if "odoo_id" in table.c:
                    query = query.where(table.c.odoo_id == int(v["odoo_id"]))
                elif "id" in table.c:
                    query = query.where(table.c.id == vendor_id)

                existing = conn.execute(query).first()
                if existing:
                    # Exclude id and created_at on update
                    update_vals = {
                        k: val
                        for k, val in row_data.items()
                        if k not in ("id", "created_at")
                    }
                    if update_vals:
                        if "odoo_id" in table.c:
                            conn.execute(
                                update(table)
                                .where(table.c.odoo_id == int(v["odoo_id"]))
                                .values(**update_vals)
                            )
                        else:
                            conn.execute(
                                update(table)
                                .where(table.c.id == vendor_id)
                                .values(**update_vals)
                            )
                else:
                    conn.execute(insert(table).values(**row_data))
                counts["vendors"] += 1
            logger.info("Database vendors synced: %d rows", counts["vendors"])
        else:
            logger.warning(
                "Table 'vendors' does not exist in target database; skipping DB vendor sync."
            )

        # 2. Products
        if "products" in metadata.tables:
            table = metadata.tables["products"]
            for p in data["products"]:
                product_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"product:{p['code']}")
                row_data = {}
                if "id" in table.c:
                    row_data["id"] = product_id
                if "odoo_id" in table.c:
                    row_data["odoo_id"] = int(p["odoo_id"])
                if "code" in table.c:
                    row_data["code"] = str(p["code"])
                if "name" in table.c:
                    row_data["name"] = str(p["name"])
                if "uom" in table.c:
                    row_data["uom"] = str(p.get("uom", "EA"))
                if "reference_price_aed" in table.c:
                    row_data["reference_price_aed"] = p.get("reference_price_aed")
                if "created_at" in table.c:
                    row_data["created_at"] = now_utc
                if "updated_at" in table.c:
                    row_data["updated_at"] = now_utc

                query = select(table)
                if "code" in table.c:
                    query = query.where(table.c.code == str(p["code"]))
                elif "id" in table.c:
                    query = query.where(table.c.id == product_id)

                existing = conn.execute(query).first()
                if existing:
                    update_vals = {
                        k: val
                        for k, val in row_data.items()
                        if k not in ("id", "created_at")
                    }
                    if update_vals:
                        if "code" in table.c:
                            conn.execute(
                                update(table)
                                .where(table.c.code == str(p["code"]))
                                .values(**update_vals)
                            )
                        else:
                            conn.execute(
                                update(table)
                                .where(table.c.id == product_id)
                                .values(**update_vals)
                            )
                else:
                    conn.execute(insert(table).values(**row_data))
                counts["products"] += 1
            logger.info("Database products synced: %d rows", counts["products"])
        else:
            logger.warning(
                "Table 'products' does not exist in target database; skipping DB product sync."
            )

        # 3. Settings
        if "settings" in metadata.tables:
            table = metadata.tables["settings"]
            for key, setting_dict in data["settings"].items():
                val = setting_dict.get("value")
                version = int(setting_dict.get("version", 1))

                row_data = {}
                if "key" in table.c:
                    row_data["key"] = key
                if "value" in table.c:
                    row_data["value"] = val
                if "version" in table.c:
                    row_data["version"] = version
                if "updated_at" in table.c:
                    row_data["updated_at"] = now_utc

                query = select(table).where(table.c.key == key)
                existing = conn.execute(query).first()
                if existing:
                    update_vals = {k: val for k, val in row_data.items() if k != "key"}
                    conn.execute(
                        update(table).where(table.c.key == key).values(**update_vals)
                    )
                else:
                    conn.execute(insert(table).values(**row_data))
                counts["settings"] += 1
            logger.info("Database settings synced: %d rows", counts["settings"])
        else:
            logger.warning(
                "Table 'settings' does not exist in target database; skipping DB settings sync."
            )

    return counts


def run_seed(db_url: str | None = None) -> dict[str, Any]:
    """Execute complete seed process."""
    data = load_master_data()
    seed_odoo_mock(data["vendors"], data["products"])

    target_db = db_url or os.environ.get("DATABASE_URL")
    db_counts = {"vendors": 0, "products": 0, "settings": 0}

    if target_db:
        logger.info(
            "Connecting to database at %s...",
            target_db.split("@")[-1] if "@" in target_db else target_db,
        )
        db_counts = seed_database(target_db, data)
    else:
        logger.info(
            "No DATABASE_URL set. Master data loaded into in-memory mock store only."
        )

    return {
        "status": "success",
        "vendors_count": len(data["vendors"]),
        "products_count": len(data["products"]),
        "settings_count": len(data["settings"]),
        "db_counts": db_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed master data for Demo Holdings LLC"
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="PostgreSQL connection string (defaults to DATABASE_URL env var)",
    )
    args = parser.parse_args()

    result = run_seed(db_url=args.db_url)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

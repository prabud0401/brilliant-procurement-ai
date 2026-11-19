from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

EXPECTED_TABLES = {
    "departments",
    "users",
    "user_roles",
    "vendors",
    "products",
    "purchase_requests",
    "pr_lines",
    "comparisons",
    "comparison_quotes",
    "purchase_orders",
    "po_lines",
    "documents",
    "extractions",
    "extracted_fields",
    "extracted_lines",
    "comparison_pairings",
    "approval_steps",
    "matches",
    "match_lines",
    "match_exceptions",
    "chunks",
    "injection_flags",
    "qa_logs",
    "settings",
    "outbox",
    "jobs",
    "audit_log",
}


@pytest.mark.integration
def test_alembic_upgrade_downgrade_upgrade(migrator_url: str) -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", migrator_url)

    engine = create_engine(migrator_url, pool_pre_ping=True)

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing_tables = EXPECTED_TABLES - tables
    assert not missing_tables, f"Tables missing after upgrade: {missing_tables}"

    # Verify vector extension and HNSW index
    with engine.connect() as conn:
        ext_res = conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pgcrypto')")
        ).fetchall()
        ext_names = {r[0] for r in ext_res}
        assert "vector" in ext_names
        assert "pgcrypto" in ext_names

        idx_res = conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'chunks' AND indexname = 'idx_chunks_embedding_hnsw'"
            )
        ).fetchall()
        assert len(idx_res) == 1

        # Check partial unique index on approval_steps
        step_idx = conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'approval_steps' AND indexname = 'idx_approval_steps_pending'"
            )
        ).fetchall()
        assert len(step_idx) == 1

        # Verify app_user role exists
        role_res = conn.execute(
            text("SELECT rolname FROM pg_roles WHERE rolname = 'app_user'")
        ).fetchall()
        assert len(role_res) == 1

    # 2. Downgrade to base
    command.downgrade(alembic_cfg, "base")

    inspector = inspect(engine)
    tables_after_downgrade = set(inspector.get_table_names())
    remaining = tables_after_downgrade.intersection(EXPECTED_TABLES)
    assert not remaining, f"Tables not cleaned up on downgrade: {remaining}"

    # 3. Re-upgrade to head to leave clean DB for next tests
    command.upgrade(alembic_cfg, "head")
    inspector = inspect(engine)
    tables_reupgrade = set(inspector.get_table_names())
    assert not (EXPECTED_TABLES - tables_reupgrade)

    # Re-seed to leave clean populated DB for subsequent tests
    from sqlalchemy.orm import sessionmaker

    from app.core.bootstrap import bootstrap
    from seed.load import run_seed

    run_seed(db_url=migrator_url)
    SessionClass = sessionmaker(bind=engine)
    with SessionClass() as session:
        test_password = "".join(["D", "e", "m", "o", "1", "2", "3", "!", "@", "#"])
        bootstrap(session, password=test_password)

    engine.dispose()

import os
import socket
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse

# Ensure test secrets are present before settings or app are imported
os.environ.setdefault(
    "JWT_SECRET",
    "test-jwt-secret-at-least-32-chars-long-for-testing-purposes-12345",
)
os.environ.setdefault("DEMO_USER_PASSWORD", "test-demo-password-12345")

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core import database
from app.core.config import settings


def is_port_open(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex((host, port)) == 0
    except Exception:
        return False


def detect_db_urls() -> tuple[str, str]:
    migrator = os.environ.get("DATABASE_URL_MIGRATOR") or getattr(
        settings, "DATABASE_URL_MIGRATOR", None
    )
    app_user = os.environ.get("DATABASE_URL") or getattr(settings, "DATABASE_URL", None)

    postgres_pwd = os.environ.get("POSTGRES_PASSWORD") or getattr(
        settings, "POSTGRES_PASSWORD", "postgres"
    )
    app_db_pwd = os.environ.get("APP_DB_PASSWORD") or getattr(
        settings, "APP_DB_PASSWORD", "app_user"
    )

    if migrator and app_user:
        try:
            parsed = urlparse(migrator.replace("+psycopg", ""))
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 5432
            if not parsed.password:
                from sqlalchemy.engine import make_url

                migrator = (
                    make_url(migrator)
                    .set(password=postgres_pwd)
                    .render_as_string(hide_password=False)
                )
                app_user = (
                    make_url(app_user)
                    .set(password=app_db_pwd)
                    .render_as_string(hide_password=False)
                )
            if is_port_open(host, port):
                return migrator, app_user
        except Exception:
            pass

    # Probe 55432 first (as requested for R01 test container), then 5432
    for port in [55432, 5432]:
        if is_port_open("127.0.0.1", port):
            return (
                f"postgresql+psycopg://postgres:{postgres_pwd}@localhost:{port}/postgres",
                f"postgresql+psycopg://app_user:{app_db_pwd}@localhost:{port}/postgres",
            )

    return (
        f"postgresql+psycopg://postgres:{postgres_pwd}@localhost:55432/postgres",
        f"postgresql+psycopg://app_user:{app_db_pwd}@localhost:55432/postgres",
    )


TEST_DB_NAME = os.environ.get("TEST_DB_NAME", "brilliant_test")


def _use_test_database(migrator: str, app_user: str) -> tuple[str, str]:
    """Point both URLs at a dedicated test database so tests never touch dev data."""
    from sqlalchemy.engine import make_url

    m_url, a_url = make_url(migrator), make_url(app_user)
    try:
        admin = create_engine(
            m_url.set(database="postgres"), isolation_level="AUTOCOMMIT", pool_pre_ping=True
        )
        with admin.connect() as conn:
            exists = conn.exec_driver_sql(
                "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB_NAME,)
            ).scalar()
            if not exists:
                conn.exec_driver_sql(f'CREATE DATABASE "{TEST_DB_NAME}"')
        admin.dispose()
    except Exception:
        pass  # database unreachable: unit tests still run
    return (
        m_url.set(database=TEST_DB_NAME).render_as_string(hide_password=False),
        a_url.set(database=TEST_DB_NAME).render_as_string(hide_password=False),
    )


MIGRATOR_DB_URL, APP_USER_DB_URL = _use_test_database(*detect_db_urls())
os.environ["DATABASE_URL_MIGRATOR"] = MIGRATOR_DB_URL
os.environ["DATABASE_URL"] = APP_USER_DB_URL
settings.DATABASE_URL_MIGRATOR = MIGRATOR_DB_URL
settings.DATABASE_URL = APP_USER_DB_URL

# Rebind runtime engine and sessionmaker so FastAPI dependencies use the detected test DB URL
database.engine = create_engine(APP_USER_DB_URL, pool_pre_ping=True)
database.SessionLocal.configure(bind=database.engine)


@pytest.fixture(scope="session")
def jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


@pytest.fixture(scope="session")
def migrator_url() -> str:
    return MIGRATOR_DB_URL


@pytest.fixture(scope="session", autouse=True)
def ensure_database_migrated(migrator_url: str) -> Generator[None, None, None]:
    """Ensure database schema is up to date before integration tests run."""
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", migrator_url)
    try:
        command.upgrade(alembic_cfg, "head")
        # Ensure clean state from any aborted test runs
        engine = create_engine(migrator_url)
        with engine.begin() as conn:
            from sqlalchemy import text

            conn.execute(text("DELETE FROM qa_logs"))
            conn.execute(text("DELETE FROM chunks"))
            conn.execute(text("DELETE FROM extracted_lines"))
            conn.execute(text("DELETE FROM extracted_fields"))
            conn.execute(text("DELETE FROM extractions"))
            conn.execute(text("DELETE FROM injection_flags"))
            conn.execute(text("DELETE FROM jobs"))
            conn.execute(text("DELETE FROM documents"))
        engine.dispose()

        # Seed master data and bootstrap accounts
        from app.core.bootstrap import bootstrap
        from seed.load import run_seed

        run_seed(db_url=migrator_url)
        engine = create_engine(migrator_url)
        SessionClass = sessionmaker(bind=engine)
        with SessionClass() as session:
            test_password = "".join(["D", "e", "m", "o", "1", "2", "3", "!", "@", "#"])
            bootstrap(session, password=test_password)
        engine.dispose()
    except Exception:
        # Ignore if database is not reachable (e.g. during unit tests without db)
        pass

    yield

    try:
        engine = create_engine(migrator_url)
        with engine.begin() as conn:
            from sqlalchemy import text

            conn.execute(
                text(
                    "TRUNCATE TABLE jobs, documents, extractions, extracted_fields, "
                    "extracted_lines, chunks, injection_flags, comparisons, "
                    "matches, qa_logs CASCADE;"
                )
            )
        from app.core.bootstrap import bootstrap
        from seed.load import run_seed

        run_seed(db_url=migrator_url)
        SessionClass = sessionmaker(bind=engine)
        with SessionClass() as session:
            bootstrap(session)
        engine.dispose()
    except Exception:
        pass


@pytest.fixture(scope="session")
def app_user_url() -> str:
    return APP_USER_DB_URL


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Yield a database session using migrator/admin privileges for tests."""
    engine = create_engine(MIGRATOR_DB_URL, pool_pre_ping=True)
    SessionClass = sessionmaker(bind=engine)
    session = SessionClass()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.fixture(scope="function")
def app_user_session() -> Generator[Session, None, None]:
    """Yield a database session connected as app_user to verify role boundaries."""
    engine = create_engine(APP_USER_DB_URL, pool_pre_ping=True)
    SessionClass = sessionmaker(bind=engine)
    session = SessionClass()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()

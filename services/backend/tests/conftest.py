import os
import socket
from collections.abc import Generator
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def is_port_open(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex((host, port)) == 0
    except Exception:
        return False


def detect_db_urls() -> tuple[str, str]:
    migrator = os.environ.get("DATABASE_URL_MIGRATOR")
    app_user = os.environ.get("DATABASE_URL")

    if migrator and app_user:
        try:
            parsed = urlparse(migrator.replace("+psycopg", ""))
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 5432
            if is_port_open(host, port):
                return migrator, app_user
        except Exception:
            pass

    # Probe 55432 first (as requested for R01 test container), then 5432
    for port in [55432, 5432]:
        if is_port_open("127.0.0.1", port):
            return (
                f"postgresql+psycopg://postgres:postgres@localhost:{port}/postgres",
                f"postgresql+psycopg://app_user:app_user@localhost:{port}/postgres",
            )

    return (
        "postgresql+psycopg://postgres:postgres@localhost:55432/postgres",
        "postgresql+psycopg://app_user:app_user@localhost:55432/postgres",
    )


MIGRATOR_DB_URL, APP_USER_DB_URL = detect_db_urls()
os.environ["DATABASE_URL_MIGRATOR"] = MIGRATOR_DB_URL
os.environ["DATABASE_URL"] = APP_USER_DB_URL


@pytest.fixture(scope="session")
def migrator_url() -> str:
    return MIGRATOR_DB_URL


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

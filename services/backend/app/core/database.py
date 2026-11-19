from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


# Application runtime engine and sessionmaker
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_migrator_engine(url: str | None = None) -> Session:
    """Helper to get a session with migrator / admin privileges."""
    migrator_url = url or settings.DATABASE_URL_MIGRATOR
    m_engine = create_engine(migrator_url, pool_pre_ping=True)
    m_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=m_engine)
    return m_session_factory()

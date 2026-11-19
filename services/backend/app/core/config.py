from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "local"
    DB_PORT: int = 5432
    API_PORT: int = 8000
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    APP_DB_PASSWORD: str | None = None
    DATABASE_URL: str = "postgresql+psycopg://app_user:app_user@localhost:5432/postgres"
    DATABASE_URL_MIGRATOR: str = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"

    JWT_SECRET: str = Field(..., min_length=32)
    JWT_ISSUER: str = "brilliant-procurement-ai"
    JWT_ALGORITHM: str = "HS256"
    JWT_TTL_MINUTES: int = 15

    DEMO_USER_PASSWORD: str | None = None

    BLOB_CONNECTION_STRING: str | None = None
    BLOB_CONTAINER: str = "documents"

    AI_PROVIDER: str = "mock"
    INTEGRATIONS_MODE: str = "mock"

    CORS_ORIGINS: list[str] = []

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env", Path(__file__).resolve().parents[3] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()  # type: ignore[call-arg]

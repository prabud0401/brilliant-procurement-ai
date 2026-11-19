from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "local"
    DATABASE_URL: str = "postgresql+psycopg://app_user:app_user@localhost:5432/postgres"
    DATABASE_URL_MIGRATOR: str = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"

    JWT_SECRET: str = "dev-insecure-secret-change-in-production-32chars"
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


settings = Settings()

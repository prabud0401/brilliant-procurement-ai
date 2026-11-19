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

    MAX_UPLOAD_SIZE_BYTES: int = 4 * 1024 * 1024  # 4 MB default while DI F0
    MAX_UPLOAD_PAGES: int = 20
    UPLOAD_RATE_LIMIT_PER_MINUTE: int = 60

    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o-mini"
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = "text-embedding-3-small"
    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_DOCINTEL_ENDPOINT: str | None = None
    AZURE_DOCINTEL_KEY: str | None = None

    AI_DAILY_BUDGET_AED: float = 50.0
    AI_LOW_CONFIDENCE_THRESHOLD: float = 0.80

    CORS_ORIGINS: list[str] = []

    REPLAY_FIXTURES_DIR: str | None = None

    def get_replay_fixtures_dir(self) -> Path:
        """Resolve replay fixtures directory lazily.

        Raises FileNotFoundError if missing when accessed.
        """
        if self.REPLAY_FIXTURES_DIR:
            p = Path(self.REPLAY_FIXTURES_DIR)
            if p.is_dir():
                return p
            raise FileNotFoundError(
                f"Configured REPLAY_FIXTURES_DIR does not exist or is not a directory: {p}"
            )

        # Discovered relative to the repo when running from source
        candidates: list[Path] = [Path.cwd() / "eval" / "data" / "replay"]
        for parent in Path(__file__).resolve().parents:
            candidates.append(parent / "eval" / "data" / "replay")

        for candidate in candidates:
            if candidate.is_dir():
                return candidate

        raise FileNotFoundError(
            "Replay fixtures directory not found. Please set the REPLAY_FIXTURES_DIR environment "
            "variable or ensure 'eval/data/replay' exists relative to the repository root."
        )

    model_config = SettingsConfigDict(
        env_file=(
            ".env",
            "../../.env",
            *([p / ".env" for p in Path(__file__).resolve().parents if (p / ".env").is_file()][:1]),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()  # type: ignore[call-arg]

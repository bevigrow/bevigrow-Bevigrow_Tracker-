"""Application settings, loaded from environment variables."""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    ENVIRONMENT: str = "development"

    # Neon PostgreSQL. Example:
    # postgresql+psycopg://USER:PASS@ep-xxx.aws.neon.tech/bevigrow?sslmode=require
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'bevigrow_dev.db'}"

    # PostgreSQL schema to own BeviGrow's tables. Keeping them out of `public`
    # means the app can share a Neon database with anything else already there
    # (Neon Auth, an earlier prototype) without table-name collisions.
    # Ignored on SQLite, which has no schema concept.
    DB_SCHEMA: str = "bevigrow"

    # Connection pooling (ignored for SQLite)
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 300
    DB_POOL_TIMEOUT: int = 30

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    # AI — Claude Haiku only. Opus-tier models are intentionally not used.
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "claude-haiku-4-5"
    AI_MAX_TOKENS: int = 900

    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_UPLOAD_MB: int = 15

    # Comma-separated list, or "*" for any origin.
    CORS_ORIGINS: str = "*"

    SEED_ADMIN_EMAIL: str = "bevigrow@gmail.com"
    SEED_ADMIN_PASSWORD: str = "Bevi@GROW30@"
    SEED_ADMIN_NAME: str = "BeviGrow Admin"

    @field_validator("DATABASE_URL")
    @classmethod
    def _use_psycopg3_driver(cls, value: str) -> str:
        """Normalise the connection URL onto the psycopg 3 driver.

        Neon (and Render, Heroku, Supabase) hand out URLs starting with
        `postgresql://` or `postgres://`. SQLAlchemy maps both to psycopg2,
        which this project does not install — the result is a confusing
        `ModuleNotFoundError: No module named 'psycopg2'` at import time.
        Rewriting the scheme here means a URL can be pasted in verbatim.
        """
        url = value.strip()
        for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://", "sqlite"):
            if url.startswith(prefix):
                return url
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://") :]
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://") :]
        return url

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def schema(self) -> str | None:
        """The schema to bind models to — None on SQLite."""
        if self.is_sqlite or not self.DB_SCHEMA.strip():
            return None
        return self.DB_SCHEMA.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

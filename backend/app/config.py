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

    # ---------------------------------------------------------------- auth
    # Google Identity Services OAuth client ID. Blank disables Google sign-in
    # entirely — the button is hidden and the endpoint refuses.
    GOOGLE_CLIENT_ID: str = ""

    # When False, only an admin can create accounts (invite-only). When True,
    # anyone may register and lands in the lowest-privilege role.
    ALLOW_SELF_SIGNUP: bool = False
    # Optional: restrict self-signup and Google sign-in to one or more email
    # domains, e.g. "bevigrow.com,partner.com". Blank allows any domain.
    ALLOWED_EMAIL_DOMAINS: str = ""
    # Role handed to accounts created by signup or first Google sign-in.
    DEFAULT_SIGNUP_ROLE: str = "employee"

    # Password-reset links point here.
    FRONTEND_URL: str = "http://localhost:5173"
    RESET_TOKEN_TTL_MINUTES: int = 60

    # SMTP for password-reset email. Unset means no mail is sent; an admin can
    # still reset a password from the Team page.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "BeviGrow <no-reply@bevigrow.local>"
    SMTP_STARTTLS: bool = True

    @property
    def google_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID.strip())

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.SMTP_HOST.strip())

    @property
    def allowed_domains(self) -> list[str]:
        return [
            d.strip().lower().lstrip("@")
            for d in self.ALLOWED_EMAIL_DOMAINS.split(",")
            if d.strip()
        ]

    def email_domain_allowed(self, email: str) -> bool:
        domains = self.allowed_domains
        if not domains:
            return True
        return email.rsplit("@", 1)[-1].lower() in domains

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
        """Allowed origins, each normalised to a full scheme://host form.

        Render's `fromService` substitution supplies a bare hostname, and a
        CORS origin without a scheme never matches the browser's `Origin`
        header — the requests fail with an opaque CORS error.
        """
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]

        origins: list[str] = []
        for raw in self.CORS_ORIGINS.split(","):
            origin = raw.strip().rstrip("/")
            if not origin:
                continue
            if not origin.startswith(("http://", "https://")):
                origin = f"https://{origin}"
            origins.append(origin)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

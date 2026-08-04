"""SQLAlchemy engine, session factory and declarative base.

Uses PostgreSQL connection pooling (Neon) in production; falls back to a local
SQLite file when DATABASE_URL is not configured so the app still boots for
local development.
"""
from collections.abc import Generator

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    # Binding the metadata to a dedicated schema keeps BeviGrow's tables from
    # colliding with anything already living in the database's `public` schema.
    metadata = MetaData(schema=settings.schema)


def _engine_kwargs() -> dict:
    if settings.is_sqlite:
        return {"connect_args": {"check_same_thread": False}}
    return {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        # Neon closes idle connections; verify liveness before handing one out.
        "pool_pre_ping": True,
    }


engine = create_engine(settings.DATABASE_URL, future=True, **_engine_kwargs())

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_schema() -> None:
    """Create the application schema if it does not exist yet (PostgreSQL)."""
    if settings.schema is None:
        return
    with engine.begin() as conn:
        # Identifier is from our own config, not user input, but quote it so an
        # unusual schema name can't break the statement.
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.schema}"'))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

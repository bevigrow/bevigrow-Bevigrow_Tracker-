"""BeviGrow Coffee B2B Tracker — FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from . import seed
from .config import settings
from .database import engine
from .routers import (
    activities,
    ai_routes,
    auth,
    contacts,
    countries,
    dashboard,
    documents,
    outreach,
    reminders,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s"
)
log = logging.getLogger("bevigrow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting BeviGrow API in %s mode", settings.ENVIRONMENT)
    log.info("Database: %s", "PostgreSQL (Neon)" if not settings.is_sqlite else "SQLite (local dev)")
    log.info("AI model: %s", settings.AI_MODEL)
    seed.run()
    yield
    engine.dispose()


app = FastAPI(
    title="BeviGrow Coffee B2B API",
    description=(
        "Export & import management for BeviGrow's coffee trading operations. "
        "AI features run on Claude Haiku."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=settings.cors_origin_list != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(auth.users_router)
app.include_router(contacts.router)
app.include_router(countries.router)
app.include_router(activities.router)
app.include_router(documents.router)
app.include_router(reminders.router)
app.include_router(dashboard.router)
app.include_router(outreach.router)
app.include_router(ai_routes.router)


@app.get("/", tags=["health"])
def root():
    return {
        "name": "BeviGrow Coffee B2B API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
    }


@app.get("/api/health", tags=["health"])
def health():
    """Liveness + database connectivity probe for Render."""
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - report, don't crash the probe
        log.error("Health check DB error: %s", exc)
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "ai_model": settings.AI_MODEL,
        "environment": settings.ENVIRONMENT,
    }

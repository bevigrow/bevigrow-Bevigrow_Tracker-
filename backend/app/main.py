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
    campaigns,
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
    # An attempt left mid-flight by a restart must be settled before any
    # queue moves again, or it would be picked up and sent a second time.
    try:
        from .database import SessionLocal
        from .services.engine import recover_stuck
        with SessionLocal() as session:
            recovered = recover_stuck(session)
        if recovered:
            log.warning('%d interrupted send(s) marked unverified', recovered)
    except Exception as exc:  # noqa: BLE001 - never block startup
        log.error('Send recovery failed: %s', exc)
    # The sender runs in here, so a campaign continues after the browser
    # that started it has gone. State lives in the database, so the thread
    # can stop at any moment without losing its place.
    from .services import scheduler
    scheduler.start()
    yield
    scheduler.stop()
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

@app.middleware("http")
async def _wake_the_sender(request, call_next):
    """A person using the app is the signal that work may exist.

    The sender goes dormant when no campaign is running, so that a quiet
    night costs no database time at all. What brings it back is this: every
    request that is not a health probe nudges it. The request has woken the
    database regardless, so the nudge is free, and it means a campaign
    started from the UI begins at once rather than when a timer next fires.
    """
    response = await call_next(request)
    if not request.url.path.startswith(("/api/health", "/api/campaigns/tick")):
        try:
            from .services import scheduler
            scheduler.nudge()
        except Exception:  # noqa: BLE001 - never break a request over this
            pass
    return response


app.include_router(auth.router)
app.include_router(auth.users_router)
app.include_router(contacts.router)
app.include_router(countries.router)
app.include_router(campaigns.router)
app.include_router(campaigns.accounts_router)
app.include_router(campaigns.templates_router)
app.include_router(campaigns.replies_router)
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

    # Whether anything is driving the send queue. A campaign stuck at nought
    # sent looks the same whether the sender is working slowly, was switched
    # off, or died with the instance — and none of those show up as an error.
    try:
        from .services import scheduler
        sender_state = scheduler.state()
    except Exception as exc:  # noqa: BLE001 - the probe must not fail
        sender_state = {"error": str(exc)[:200]}

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "ai_model": settings.AI_MODEL,
        "environment": settings.ENVIRONMENT,
        "sender": sender_state,
    }

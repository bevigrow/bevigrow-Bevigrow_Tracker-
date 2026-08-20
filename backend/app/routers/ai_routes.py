"""AI endpoints.

None of these make a person wait for a model. Generation happens after the
response has been sent; the request itself is answered from the database. See
`_cached_insight` for why.
"""
from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal, get_db
from ..deps import get_current_user, require_roles
from ..models import AIInsight, Contact, DealStatus, Reminder, User
from ..schemas import (
    InsightResponse,
    SuggestionItem,
    SuggestionsResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from ..services import ai, providers
from .dashboard import compute_stats

log = logging.getLogger("bevigrow.ai")

router = APIRouter(prefix="/api/ai", tags=["ai"])

# How long a stored insight counts as fresh. Past this it is still served —
# instantly — while a new one is written behind the response.
CACHE_MINUTES = 30

# Keys currently being regenerated, so a burst of requests triggers one call
# rather than one per request.
_refreshing: set[str] = set()
_refresh_lock = threading.Lock()

# Statuses where silence from the counterparty is itself a signal.
AWAITING_REPLY = {
    DealStatus.quotation_sent,
    DealStatus.sample_sent,
    DealStatus.negotiation,
    DealStatus.contacted,
    DealStatus.new_lead,
}


@router.get("/status")
def ai_status(_: User = Depends(get_current_user)):
    return {
        "ai_enabled": ai.ai_enabled(),
        "model": ai.active_model(),
        "provider": providers.active_provider() or "none",
        "note": "Gemini (free tier) is preferred when configured; otherwise Claude Haiku, "
                "otherwise built-in rules.",
    }


@router.get("/diagnose")
def ai_diagnose(_: User = Depends(require_roles("admin"))):
    """Why is the AI falling back to templates?

    `/status` says which provider *would* be used; it cannot say whether the
    key works. This calls each configured provider for real and returns the
    error verbatim, so a wrong key, a spent balance and an exhausted quota are
    distinguishable from each other without reading server logs.

    Admin-only, and it reports key prefixes rather than keys.
    """
    return {
        "selected_provider": providers.active_provider() or "none",
        "ai_provider_setting": settings.AI_PROVIDER,
        "gemini": {
            "key": providers.key_fingerprint(settings.GEMINI_API_KEY),
            "model": settings.GEMINI_MODEL,
            "probe": (
                providers.probe("gemini")
                if settings.GEMINI_API_KEY.strip()
                else "skipped - no key"
            ),
        },
        "anthropic": {
            "key": providers.key_fingerprint(settings.ANTHROPIC_API_KEY),
            "model": settings.AI_MODEL,
            "probe": (
                providers.probe("anthropic")
                if settings.ANTHROPIC_API_KEY.strip()
                else "skipped - no key"
            ),
        },
    }


@router.post("/summarize", response_model=SummarizeResponse)
def summarize(payload: SummarizeRequest, _: User = Depends(get_current_user)):
    summary, used_ai = ai.summarize_interaction(
        payload.notes, payload.company_name, payload.country
    )
    return SummarizeResponse(summary=summary, model=ai.active_model(), ai_enabled=used_ai)


def _store(kind: str, content: str, used_ai: bool) -> None:
    """Write a generated insight on its own session.

    Its own, because this runs after the response has been sent and the
    request's session is already closed.
    """
    with SessionLocal() as session:
        session.add(
            AIInsight(
                kind=kind,
                content=content,
                model=ai.active_model() if used_ai else "rule-based",
            )
        )
        session.commit()


def _regenerate(kind: str, builder) -> None:
    """Build a fresh insight in the background, once per key at a time.

    The guard matters on a dashboard: several panels and a page refresh can
    all notice the same stale entry within a second of each other, and without
    it each would start its own twelve-second call to the model.
    """
    with _refresh_lock:
        if kind in _refreshing:
            return
        _refreshing.add(kind)
    try:
        content, used_ai = builder()
        _store(kind, content, used_ai)
    except Exception as exc:  # noqa: BLE001 - a background failure must stay silent
        log.warning("Background insight refresh failed for %s: %s", kind, exc)
    finally:
        with _refresh_lock:
            _refreshing.discard(kind)


def _cached_insight(
    db: Session,
    kind: str,
    refresh: bool,
    builder,
    background: BackgroundTasks | None = None,
    fallback=None,
) -> InsightResponse:
    """Answer from the database now; talk to the model afterwards.

    Measured on production, a cache miss here took **11.8 seconds** — the
    provider reasons at length before writing three lines. The panel was
    fetched off the critical path already, so the page still rendered, but
    somebody watched a spinner for twelve seconds every half hour, and on a
    phone that is the part you notice.

    Nothing is gained by making them wait for it. A briefing thirty-five
    minutes old is not meaningfully worse than one written this second, so:

      fresh  -> serve it
      stale  -> serve the stale copy immediately, refresh behind the response
      empty  -> serve the deterministic rule-based summary, same refresh

    Every path answers in database time. The only request that still waits is
    an explicit Refresh, where somebody has asked for new words and is
    watching a button spin — there, waiting is the honest behaviour.
    """
    now = datetime.now(timezone.utc)
    latest = db.scalar(
        select(AIInsight).where(AIInsight.kind == kind).order_by(AIInsight.created_at.desc())
    )

    if refresh:
        content, used_ai = builder()
        _store(kind, content, used_ai)
        return InsightResponse(
            content=content,
            model=ai.active_model() if used_ai else "rule-based",
            generated_at=now,
            cached=False,
            ai_enabled=used_ai,
        )

    if latest is not None:
        age = latest.created_at
        if age.tzinfo is None:
            age = age.replace(tzinfo=timezone.utc)
        is_fresh = age >= now - timedelta(minutes=CACHE_MINUTES)
        if not is_fresh and background is not None:
            background.add_task(_regenerate, kind, builder)
        return InsightResponse(
            content=latest.content,
            model=latest.model,
            generated_at=latest.created_at,
            cached=True,
            ai_enabled=ai.ai_enabled(),
        )

    # Nothing stored at all — the first ever load, or a new prompt version.
    if background is not None:
        background.add_task(_regenerate, kind, builder)
    if fallback is not None:
        return InsightResponse(
            content=fallback(),
            model="rule-based",
            generated_at=now,
            cached=False,
            ai_enabled=False,
        )

    content, used_ai = builder()
    _store(kind, content, used_ai)
    return InsightResponse(
        content=content,
        model=ai.active_model() if used_ai else "rule-based",
        generated_at=now,
        cached=False,
        ai_enabled=used_ai,
    )


def _stats_payload(db: Session) -> dict:
    stats = compute_stats(db)
    return {
        "kpis": stats["kpis"].model_dump(),
        "export_vs_import": stats["export_vs_import"],
        "top_countries": [c.model_dump() for c in stats["by_country"][:6]],
        "pipeline_by_status": [
            s.model_dump() for s in stats["by_status"] if s.count > 0
        ],
        "last_14_days": [t.model_dump() for t in stats["trend"]],
    }


@router.get("/insights", response_model=InsightResponse)
def dashboard_insights(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    refresh: bool = Query(default=False, description="Generate now instead of serving the stored copy"),
):
    payload = _stats_payload(db)
    return _cached_insight(
        db,
        f"dashboard:{ai.prompt_fingerprint()}",
        refresh,
        lambda: ai.dashboard_insight(payload),
        background=background,
        fallback=lambda: ai.fallback_briefing(payload),
    )


@router.get("/weekly", response_model=InsightResponse)
def weekly_report(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    refresh: bool = Query(default=False),
):
    payload = _stats_payload(db)
    payload["window"] = "last 7 days vs prior 7 days"
    return _cached_insight(
        db,
        "weekly",
        refresh,
        lambda: ai.weekly_highlights(payload),
        background=background,
        fallback=lambda: ai.fallback_briefing(payload),
    )


def build_suggestions(db: Session, limit: int, min_days_silent: int) -> SuggestionsResponse:
    """Rank accounts that need attention, with a reason and a next action.

    Plain function (no FastAPI dependencies) so other endpoints can reuse it.
    """
    today = date.today()
    now = datetime.now(timezone.utc)

    contacts = db.scalars(
        select(Contact).where(Contact.status.in_(AWAITING_REPLY))
    ).all()

    candidates: list[dict] = []
    for c in contacts:
        if c.last_contacted_at:
            last = c.last_contacted_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            days_silent = (now - last).days
        else:
            days_silent = None

        overdue = c.next_follow_up is not None and c.next_follow_up <= today
        silent_enough = days_silent is None or days_silent >= min_days_silent
        if not (overdue or silent_enough):
            continue

        candidates.append(
            {
                "contact_id": c.id,
                "company_name": c.company_name,
                "country": c.country,
                "status": c.status.value,
                "days_since_contact": days_silent,
                "activity_count": len(c.activities),
                "coffee_product": c.coffee_product,
                "follow_up_overdue": overdue,
            }
        )

    candidates.sort(key=lambda x: (x["days_since_contact"] is None, -(x["days_since_contact"] or 0)))
    candidates = candidates[:limit]

    ranked, used_ai = ai.followup_suggestions(candidates)

    suggestions = [
        SuggestionItem(
            contact_id=item["contact_id"],
            company_name=item["company_name"],
            country=item["country"],
            status=DealStatus(item["status"]),
            priority=item["priority"],
            reason=item["reason"],
            suggested_action=item["suggested_action"],
            days_since_contact=item.get("days_since_contact"),
        )
        for item in ranked
    ]
    return SuggestionsResponse(
        suggestions=suggestions,
        model=ai.active_model() if used_ai else "rule-based",
        ai_enabled=used_ai,
    )


@router.get("/suggestions", response_model=SuggestionsResponse)
def smart_followups(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    limit: int = Query(default=12, ge=1, le=30),
    min_days_silent: int = Query(default=3, ge=0, le=90),
):
    return build_suggestions(db, limit, min_days_silent)


@router.post("/suggestions/apply", response_model=list[int])
def apply_suggestions(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    limit: int = Query(default=12, ge=1, le=30),
    min_days_silent: int = Query(default=3, ge=0, le=90),
):
    """Turn the current AI suggestions into concrete reminder rows."""
    result = build_suggestions(db, limit, min_days_silent)
    created: list[int] = []
    today = date.today()

    for s in result.suggestions:
        exists = db.scalar(
            select(Reminder).where(
                Reminder.contact_id == s.contact_id,
                Reminder.source == "ai",
                Reminder.is_done.is_(False),
            )
        )
        if exists:
            continue
        reminder = Reminder(
            contact_id=s.contact_id,
            due_date=today,
            message=s.suggested_action[:500],
            source="ai",
            priority=s.priority,
        )
        db.add(reminder)
        db.flush()
        created.append(reminder.id)

    db.commit()
    return created

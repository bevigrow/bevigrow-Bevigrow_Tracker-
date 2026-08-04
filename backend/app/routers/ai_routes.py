"""AI endpoints — all powered by Claude Haiku (`claude-haiku-4-5`)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import AIInsight, Contact, DealStatus, Reminder, User
from ..schemas import (
    InsightResponse,
    SuggestionItem,
    SuggestionsResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from ..services import ai
from .dashboard import compute_stats

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Insights are cached this long so a dashboard refresh doesn't re-bill the API.
CACHE_MINUTES = 30

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
        "model": settings.AI_MODEL,
        "note": "All AI features run on Claude Haiku for low cost and fast response.",
    }


@router.post("/summarize", response_model=SummarizeResponse)
def summarize(payload: SummarizeRequest, _: User = Depends(get_current_user)):
    summary, used_ai = ai.summarize_interaction(
        payload.notes, payload.company_name, payload.country
    )
    return SummarizeResponse(summary=summary, model=settings.AI_MODEL, ai_enabled=used_ai)


def _cached_insight(
    db: Session, kind: str, refresh: bool, builder
) -> InsightResponse:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=CACHE_MINUTES)
    if not refresh:
        cached = db.scalar(
            select(AIInsight)
            .where(AIInsight.kind == kind, AIInsight.created_at >= cutoff)
            .order_by(AIInsight.created_at.desc())
        )
        if cached:
            return InsightResponse(
                content=cached.content,
                model=cached.model,
                generated_at=cached.created_at,
                cached=True,
                ai_enabled=ai.ai_enabled(),
            )

    content, used_ai = builder()
    record = AIInsight(kind=kind, content=content, model=settings.AI_MODEL if used_ai else "rule-based")
    db.add(record)
    db.commit()
    db.refresh(record)
    return InsightResponse(
        content=record.content,
        model=record.model,
        generated_at=record.created_at,
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
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    refresh: bool = Query(default=False, description="Bypass the 30-minute cache"),
):
    payload = _stats_payload(db)
    return _cached_insight(db, "dashboard", refresh, lambda: ai.dashboard_insight(payload))


@router.get("/weekly", response_model=InsightResponse)
def weekly_report(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    refresh: bool = Query(default=False),
):
    payload = _stats_payload(db)
    payload["window"] = "last 7 days vs prior 7 days"
    return _cached_insight(db, "weekly", refresh, lambda: ai.weekly_highlights(payload))


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
        model=settings.AI_MODEL if used_ai else "rule-based",
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

"""Dashboard analytics: KPIs, country breakdown, pipeline mix, trends."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    CLOSED_WON,
    OPEN_PIPELINE,
    Activity,
    Contact,
    DealStatus,
    Reminder,
    TradeType,
    User,
)
from ..schemas import (
    ActivityOut,
    CountryStat,
    DashboardOut,
    KpiSet,
    ReminderOut,
    StatusStat,
    TrendPoint,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

EXPORT_ORDER_STATUSES = {
    DealStatus.order_confirmed,
    DealStatus.production,
    DealStatus.shipment_in_progress,
    DealStatus.delivered,
    DealStatus.completed,
}


def _greeting(now: datetime) -> str:
    hour = now.hour
    if hour < 12:
        return "Good Morning, BeviGrow Team"
    if hour < 17:
        return "Good Afternoon, BeviGrow Team"
    return "Good Evening, BeviGrow Team"


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time(), timezone.utc)
    return start, start + timedelta(days=1)


def compute_stats(db: Session) -> dict:
    """Raw numbers, reused by both the dashboard endpoint and the AI prompts."""
    now = datetime.now(timezone.utc)
    today = now.date()
    today_start, today_end = _day_bounds(today)

    total_contacts = db.scalar(select(func.count(Contact.id))) or 0

    status_rows = db.execute(
        select(Contact.status, func.count(Contact.id)).group_by(Contact.status)
    ).all()
    status_counts = {status: count for status, count in status_rows}

    trade_rows = db.execute(
        select(Contact.trade_type, func.count(Contact.id)).group_by(Contact.trade_type)
    ).all()
    trade_counts = {t: c for t, c in trade_rows}

    export_orders = (
        db.scalar(
            select(func.count(Contact.id)).where(
                Contact.trade_type == TradeType.export,
                Contact.status.in_(EXPORT_ORDER_STATUSES),
            )
        )
        or 0
    )
    import_orders = (
        db.scalar(
            select(func.count(Contact.id)).where(
                Contact.trade_type == TradeType.import_,
                Contact.status.in_(EXPORT_ORDER_STATUSES),
            )
        )
        or 0
    )

    activities_today = (
        db.scalar(
            select(func.count(Activity.id)).where(
                Activity.occurred_at >= today_start, Activity.occurred_at < today_end
            )
        )
        or 0
    )

    pending_follow_ups = (
        db.scalar(
            select(func.count(Reminder.id)).where(
                Reminder.is_done.is_(False), Reminder.due_date <= today
            )
        )
        or 0
    )

    completed = status_counts.get(DealStatus.completed, 0) + status_counts.get(
        DealStatus.delivered, 0
    )
    closed_total = completed + status_counts.get(DealStatus.rejected, 0)
    conversion = round((completed / closed_total) * 100, 1) if closed_total else 0.0

    pipeline_value = (
        db.scalar(
            select(func.coalesce(func.sum(Contact.estimated_value_usd), 0.0)).where(
                Contact.status.in_(OPEN_PIPELINE)
            )
        )
        or 0.0
    )

    country_rows = db.execute(
        select(
            Contact.country,
            func.count(Contact.id),
            func.coalesce(func.sum(Contact.estimated_value_usd), 0.0),
        )
        .group_by(Contact.country)
        .order_by(func.count(Contact.id).desc())
    ).all()

    kpis = KpiSet(
        new_leads=status_counts.get(DealStatus.new_lead, 0),
        export_orders=export_orders,
        import_orders=import_orders,
        shipments_in_progress=status_counts.get(DealStatus.shipment_in_progress, 0),
        completed_orders=completed,
        pending_follow_ups=pending_follow_ups,
        total_contacts=total_contacts,
        activities_today=activities_today,
        conversion_rate=conversion,
        pipeline_value_usd=round(float(pipeline_value), 2),
    )

    by_country = [
        CountryStat(country=c or "Unknown", count=n, value_usd=round(float(v or 0), 2))
        for c, n, v in country_rows
    ]
    by_status = [StatusStat(status=s, count=status_counts.get(s, 0)) for s in DealStatus]

    # 14-day trend of activities and new leads.
    trend: list[TrendPoint] = []
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        start, end = _day_bounds(day)
        acts = (
            db.scalar(
                select(func.count(Activity.id)).where(
                    Activity.occurred_at >= start, Activity.occurred_at < end
                )
            )
            or 0
        )
        leads = (
            db.scalar(
                select(func.count(Contact.id)).where(
                    Contact.created_at >= start, Contact.created_at < end
                )
            )
            or 0
        )
        trend.append(TrendPoint(label=day.strftime("%d %b"), activities=acts, new_leads=leads))

    return {
        "greeting": _greeting(now),
        "kpis": kpis,
        "by_country": by_country,
        "by_status": by_status,
        "trend": trend,
        "export_vs_import": {
            "export": trade_counts.get(TradeType.export, 0),
            "import": trade_counts.get(TradeType.import_, 0),
        },
    }


@router.get("", response_model=DashboardOut)
def get_dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stats = compute_stats(db)

    recent = db.scalars(
        select(Activity)
        .options(selectinload(Activity.user), selectinload(Activity.contact))
        .order_by(Activity.occurred_at.desc())
        .limit(8)
    ).all()
    recent_out = []
    for a in recent:
        item = ActivityOut.model_validate(a)
        item.contact_company = a.contact.company_name if a.contact else None
        recent_out.append(item)

    upcoming = db.scalars(
        select(Reminder)
        .options(selectinload(Reminder.contact))
        .where(Reminder.is_done.is_(False))
        .order_by(Reminder.due_date.asc())
        .limit(8)
    ).all()
    upcoming_out = []
    for r in upcoming:
        item = ReminderOut.model_validate(r)
        item.contact_company = r.contact.company_name if r.contact else None
        upcoming_out.append(item)

    return DashboardOut(
        **stats, recent_activities=recent_out, upcoming_follow_ups=upcoming_out
    )


@router.get("/leaderboard")
def leaderboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    days: int = Query(default=30, ge=1, le=365),
):
    """Per-employee activity counts over the given window."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(User.id, User.name, func.count(Activity.id))
        .join(Activity, Activity.user_id == User.id)
        .where(Activity.occurred_at >= since)
        .group_by(User.id, User.name)
        .order_by(func.count(Activity.id).desc())
    ).all()
    return [{"user_id": uid, "name": name, "activities": count} for uid, name, count in rows]

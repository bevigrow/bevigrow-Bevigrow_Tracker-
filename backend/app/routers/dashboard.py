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
    DashboardFilterState,
    DashboardOut,
    KpiSet,
    ReminderOut,
    StatusStat,
    TrendPoint,
)
from ..services.geo import canon
from .countries import tally_countries

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

EXPORT_ORDER_STATUSES = {
    DealStatus.order_confirmed,
    DealStatus.production,
    DealStatus.shipment_in_progress,
    DealStatus.delivered,
    DealStatus.completed,
}

DEFAULT_TREND_DAYS = 14


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


def quote_scope(country: str | None, trade_type: TradeType | None) -> list:
    """Conditions that narrow every quote-derived figure to the current filter.

    Country is matched case- and padding-insensitively, because that is how it
    was stored: free text, typed by hand, sometimes pasted with a trailing
    space. (A doubled space inside a name is the one variation this misses —
    the tally in services.geo collapses those, SQL here does not.)
    """
    conds = []
    if trade_type:
        conds.append(Contact.trade_type == trade_type)
    if country and country.strip():
        conds.append(func.lower(func.trim(Contact.country)) == canon(country))
    return conds


def compute_stats(
    db: Session,
    *,
    country: str | None = None,
    trade_type: TradeType | None = None,
    days: int = DEFAULT_TREND_DAYS,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """Raw numbers, reused by both the dashboard endpoint and the AI prompts.

    With no arguments this is the whole desk, as it always was. Passing a
    country or trade type narrows every quote-derived figure — KPIs, stages,
    open value, and the activity trend through the quote each activity hangs
    off — so the page reads as one filtered view rather than a filtered chart
    surrounded by unfiltered totals.
    """
    now = datetime.now(timezone.utc)
    today = now.date()
    today_start, today_end = _day_bounds(today)

    scope = quote_scope(country, trade_type)

    def quotes(stmt):
        return stmt.where(*scope) if scope else stmt

    def via_quote(stmt, foreign_key):
        """The same narrowing for rows that hang off a quote."""
        if not scope:
            return stmt
        return stmt.join(Contact, foreign_key == Contact.id).where(*scope)

    total_contacts = db.scalar(quotes(select(func.count(Contact.id)))) or 0

    status_rows = db.execute(
        quotes(select(Contact.status, func.count(Contact.id))).group_by(Contact.status)
    ).all()
    status_counts = {status: count for status, count in status_rows}

    trade_rows = db.execute(
        quotes(select(Contact.trade_type, func.count(Contact.id))).group_by(Contact.trade_type)
    ).all()
    trade_counts = {t: c for t, c in trade_rows}

    export_orders = (
        db.scalar(
            quotes(
                select(func.count(Contact.id)).where(
                    Contact.trade_type == TradeType.export,
                    Contact.status.in_(EXPORT_ORDER_STATUSES),
                )
            )
        )
        or 0
    )
    import_orders = (
        db.scalar(
            quotes(
                select(func.count(Contact.id)).where(
                    Contact.trade_type == TradeType.import_,
                    Contact.status.in_(EXPORT_ORDER_STATUSES),
                )
            )
        )
        or 0
    )

    activities_today = (
        db.scalar(
            via_quote(select(func.count(Activity.id)), Activity.contact_id).where(
                Activity.occurred_at >= today_start, Activity.occurred_at < today_end
            )
        )
        or 0
    )

    pending_follow_ups = (
        db.scalar(
            via_quote(select(func.count(Reminder.id)), Reminder.contact_id).where(
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
            quotes(
                select(func.coalesce(func.sum(Contact.estimated_value_usd), 0.0)).where(
                    Contact.status.in_(OPEN_PIPELINE)
                )
            )
        )
        or 0.0
    )

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

    # The country breakdown covers cold outreach as well as quotes, and merges
    # spellings. Both matter: a country you have only prospected has no quote
    # rows at all, so grouping the quotes table alone showed nothing and the
    # name looked like it had been dropped on the way in. Filters are not
    # applied — this is the chart you choose a country from.
    by_country = [
        CountryStat(
            country=row.label,
            count=row.quotes,
            prospects=row.prospects,
            value_usd=round(row.value_usd, 2),
        )
        for row in tally_countries(db).rows()
    ]
    by_status = [StatusStat(status=s, count=status_counts.get(s, 0)) for s in DealStatus]

    # Trend of activities and new leads over the requested window.
    #
    # This used to ask the database two questions per day inside a loop: 28
    # round trips to build a sparkline. Every one of them was fast to execute
    # and slow to make, because the database is in another region and each
    # trip pays the latency whether it counts a million rows or none. Grouping
    # by day asks the same two questions once each, and the wall-clock cost of
    # the dashboard drops by roughly two thirds.
    # The window: an explicit range if one was given, otherwise the last N
    # days ending today.
    end_day = date_to or today
    start_day = date_from or (end_day - timedelta(days=max(1, days) - 1))
    if start_day > end_day:
        start_day, end_day = end_day, start_day
    window_start, _ = _day_bounds(start_day)
    _, window_end = _day_bounds(end_day)
    total_days = (end_day - start_day).days + 1

    def _per_day(column, timestamp, foreign_key=None) -> dict[date, int]:
        day = func.date(timestamp)
        stmt = select(day, func.count(column))
        if foreign_key is not None:
            stmt = via_quote(stmt, foreign_key)
        elif scope:
            stmt = stmt.where(*scope)
        rows = db.execute(
            stmt.where(timestamp >= window_start, timestamp < window_end).group_by(day)
        ).all()
        # func.date() comes back as a date on PostgreSQL and a string on
        # SQLite, so normalise before the lookup below.
        return {
            (d if isinstance(d, date) else date.fromisoformat(str(d))): n for d, n in rows
        }

    acts_by_day = _per_day(Activity.id, Activity.occurred_at, Activity.contact_id)
    leads_by_day = _per_day(Contact.id, Contact.created_at)

    # A year at one point per day is 365 marks in a chart 620 units wide: less
    # than two pixels each, unreadable, and a payload to match. Longer ranges
    # are grouped, so the shape of the year survives even though the individual
    # Tuesdays do not.
    if total_days <= 45:
        bucket, fmt = "day", "%d %b"
    elif total_days <= 130:
        bucket, fmt = "week", "%d %b"
    else:
        bucket, fmt = "month", "%b %Y"

    def _next_boundary(start: date) -> date:
        """The last day covered by the bucket beginning at `start`."""
        if bucket == "day":
            return start
        if bucket == "week":
            return start + timedelta(days=6)
        # Calendar months, not thirty-day blocks. Fixed blocks drift: starting
        # on 1 January, the second block began on the 31st and was still
        # labelled January, and February never appeared at all.
        if start.month == 12:
            return date(start.year, 12, 31)
        return date(start.year, start.month + 1, 1) - timedelta(days=1)

    # Days with no rows are absent from a GROUP BY, so the axis is built from
    # the calendar rather than from the results — a quiet day must show 0.
    trend: list[TrendPoint] = []
    cursor = start_day
    while cursor <= end_day:
        last = min(_next_boundary(cursor), end_day)
        days_in_bucket = [
            cursor + timedelta(days=i) for i in range((last - cursor).days + 1)
        ]
        trend.append(
            TrendPoint(
                label=cursor.strftime(fmt),
                activities=sum(acts_by_day.get(d, 0) for d in days_in_bucket),
                new_leads=sum(leads_by_day.get(d, 0) for d in days_in_bucket),
            )
        )
        cursor = last + timedelta(days=1)

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
        "filters": DashboardFilterState(
            country=(country or "").strip() or None,
            trade_type=trade_type,
            days=total_days,
            date_from=start_day,
            date_to=end_day,
            # So the chart can say "per week" rather than leaving the reader to
            # work out why Tuesday is missing.
            bucket_days={'day': 1, 'week': 7, 'month': 30}[bucket],
        ),
        "period": {
            "activities": sum(acts_by_day.values()),
            "new_leads": sum(leads_by_day.values()),
        },
    }


@router.get("", response_model=DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    country: str | None = Query(default=None, max_length=100),
    trade_type: TradeType | None = None,
    days: int = Query(default=DEFAULT_TREND_DAYS, ge=1, le=1095),
    date_from: date | None = Query(default=None, description="Start of an explicit range"),
    date_to: date | None = Query(default=None, description="End of an explicit range"),
):
    stats = compute_stats(
        db,
        country=country,
        trade_type=trade_type,
        days=days,
        date_from=date_from,
        date_to=date_to,
    )
    scope = quote_scope(country, trade_type)

    recent_stmt = select(Activity).options(
        selectinload(Activity.user), selectinload(Activity.contact)
    )
    if scope:
        recent_stmt = recent_stmt.join(Contact, Activity.contact_id == Contact.id).where(*scope)
    recent = db.scalars(recent_stmt.order_by(Activity.occurred_at.desc()).limit(8)).all()
    recent_out = []
    for a in recent:
        item = ActivityOut.model_validate(a)
        item.contact_company = a.contact.company_name if a.contact else None
        recent_out.append(item)

    upcoming_stmt = select(Reminder).options(selectinload(Reminder.contact))
    if scope:
        upcoming_stmt = upcoming_stmt.join(Contact, Reminder.contact_id == Contact.id).where(*scope)
    upcoming = db.scalars(
        upcoming_stmt.where(Reminder.is_done.is_(False))
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

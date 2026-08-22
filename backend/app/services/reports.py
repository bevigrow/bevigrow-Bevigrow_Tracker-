"""What happened, by day — and what it noticed while doing it.

Everything here reads the ledger, never the campaigns. That is deliberate: a
campaign is a working file that gets deleted when it is done or when it was
only a test, and the report has to survive that. Delete this morning's trial
run and the app must still know it wrote to those twelve companies this
morning, or it will write to them again.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .geo import canon
from .importer import company_key
from ..models import DailyQuota, Outreach, SendLedger
from . import campaigns as cm
from .geo import tidy
from .importer import normalize_company


def daily(db: Session, days: int = 30) -> list[dict]:
    """One entry per day that had activity, newest first."""
    since = cm.sending_day() - timedelta(days=max(1, days) - 1)
    rows = db.scalars(
        select(SendLedger).where(SendLedger.day >= since).order_by(SendLedger.at.desc())
    ).all()

    by_day: dict[date, list[SendLedger]] = defaultdict(list)
    for row in rows:
        by_day[row.day].append(row)

    # The quota rows are the independent record of how much of the allowance
    # was used. They are kept even for days whose ledger lines were purged.
    quotas = {
        q.day: q
        for q in db.scalars(select(DailyQuota).where(DailyQuota.day >= since)).all()
    }

    out: list[dict] = []
    for day in sorted(set(by_day) | set(quotas), reverse=True):
        entries = by_day.get(day, [])
        sent = [e for e in entries if e.outcome == "sent"]
        failed = [e for e in entries if e.outcome == "failed"]
        duplicates = [e for e in entries if e.outcome == "duplicate"]
        skipped = [e for e in entries if e.outcome == "skipped"]
        quota = quotas.get(day)
        out.append(
            {
                "day": day,
                "sent": len(sent),
                "failed": len(failed),
                "duplicates": len(duplicates),
                "skipped": len(skipped),
                "limit": quota.limit_value if quota else cm.HARD_DAILY_CAP,
                # Companies, not addresses: three mailboxes at one firm is one
                # company contacted, and saying "3 companies" would overstate
                # the day's reach.
                "companies": len({e.normalized_company or e.company_name for e in sent}),
                "campaigns": sorted({e.campaign_name for e in entries if e.campaign_name}),
                "sent_to": [
                    {"company": e.company_name, "email": e.email, "at": e.at, "country": e.country}
                    for e in sent
                ],
                "not_sent": [
                    {
                        "company": e.company_name,
                        # The location is what tells two firms of one name
                        # apart, so a line saying a company was skipped is
                        # ambiguous without it.
                        "location": e.location,
                        "country": e.country,
                        "email": e.email,
                        "outcome": e.outcome,
                        "reason": e.reason,
                    }
                    for e in (duplicates + skipped + failed)
                ],
            }
        )
    return out


def same_name_different_details(db: Session) -> list[dict]:
    """Companies sharing a name but not an address, a domain or a mailbox.

    Two firms called "Rothfos" in different cities are two firms; the same firm
    listed twice under two spellings is one. Only a person can tell, so this
    reports the pairs and states what differs, rather than merging anything.
    """
    rows = db.scalars(select(SendLedger)).all()
    groups: dict[str, list[SendLedger]] = defaultdict(list)
    for row in rows:
        # By the *name*, not by `normalized_company` — that column holds the
        # mail domain, which is precisely what differs between two firms
        # sharing a name. Grouping on it put every one of them in its own
        # group and the report came back empty.
        key = normalize_company(row.company_name)
        if key:
            groups[key].append(row)

    out: list[dict] = []
    for key, entries in groups.items():
        names = {e.company_name for e in entries if e.company_name}
        locations = {e.location for e in entries if e.location}
        domains = {e.domain for e in entries if e.domain}
        emails = {e.email for e in entries if e.email}
        websites = {e.website for e in entries if e.website}
        if len(locations) < 2 and len(domains) < 2 and len(emails) < 2:
            continue
        differs = []
        if len(locations) > 1:
            differs.append("address")
        if len(domains) > 1:
            differs.append("domain")
        if len(websites) > 1:
            differs.append("website")
        if len(emails) > 1 and len(domains) < 2:
            differs.append("mailbox")
        out.append(
            {
                "name": sorted(names)[0] if names else key,
                "spellings": sorted(names),
                "locations": sorted(locations),
                "emails": sorted(emails),
                "websites": sorted(websites),
                "differs_by": differs,
                "contacted": sum(1 for e in entries if e.outcome == "sent"),
                "skipped_as_duplicate": sum(1 for e in entries if e.outcome == "duplicate"),
            }
        )
    out.sort(key=lambda g: (-len(g["emails"]), g["name"]))
    return out


def totals(db: Session) -> dict:
    """The all-time figures, for the top of the report."""
    counts = dict(
        db.execute(
            select(SendLedger.outcome, func.count(SendLedger.id)).group_by(SendLedger.outcome)
        ).all()
    )
    companies = db.scalar(
        select(func.count(func.distinct(SendLedger.normalized_company))).where(
            SendLedger.outcome == "sent"
        )
    ) or 0
    return {
        "sent": counts.get("sent", 0),
        "failed": counts.get("failed", 0),
        "duplicates": counts.get("duplicate", 0),
        "skipped": counts.get("skipped", 0),
        "companies": companies,
        "today": cm.quota_state(db),
    }


def trends(db: Session, months: int = 12) -> dict:
    """Three questions the daily view cannot answer.

    Is it working *over time*, where has the effort gone *when*, and how long
    do the people who answer take to do it. All three read the ledger and the
    outreach log, so they survive campaigns being deleted.
    """
    today = cm.sending_day()
    first = date(today.year, today.month, 1)
    for _ in range(max(1, months) - 1):
        first = date(first.year - 1, 12, 1) if first.month == 1 else date(first.year, first.month - 1, 1)

    def month_key(value: date) -> str:
        return f"{value.year:04d}-{value.month:02d}"

    # Every month in the window, so a quiet one is a gap in the line rather
    # than a month that silently does not exist.
    axis: list[str] = []
    cursor = first
    while cursor <= today:
        axis.append(month_key(cursor))
        cursor = date(cursor.year + 1, 1, 1) if cursor.month == 12 else date(cursor.year, cursor.month + 1, 1)

    # Sourced from the outreach log, not the ledger.
    #
    # The ledger only began recording when it was built, so it knows nothing
    # about anything sent before that — and a chart of the last twelve months
    # that starts at "whenever this feature shipped" is a chart that quietly
    # says the work never happened. The outreach log is the record of every
    # company contacted, by hand or by campaign, since the beginning.
    sent_rows = db.execute(
        select(Outreach.contacted_on, func.count(Outreach.id))
        .where(Outreach.contacted_on.is_not(None), Outreach.contacted_on >= first)
        .group_by(Outreach.contacted_on)
    ).all()
    sent_by_month: dict[str, int] = defaultdict(int)
    for day, count in sent_rows:
        if isinstance(day, str):
            day = date.fromisoformat(day)
        sent_by_month[month_key(day)] += count

    replied_rows = db.execute(
        select(Outreach.replied_on, func.count(Outreach.id))
        .where(Outreach.replied_on.is_not(None), Outreach.replied_on >= first)
        .group_by(Outreach.replied_on)
    ).all()
    replied_by_month: dict[str, int] = defaultdict(int)
    for day, count in replied_rows:
        if isinstance(day, str):
            day = date.fromisoformat(day)
        replied_by_month[month_key(day)] += count

    by_month = [
        {
            "month": key,
            "label": date(int(key[:4]), int(key[5:]), 1).strftime("%b %y"),
            "sent": sent_by_month.get(key, 0),
            "replied": replied_by_month.get(key, 0),
        }
        for key in axis
    ]

    # Country against month. Two categories and one magnitude, which is a grid
    # rather than a stack: eleven countries would need eleven hues, and the
    # palette holds three on purpose.
    grid_rows = db.execute(
        select(Outreach.contacted_on, Outreach.country, func.count(Outreach.id))
        .where(Outreach.contacted_on.is_not(None), Outreach.contacted_on >= first)
        .group_by(Outreach.contacted_on, Outreach.country)
    ).all()
    grid: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for day, country, count in grid_rows:
        if isinstance(day, str):
            day = date.fromisoformat(day)
        grid[tidy(country) or "Unknown"][month_key(day)] += count

    countries = sorted(grid, key=lambda c: -sum(grid[c].values()))
    country_by_month = [
        {"country": c, "cells": [grid[c].get(m, 0) for m in axis]} for c in countries
    ]

    # How long the people who answer take. Only the ones who answered — the
    # silent majority has no response time, and averaging them in as zero or
    # as infinity would both be lies.
    gaps = db.execute(
        select(Outreach.contacted_on, Outreach.replied_on).where(
            Outreach.replied_on.is_not(None), Outreach.contacted_on.is_not(None)
        )
    ).all()
    buckets = [("Same day", 0, 0), ("1-3 days", 1, 3), ("4-7 days", 4, 7),
               ("8-14 days", 8, 14), ("15+ days", 15, 10_000)]
    counted = {label: 0 for label, _, _ in buckets}
    for contacted, replied in gaps:
        if isinstance(contacted, str):
            contacted = date.fromisoformat(contacted)
        if isinstance(replied, str):
            replied = date.fromisoformat(replied)
        days = max(0, (replied - contacted).days)
        for label, low, high in buckets:
            if low <= days <= high:
                counted[label] += 1
                break

    return {
        "months": [m["label"] for m in by_month],
        "by_month": by_month,
        "country_by_month": country_by_month,
        "response_days": [{"bucket": label, "count": counted[label]} for label, _, _ in buckets],
        "replies_counted": sum(counted.values()),
    }


def sent_by_country(db: Session) -> list[dict]:
    """Companies written to, per country, from everything the app knows.

    Two sources, deliberately, because neither alone is complete.

    The send ledger is the better one: it carries `normalized_company`, the
    key the importer grouped on, so info@ and sales@ at one business were one
    company before anything was sent. But it only holds sends made since it
    existed, and the log goes back further — reading only the ledger would
    silently omit whole countries written to before it.

    The outreach log covers those, at the cost of having to work out which
    rows are one company. That is done on the mail domain, which is the same
    rule the importer used, so the two sources agree about what a company is
    and a firm present in both is counted once.

    Only successful sends count from the ledger; a duplicate that was refused
    was already counted on the day the company was actually written to.
    """
    per_country: dict[str, dict] = {}
    # Which companies the ledger already accounted for. A log row for one of
    # these adds no emails, because the ledger holds every send it made.
    from_ledger: set[tuple[str, str]] = set()

    def note(country: str | None, key: str, emails: int) -> None:
        name = (country or "").strip()
        bucket = per_country.setdefault(
            canon(name) or "unknown",
            {"country": name or "Not recorded", "companies": set(), "emails": 0},
        )
        bucket["companies"].add(key)
        bucket["emails"] += emails

    for entry in db.scalars(select(SendLedger).where(SendLedger.outcome == "sent")):
        # Recomputed rather than trusted: `normalized_company` was written
        # by an older rule that grouped on the domain alone, so rows stored
        # before this would have every gmail company under one key.
        key = company_key(entry.email, entry.website, entry.company_name)
        from_ledger.add((canon((entry.country or "").strip()) or "unknown", key))
        note(entry.country, key, 1)

    # The log fills in what predates the ledger. A row can hold several
    # addresses, and each of those was an email that went out.
    for row in db.scalars(select(Outreach)):
        addresses = [a.strip() for a in (row.email or "").replace(";", ",").split(",") if a.strip()]
        key = company_key(addresses[0] if addresses else None, row.website, row.company_name)
        # Counted from the ledger already? Then the company is known and so
        # are its sends; this row would double them.
        #
        # Checked against the ledger specifically, not against whatever the
        # tally holds so far — an earlier version asked the latter, which made
        # a company's *second* log row look like a repeat of its first and
        # dropped one email per extra mailbox.
        name = canon((row.country or "").strip()) or "unknown"
        if (name, key) in from_ledger:
            note(row.country, key, 0)
        else:
            note(row.country, key, max(1, len(addresses)))

    rows = [
        {
            "country": v["country"],
            "companies": len(v["companies"]),
            "emails": v["emails"],
        }
        for v in per_country.values()
    ]
    rows.sort(key=lambda r: (-r["companies"], r["country"]))
    return rows

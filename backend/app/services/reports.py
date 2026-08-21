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

from ..models import DailyQuota, SendLedger
from . import campaigns as cm
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

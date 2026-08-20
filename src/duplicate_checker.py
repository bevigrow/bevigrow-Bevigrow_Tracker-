"""
Duplicate prevention.

Before a single message is prepared we check, in this order:

  1. the local send log (data/state/contacted.json) - instant, works offline
  2. the BeviGrow tracker itself - the real source of truth

Matching is done on company name (normalised, so "Benecke Coffee GmbH & Co. KG"
matches "Benecke Coffee"), on website domain, and on email address.

If the company was contacted inside DUPLICATE_COOLDOWN_DAYS the pipeline stops
and shows you: "Already contacted - review existing record."
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.config import STATE_DIR, settings
from src.logging_setup import get_logger
from src.models import ResearchResult
from src.utils import company_key, domain_of, normalise_company_name, parse_date, read_json, similar, write_json

log = get_logger("duplicates")

CONTACTED_FILE = STATE_DIR / "contacted.json"


@dataclass
class DuplicateVerdict:
    is_duplicate: bool = False
    reason: str = ""
    source: str = ""            # "local" or "tracker"
    record_id: int | None = None
    last_contacted: str = ""
    status: str = ""

    @property
    def summary(self) -> str:
        if not self.is_duplicate:
            return "No previous outreach found."
        bits = [self.reason]
        if self.last_contacted:
            bits.append(f"Last contacted {self.last_contacted}.")
        if self.status:
            bits.append(f"Status: {self.status}.")
        if self.record_id:
            bits.append(f"Tracker record #{self.record_id}.")
        return " ".join(bits)


# --------------------------------------------------------------------------
# Local log
# --------------------------------------------------------------------------
def _load_local() -> dict:
    return read_json(CONTACTED_FILE, default={}) or {}


def record_locally(company: str, website: str, email: str, channel: str,
                   tracker_id: int | None, message_hash: str, simulated: bool) -> None:
    """Remember that we contacted this company, whether or not the API call worked."""
    data = _load_local()
    key = company_key(company)
    entry = data.get(key, {"history": []})
    entry.update(
        {
            "company": company,
            "normalised": normalise_company_name(company),
            "domain": domain_of(website),
            "last_email": email,
            "last_contacted": date.today().isoformat(),
            "last_channel": channel,
            "tracker_id": tracker_id or entry.get("tracker_id"),
        }
    )
    entry.setdefault("history", []).append(
        {
            "date": date.today().isoformat(),
            "channel": channel,
            "email": email,
            "tracker_id": tracker_id,
            "message_hash": message_hash,
            "simulated": simulated,
        }
    )
    data[key] = entry
    write_json(CONTACTED_FILE, data)


def sends_today() -> int:
    """How many REAL sends happened today - used for the daily cap."""
    today = date.today().isoformat()
    count = 0
    for entry in _load_local().values():
        for item in entry.get("history", []):
            if item.get("date") == today and not item.get("simulated"):
                count += 1
    return count


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------
def _within_cooldown(when: str) -> bool:
    contacted = parse_date(when)
    if not contacted:
        return True  # unknown date -> treat as recent, be safe
    return (date.today() - contacted).days < settings.duplicate_cooldown_days


def check_local(company: str, website: str = "", email: str = "") -> DuplicateVerdict:
    data = _load_local()
    key = company_key(company)
    target_domain = domain_of(website)

    entry = data.get(key)
    if not entry:
        # Also try a fuzzy match and a domain match.
        for other_key, other in data.items():
            if similar(company, other.get("company", "")) >= 0.75:
                entry = other
                break
            if target_domain and other.get("domain") and target_domain == other["domain"]:
                entry = other
                break
            if email and email and other.get("last_email", "").lower() == email.lower():
                entry = other
                break

    if not entry:
        return DuplicateVerdict()

    last = entry.get("last_contacted", "")
    if not _within_cooldown(last):
        return DuplicateVerdict(
            is_duplicate=False,
            reason=f"Contacted before ({last}) but outside the {settings.duplicate_cooldown_days}-day cooldown.",
            source="local",
            last_contacted=last,
        )

    return DuplicateVerdict(
        is_duplicate=True,
        reason=f"Already contacted - local record for '{entry.get('company')}'.",
        source="local",
        record_id=entry.get("tracker_id"),
        last_contacted=last,
    )


def check_tracker(company: str, website: str = "", email: str = "") -> DuplicateVerdict:
    """Ask the BeviGrow tracker. Returns 'not duplicate' if the API is unreachable."""
    from src.tracker import TrackerError, get_client

    if not settings.tracker_configured:
        return DuplicateVerdict(reason="Tracker credentials not configured - skipped this check.")

    client = get_client()
    target_domain = domain_of(website)
    candidates: list[dict] = []

    try:
        core = normalise_company_name(company)
        search_term = core.split()[0] if core else company
        candidates.extend(client.list_outreach(search=search_term, limit=200))
        if target_domain:
            candidates.extend(client.list_outreach(search=target_domain, limit=100))
        if email:
            candidates.extend(client.list_outreach(search=email, limit=50))
    except TrackerError as exc:
        log.warning("Duplicate check against the tracker failed: %s", exc)
        return DuplicateVerdict(reason=f"Tracker check skipped: {exc}")

    seen_ids: set[int] = set()
    for record in candidates:
        rid = record.get("id")
        if rid in seen_ids:
            continue
        seen_ids.add(rid)

        name_match = similar(company, record.get("company_name", "")) >= 0.7
        domain_match = bool(target_domain) and target_domain == domain_of(record.get("website") or "")
        email_match = bool(email) and email.lower() == (record.get("email") or "").lower()

        if not (name_match or domain_match or email_match):
            continue

        why = (
            "same company name" if name_match
            else "same website domain" if domain_match
            else "same email address"
        )
        contacted_on = record.get("contacted_on") or ""
        status = record.get("status") or ""

        if not _within_cooldown(contacted_on):
            return DuplicateVerdict(
                is_duplicate=False,
                reason=f"Exists in the tracker ({why}) but last contacted {contacted_on}.",
                source="tracker",
                record_id=rid,
                last_contacted=contacted_on,
                status=status,
            )

        return DuplicateVerdict(
            is_duplicate=True,
            reason=f"Already in the BeviGrow tracker ({why}): '{record.get('company_name')}'.",
            source="tracker",
            record_id=rid,
            last_contacted=contacted_on,
            status=status,
        )

    return DuplicateVerdict()


def check(company: str, website: str = "", email: str = "",
          use_tracker: bool = True) -> DuplicateVerdict:
    """Full duplicate check. Local first (fast), then the tracker."""
    local = check_local(company, website, email)
    if local.is_duplicate:
        return local

    if use_tracker:
        remote = check_tracker(company, website, email)
        if remote.is_duplicate:
            return remote
        if remote.reason and not local.reason:
            local.reason = remote.reason
            local.record_id = remote.record_id or local.record_id
            local.status = remote.status or local.status

    return local


def check_research(result: ResearchResult, use_tracker: bool = True) -> DuplicateVerdict:
    email = result.primary_email.address if result.primary_email else ""
    return check(result.resolved_company_name, result.website, email, use_tracker=use_tracker)

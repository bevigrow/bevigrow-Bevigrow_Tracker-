"""The thing that keeps sending after you close the browser.

A daemon thread inside the API process, plus an endpoint an external cron can
poke. Not Celery, not Redis, not a paid worker — for fifty emails a day those
are three more things to run, pay for and debug, and the queue is already in
the database where a broker's queue would otherwise live.

The honest limitation, stated plainly because it shapes the design: this
application is hosted on an instance that may be put to sleep when nothing has
called it for a while. A thread inside a sleeping process does not run. So the
thread is not the guarantee — the *database* is. Every send is claimed, paced
and recorded transactionally, so the campaign can be interrupted at any instant
and continue from the next address whenever the process is alive again. The
external heartbeat (see `tick`) then makes "alive again" happen on a schedule
rather than when somebody happens to open the page.

The result: press Start, close the browser, and the campaign keeps going.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import select

from ..config import settings
from ..database import SessionLocal
from ..models import Campaign, CampaignStatus
from . import campaigns as cm
from . import engine

log = logging.getLogger("bevigrow.scheduler")

# Roughly how long between two emails. Fifty of them evenly spaced to the
# millisecond is a machine-shaped pattern; the jitter is applied per send.
PACE_SECONDS = settings.OUTREACH_PACE_SECONDS

# How long to wait before looking again when there is nothing to do. Long
# enough that an idle app is not querying constantly, short enough that
# pressing Start feels immediate.
IDLE_SECONDS = 10

_thread: threading.Thread | None = None
_stop = threading.Event()
# Held for the duration of one send so the loop and an HTTP tick cannot both
# be inside the engine at once in this process.
_sending = threading.Lock()


def running_campaigns(db) -> list[Campaign]:
    """Campaigns that want to send right now, oldest activity first.

    Includes the ones parked on yesterday's limit: `step` promotes those back
    to running by itself once the day rolls over, which is what makes "it
    continues tomorrow" happen without anyone pressing anything.
    """
    return list(
        db.scalars(
            select(Campaign)
            .where(Campaign.status.in_([CampaignStatus.running, CampaignStatus.daily_limit]))
            .order_by(Campaign.last_activity_at.asc().nullsfirst())
        ).all()
    )


def advance_once() -> dict:
    """Take one step on one campaign. Returns what happened, for the caller.

    One step, not one campaign's worth: with two campaigns running, they take
    turns rather than the first one holding the mailbox until it finishes.
    """
    with _sending:
        with SessionLocal() as db:
            campaigns = running_campaigns(db)
            if not campaigns:
                return {"action": "idle", "message": "No campaign is running."}

            account = engine.active_account(db)
            if account is None:
                for campaign in campaigns:
                    cm.pause(db, campaign, "No sending mailbox is connected.")
                return {"action": "idle", "message": "No sending mailbox is connected."}

            for campaign in campaigns:
                outcome = engine.step(db, campaign, account=account)
                if outcome.action != "idle":
                    return {
                        "action": outcome.action,
                        "message": outcome.message,
                        "campaign_id": campaign.id,
                        "company": outcome.target.company_name if outcome.target else None,
                    }
            return {"action": "idle", "message": "Nothing to do."}


def tick(max_steps: int = 12) -> dict:
    """Advance the queue a few steps. What the cron and the UI both call.

    Capped, because this runs inside a web request: a tick that tried to empty
    the whole queue would hold a worker for minutes and time out. The cron
    calls it again in ten minutes, and the in-process loop is doing the same
    work continuously in between.
    """
    done: list[dict] = []
    for _ in range(max(1, min(max_steps, 25))):
        result = advance_once()
        done.append(result)
        if result["action"] == "idle":
            break
        # Pace inside the tick as well, so a cron-driven run does not fire
        # twelve emails in two seconds.
        time.sleep(_paced())
    return {
        "steps": done,
        "sent": sum(1 for d in done if d["action"] == "sent"),
        "at": datetime.now(timezone.utc).isoformat(),
    }


def _paced() -> float:
    """Seconds to wait after a send, with a little jitter."""
    import random

    return PACE_SECONDS + random.random() * 2.0


def _loop() -> None:
    log.info("Outreach scheduler started (pace %.1fs)", PACE_SECONDS)
    while not _stop.is_set():
        try:
            result = advance_once()
            if result["action"] == "idle":
                _stop.wait(IDLE_SECONDS)
            else:
                log.info("Scheduler: %s — %s", result["action"], result["message"])
                _stop.wait(_paced())
        except Exception as exc:  # noqa: BLE001 - a loop that dies stops the product
            log.exception("Scheduler step failed: %s", exc)
            _stop.wait(30)
    log.info("Outreach scheduler stopped")


def start() -> None:
    """Begin the loop. Called once, at application startup."""
    global _thread
    if not settings.OUTREACH_SCHEDULER_ENABLED:
        log.info("Outreach scheduler disabled by configuration")
        return
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="outreach-scheduler", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()


def is_alive() -> bool:
    return bool(_thread and _thread.is_alive())

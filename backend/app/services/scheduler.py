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
from . import engine, replies

log = logging.getLogger("bevigrow.scheduler")

# Roughly how long between two emails. Fifty of them evenly spaced to the
# millisecond is a machine-shaped pattern; the jitter is applied per send.
PACE_SECONDS = settings.OUTREACH_PACE_SECONDS

# How long to wait before looking again when there is nothing to do. Long
# enough that an idle app is not querying constantly, short enough that
# pressing Start feels immediate.
IDLE_SECONDS = 10

# The inbox is read on its own clock, far slower than the send loop: a
# reply that lands at 10:00 and is noticed at 10:05 has cost nothing,
# whereas logging into IMAP every three seconds would be rude and slow.
REPLY_CHECK_SECONDS = settings.OUTREACH_REPLY_CHECK_SECONDS
_last_reply_check = 0.0
# When the sender last actually moved a queue, and what it did. Kept so the
# health endpoint can answer "is anything driving this?" — the question you
# are left with when a campaign sits at nought sent and no error anywhere.
_last_tick_at: float = 0.0
_last_tick_result: dict | None = None

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


def check_replies_if_due(force: bool = False) -> dict | None:
    """Read the mailbox, at most every REPLY_CHECK_SECONDS.

    Deliberately outside the send loop. Replies never consume quota and never
    trigger a send; the only thing a reply does automatically is update the
    company's own record and stop it being chased.
    """
    global _last_reply_check
    if not settings.OUTREACH_REPLY_CHECK_SECONDS and not force:
        return None
    now = time.monotonic()
    if not force and now - _last_reply_check < REPLY_CHECK_SECONDS:
        return None
    _last_reply_check = now

    with SessionLocal() as db:
        account = engine.active_account(db)
        if account is None or not account.imap_password_enc or not account.reply_check_enabled:
            return None
        result = replies.sync(db, account)
        if result.stored:
            log.info(
                "Replies: %d new (%d matched, %d unmatched)",
                result.stored,
                result.matched,
                result.unmatched,
            )
        return {
            "checked": result.checked,
            "stored": result.stored,
            "matched": result.matched,
            "unmatched": result.unmatched,
            "error": result.error,
        }


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


def state() -> dict:
    """Whether anything is driving the queue, and when it last did.

    A campaign that is not sending looks identical whether the scheduler is
    working through it slowly, has been switched off, or died with the
    instance that hosted it. This is what tells those three apart without
    reading a log file.
    """
    import time as _time

    alive = bool(_thread and _thread.is_alive())
    return {
        "enabled": settings.OUTREACH_SCHEDULER_ENABLED,
        "thread_alive": alive,
        "seconds_since_last_send": (
            round(_time.time() - _last_tick_at, 1) if _last_tick_at else None
        ),
        "last_result": _last_tick_result,
        "heartbeat_token_set": bool(settings.OUTREACH_TICK_TOKEN.strip()),
    }


def tick(max_steps: int = 12) -> dict:
    """Advance the queue a few steps. What the cron and the UI both call.

    Capped, because this runs inside a web request: a tick that tried to empty
    the whole queue would hold a worker for minutes and time out. The cron
    calls it again in ten minutes, and the in-process loop is doing the same
    work continuously in between.
    """
    # The heartbeat is also the only thing that runs when nobody is looking,
    # so it reads the inbox as well as advancing the queue.
    try:
        check_replies_if_due()
    except Exception as exc:  # noqa: BLE001
        log.warning("Reply check failed during tick: %s", exc)

    global _last_tick_at, _last_tick_result
    done: list[dict] = []
    for _ in range(max(1, min(max_steps, 25))):
        result = advance_once()
        _last_tick_at = time.time()
        _last_tick_result = result
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
            try:
                check_replies_if_due()
            except Exception as exc:  # noqa: BLE001 - reading must not stop sending
                log.warning("Reply check failed: %s", exc)
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

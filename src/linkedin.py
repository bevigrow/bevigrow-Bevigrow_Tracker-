"""
LinkedIn - prepared for you, never automated.

This module deliberately does NOT log in to LinkedIn, does not scrape profiles
behind authentication, and does not send connection requests. Automating a
personal LinkedIn account risks a permanent ban and breaks their terms.

What it does instead:
  * records the public LinkedIn URLs found during research
  * writes the personalised connection note and first message
  * keeps a task list you work through by hand, then marks done

Marking a task done writes the outreach into the BeviGrow tracker with
Channel = LinkedIn and Exact place = the LinkedIn URL.
"""

from __future__ import annotations

import re
from datetime import date

from src.config import RESULTS_DIR
from src.logging_setup import get_logger
from src.models import Channel, PersonCandidate, PreparedMessage, ResearchResult
from src.utils import read_json, write_json, write_text

log = get_logger("linkedin")

TASKS_FILE = RESULTS_DIR / "linkedin_tasks.json"
TASKS_MARKDOWN = RESULTS_DIR / "linkedin_tasks.md"


def pick_target(result: ResearchResult, person: PersonCandidate | None) -> tuple[str, str]:
    """
    Decide WHICH LinkedIn URL this task should point at.

    A personal profile is only used when the name in the profile URL actually
    matches the person we are writing to - otherwise the message would be
    addressed to one person and delivered to another. When there is no match
    we fall back to the company page.

    Returns (url, note_for_you).
    """
    import unicodedata

    def slug_tokens(text: str) -> set[str]:
        text = unicodedata.normalize("NFKD", text or "")
        text = text.encode("ascii", "ignore").decode("ascii").lower()
        return {t for t in re.split(r"[^a-z0-9]+", text) if len(t) > 2}

    if person and person.linkedin_url and "/in/" in person.linkedin_url:
        return person.linkedin_url, "profile verified for this person"

    if person and person.name:
        wanted = slug_tokens(person.name)
        for url in result.linkedin_profiles or ([result.linkedin_person_url]
                                                if result.linkedin_person_url else []):
            if wanted & slug_tokens(url.rsplit("/in/", 1)[-1]):
                return url, "profile matched by name"

    if result.linkedin_company_url:
        note = (
            "company page - no LinkedIn profile could be matched to "
            f"{person.name}" if person else "company page"
        )
        return result.linkedin_company_url, note

    if result.linkedin_profiles:
        return "", "profiles were found but none could be matched to this person"

    return "", "no LinkedIn page found"


def split_message(body: str) -> tuple[str, str]:
    """Separate the connection note from the follow-on message."""
    note_match = re.search(r"\[CONNECTION NOTE[^\]]*\]\s*\n(.*?)(?=\n\[|\Z)", body, re.S)
    msg_match = re.search(r"\[FIRST MESSAGE[^\]]*\]\s*\n(.*)", body, re.S)
    note = note_match.group(1).strip() if note_match else ""
    message = msg_match.group(1).strip() if msg_match else body.strip()
    return note, message


def add_task(result: ResearchResult, person: PersonCandidate | None,
             message: PreparedMessage, why: str = "") -> dict:
    """Queue a LinkedIn action for you to perform manually."""
    note, first_message = split_message(message.body)
    target = message.target_url or result.linkedin_person_url or result.linkedin_company_url

    task = {
        "company": result.resolved_company_name,
        "country": result.country,
        "website": result.website,
        "linkedin_url": target,
        "linkedin_company_url": result.linkedin_company_url,
        "linkedin_person_url": result.linkedin_person_url,
        "person": person.name if person else "",
        "person_title": person.title if person else "",
        "connection_note": note,
        "first_message": first_message,
        "why": why,
        "prepared_on": date.today().isoformat(),
        "status": "pending",
        "done_on": "",
        "tracker_id": None,
    }

    tasks = read_json(TASKS_FILE, default=[]) or []
    # Replace an existing pending task for the same company rather than duplicating.
    tasks = [
        t for t in tasks
        if not (t.get("company") == task["company"] and t.get("status") == "pending")
    ]
    tasks.append(task)
    write_json(TASKS_FILE, tasks)
    _write_markdown(tasks)
    log.info("LinkedIn task prepared for %s -> %s", task["company"], target or "(no URL)")
    return task


def list_tasks(status: str | None = "pending") -> list[dict]:
    tasks = read_json(TASKS_FILE, default=[]) or []
    if status:
        return [t for t in tasks if t.get("status") == status]
    return tasks


def mark_done(company: str, tracker_id: int | None = None) -> dict | None:
    tasks = read_json(TASKS_FILE, default=[]) or []
    updated = None
    for task in tasks:
        if task.get("company", "").lower() == company.lower() and task.get("status") == "pending":
            task["status"] = "sent"
            task["done_on"] = date.today().isoformat()
            task["tracker_id"] = tracker_id
            updated = task
            break
    if updated:
        write_json(TASKS_FILE, tasks)
        _write_markdown(tasks)
    return updated


def build_tracker_message(task: dict) -> PreparedMessage:
    """Turn a completed LinkedIn task into something the tracker can store."""
    body = ""
    if task.get("connection_note"):
        body += f"[Connection note]\n{task['connection_note']}\n\n"
    if task.get("first_message"):
        body += f"[Message]\n{task['first_message']}"
    return PreparedMessage(
        channel=Channel.LINKEDIN,
        subject="LinkedIn outreach",
        body=body.strip(),
        target_url=task.get("linkedin_url", ""),
    )


def _write_markdown(tasks: list[dict]) -> None:
    """A human-readable checklist you can keep open while working."""
    pending = [t for t in tasks if t.get("status") == "pending"]
    lines = [
        "# LinkedIn outreach - manual task list",
        "",
        "The system never sends these. Open each URL, paste the text, send it,",
        "then run:  python -m src.main linkedin-done \"Company Name\"",
        "",
        f"Pending: {len(pending)} | Completed: {len(tasks) - len(pending)}",
        "",
    ]
    for i, task in enumerate(pending, start=1):
        lines += [
            f"## {i}. {task['company']}",
            f"- **Open:** {task.get('linkedin_url') or '(no LinkedIn URL found)'}",
            f"- **Person:** {task.get('person') or '(none verified)'}"
            + (f" - {task['person_title']}" if task.get("person_title") else ""),
            f"- **Country:** {task.get('country') or '-'}",
            f"- **Website:** {task.get('website') or '-'}",
            f"- **Why LinkedIn:** {task.get('why') or '-'}",
            "",
            "**Connection note (max 300 characters):**",
            "",
            "```",
            task.get("connection_note", "").strip() or "(none)",
            "```",
            "",
            "**Message after connecting:**",
            "",
            "```",
            task.get("first_message", "").strip() or "(none)",
            "```",
            "",
            "---",
            "",
        ]
    write_text(TASKS_MARKDOWN, "\n".join(lines))

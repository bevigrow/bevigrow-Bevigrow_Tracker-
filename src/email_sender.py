"""
Sending email through the official Gmail API.

Your Google password is never asked for and never stored. You authorise the
app once in a browser; Google gives us a token file that only allows the two
scopes below.

    gmail.send      - send mail as you
    gmail.readonly  - read replies, so follow-up status can be updated

SAFETY
    TEST_MODE=true              -> nothing is ever transmitted. The complete
                                   message is written to data/outbox/ instead.
    ALLOW_REAL_SENDING=false    -> a second, independent brake.
    DAILY_SEND_LIMIT            -> hard stop for the day.
    SEND_RATE_LIMIT_SECONDS     -> minimum gap between two sends.
"""

from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from src.config import OUTBOX_DIR, settings
from src.logging_setup import get_logger
from src.models import PreparedMessage
from src.utils import looks_like_email, sha256, slugify, write_text

log = get_logger("email_sender")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

_last_send_at: float = 0.0


class SendError(RuntimeError):
    pass


@dataclass
class SendResult:
    ok: bool
    simulated: bool
    message_id: str = ""
    thread_id: str = ""
    error: str = ""
    outbox_file: str = ""


# --------------------------------------------------------------------------
# Gmail service
# --------------------------------------------------------------------------
_service = None


def gmail_service(interactive: bool = False):
    """
    Build an authorised Gmail client.

    `interactive=True` is allowed to open a browser window for the one-time
    consent screen. During a normal run it stays False, so a run can never
    hang waiting for a browser.
    """
    global _service
    if _service is not None:
        return _service

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise SendError(
            "Google libraries are missing. Run: pip install -r requirements.txt"
        ) from exc

    token_file: Path = settings.gmail_token_file
    creds_file: Path = settings.gmail_credentials_file
    creds = None

    if token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        except Exception as exc:
            log.warning("Stored Gmail token is unreadable (%s) - re-authorisation needed.", exc)
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:
            log.warning("Refreshing the Gmail token failed: %s", exc)
            creds = None

    if not creds or not creds.valid:
        if not interactive:
            raise SendError(
                "Gmail is not authorised yet. Run:  python -m src.main auth-gmail"
            )
        if not creds_file.exists():
            raise SendError(
                f"OAuth client file not found at {creds_file}.\n"
                "Download it from Google Cloud Console (APIs & Services -> Credentials ->\n"
                "Create OAuth client ID -> Desktop app -> Download JSON) and save it there."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")
        try:
            token_file.chmod(0o600)
        except OSError:
            pass  # Windows may refuse; the file is gitignored either way
        log.info("Gmail authorised. Token saved to %s", token_file)

    _service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return _service


def authorise_interactively() -> str:
    """Run the one-time browser consent flow. Returns the connected address."""
    service = gmail_service(interactive=True)
    profile = service.users().getProfile(userId="me").execute()
    address = profile.get("emailAddress", "")
    log.info("Gmail connected: %s", address)
    if settings.gmail_sender and address.lower() != settings.gmail_sender.lower():
        log.warning(
            "You authorised %s but GMAIL_SENDER in .env is %s. Update .env so they match.",
            address, settings.gmail_sender,
        )
    return address


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def validate_message(message: PreparedMessage) -> list[str]:
    """Everything that would make this message unsafe or embarrassing to send."""
    problems: list[str] = []

    if not message.to:
        problems.append("No recipient address.")
    for address in message.to + message.cc + message.bcc:
        if not looks_like_email(address):
            problems.append(f"Invalid email address: {address}")

    if not message.subject.strip():
        problems.append("Empty subject line.")
    if len(message.subject) > 200:
        problems.append("Subject line is unusually long.")
    if not message.body.strip():
        problems.append("Empty message body.")

    leftovers = re.findall(r"\{\{[^}]+\}\}", message.subject + message.body)
    if leftovers:
        problems.append(f"Unfilled placeholders remain: {', '.join(sorted(set(leftovers)))}")

    if "[SENDER_NAME not set" in message.body:
        problems.append("SENDER_NAME is not set in .env - your signature would be broken.")

    if not settings.gmail_sender:
        problems.append("GMAIL_SENDER is not set in .env.")

    # Same address twice across To/Cc/Bcc.
    everyone = [a.lower() for a in message.to + message.cc]
    if len(everyone) != len(set(everyone)):
        problems.append("The same address appears more than once in To/Cc.")

    if settings.gmail_sender and settings.gmail_sender.lower() in everyone:
        problems.append("You would be emailing yourself.")

    return problems


# --------------------------------------------------------------------------
# Sending
# --------------------------------------------------------------------------
def _build_mime(message: PreparedMessage) -> EmailMessage:
    mime = EmailMessage()
    from_name = settings.sender_name or settings.sender_company
    mime["From"] = f"{from_name} <{settings.gmail_sender}>" if from_name else settings.gmail_sender
    mime["To"] = ", ".join(message.to)
    if message.cc:
        mime["Cc"] = ", ".join(message.cc)
    if message.bcc:
        mime["Bcc"] = ", ".join(message.bcc)
    mime["Subject"] = message.subject
    mime.set_content(message.body)
    return mime


def _write_outbox(message: PreparedMessage, company: str, note: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = OUTBOX_DIR / f"{stamp}-{slugify(company)}.txt"
    contents = (
        f"{note}\n"
        f"{'=' * 70}\n"
        f"Generated : {datetime.now().isoformat(timespec='seconds')}\n"
        f"Channel   : {message.channel.value}\n"
        f"From      : {settings.gmail_sender or '(GMAIL_SENDER not set)'}\n"
        f"To        : {', '.join(message.to)}\n"
        f"Cc        : {', '.join(message.cc) or '-'}\n"
        f"Bcc       : {', '.join(message.bcc) or '-'}\n"
        f"Subject   : {message.subject}\n"
        f"{'=' * 70}\n\n"
        f"{message.body}\n"
    )
    write_text(path, contents)
    return path


def _rate_limit() -> None:
    global _last_send_at
    gap = settings.send_rate_limit_seconds
    if gap <= 0 or _last_send_at == 0:
        _last_send_at = time.time()
        return
    waited = time.time() - _last_send_at
    if waited < gap:
        remaining = gap - waited
        log.info("Rate limit: waiting %.0f s before the next send.", remaining)
        time.sleep(remaining)
    _last_send_at = time.time()


def send(message: PreparedMessage, company: str, force_simulate: bool = False) -> SendResult:
    """
    Send one email - or simulate it.

    Never sends unless TEST_MODE=false AND ALLOW_REAL_SENDING=true.
    """
    problems = validate_message(message)
    if problems:
        return SendResult(ok=False, simulated=True, error="; ".join(problems))

    simulate = force_simulate or not settings.can_send_for_real

    if simulate:
        reason = (
            "SIMULATED - TEST_MODE=true, nothing was sent."
            if settings.test_mode
            else "SIMULATED - ALLOW_REAL_SENDING=false, nothing was sent."
        )
        path = _write_outbox(message, company, reason)
        log.info("[SIMULATED] Email for %s written to %s", company, path.name)
        return SendResult(ok=True, simulated=True, outbox_file=str(path))

    from src.duplicate_checker import sends_today

    if sends_today() >= settings.daily_send_limit:
        return SendResult(
            ok=False, simulated=False,
            error=f"Daily send limit reached ({settings.daily_send_limit}). Try again tomorrow.",
        )

    try:
        service = gmail_service(interactive=False)
        _rate_limit()
        mime = _build_mime(message)
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except SendError:
        raise
    except Exception as exc:
        log.exception("Gmail send failed for %s", company)
        return SendResult(ok=False, simulated=False, error=str(exc)[:400])

    path = _write_outbox(message, company, f"SENT via Gmail (id {sent.get('id')})")
    log.info("Email SENT to %s for %s (Gmail id %s)", ", ".join(message.to), company, sent.get("id"))
    return SendResult(
        ok=True,
        simulated=False,
        message_id=sent.get("id", ""),
        thread_id=sent.get("threadId", ""),
        outbox_file=str(path),
    )


def message_fingerprint(message: PreparedMessage) -> str:
    return sha256(f"{sorted(message.to)}|{message.subject}|{message.body}")


# --------------------------------------------------------------------------
# Reading replies (used by `python -m src.main replies`)
# --------------------------------------------------------------------------
def _decode_part(part: dict) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data.encode("ascii")).decode("utf-8", "replace")
    except Exception:
        return ""


def _extract_body(payload: dict) -> str:
    if payload.get("mimeType", "").startswith("text/plain"):
        return _decode_part(payload)
    for part in payload.get("parts", []) or []:
        text = _extract_body(part)
        if text.strip():
            return text
    if payload.get("mimeType", "").startswith("text/html"):
        from bs4 import BeautifulSoup

        return BeautifulSoup(_decode_part(payload), "lxml").get_text("\n", strip=True)
    return ""


def fetch_recent_replies(days: int = 30, max_results: int = 100) -> list[dict]:
    """
    Return inbox messages from the last N days as
    {from, from_email, subject, date, body, thread_id}.
    """
    service = gmail_service(interactive=False)
    query = f"in:inbox newer_than:{max(days, 1)}d -category:promotions -category:social"
    listing = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )

    out: list[dict] = []
    for item in listing.get("messages", []):
        try:
            full = (
                service.users()
                .messages()
                .get(userId="me", id=item["id"], format="full")
                .execute()
            )
        except Exception as exc:
            log.debug("Could not read message %s: %s", item["id"], exc)
            continue

        headers = {h["name"].lower(): h["value"] for h in full.get("payload", {}).get("headers", [])}
        sender = headers.get("from", "")
        match = re.search(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+", sender)
        out.append(
            {
                "id": item["id"],
                "thread_id": full.get("threadId", ""),
                "from": sender,
                "from_email": (match.group(0).lower() if match else ""),
                "subject": headers.get("subject", ""),
                "date": headers.get("date", ""),
                "body": _extract_body(full.get("payload", {}))[:8000],
                "snippet": full.get("snippet", ""),
            }
        )
    return out

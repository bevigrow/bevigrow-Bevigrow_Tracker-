"""Reading the mailbox, and attaching what arrives to the right company.

The outbound half of this application sends over HTTPS because the host blocks
the SMTP ports. The inbound half uses IMAP, because port 993 *is* reachable
from here — measured against the live server rather than assumed.

Three rules shape everything below.

**A message is processed exactly once.** The sender's own Message-ID is stored
with a unique constraint, so a second sighting is refused by the database
rather than by remembering to check. The inbox is polled repeatedly and a reply
that counted twice would inflate the reply rate and every chart built on it.

**A reply is attached to a company only on evidence.** The strong signal is the
`In-Reply-To` header quoting a Message-ID this application generated when it
sent the original — that is proof, not inference. The weaker one is the sender
being an address we wrote to. Anything less stays `unmatched` and waits for a
person, because attaching a reply to the wrong company is worse than attaching
it to none.

**Nothing is ever sent from here.** A reply can change a status, stop a
follow-up and be summarised in a line. It can never be answered: no function
in this module composes or sends a message to a customer, and none should be
added. BeviGrow replies to its customers by hand, in Gmail.
"""
from __future__ import annotations

import email
import imaplib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    EmailAccount,
    InboundReply,
    Outreach,
    OutreachStatus,
    ReplyClass,
    ReplyMatch,
    SendLedger,
)
from . import ai
from . import campaigns as cm
from .sender import decrypt_password

log = logging.getLogger("bevigrow.replies")

# How far back to look on a normal poll. Generous, because the same message
# arriving twice is refused by the unique index anyway, and a missed reply is
# far more costly than a wasted comparison.
LOOKBACK_DAYS = 14

# Senders that are machinery, not customers.
_ROBOTS = (
    "mailer-daemon",
    "postmaster",
    "no-reply",
    "noreply",
    "donotreply",
    "bounce",
)

_QUOTE_MARKERS = (
    re.compile(r"^\s*On .{5,120}\bwrote:\s*$", re.M),
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.M | re.I),
    re.compile(r"^\s*_{5,}\s*$", re.M),
    re.compile(r"^\s*From:\s.+$", re.M),
    re.compile(r"^\s*Am .{5,80}schrieb\b.*$", re.M),   # German clients
)


@dataclass
class SyncResult:
    checked: int = 0
    stored: int = 0
    matched: int = 0
    unmatched: int = 0
    skipped: int = 0
    ai_reads: int = 0
    error: str | None = None


# ------------------------------------------------------------------ helpers


def _decode(raw: str | None) -> str:
    """Header text as a person wrote it, not as MIME encoded it."""
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw))).strip()
    except Exception:  # noqa: BLE001 - a malformed header must not stop a sync
        return raw.strip()


def _ids(raw: str | None) -> list[str]:
    """Every <message-id> in a header, in order."""
    return re.findall(r"<[^<>@\s]+@[^<>\s]+>", raw or "")


def strip_quoted(text: str) -> str:
    """Just the part they typed.

    Everything under "On … wrote:" is our own email quoted back, which is
    already stored on the outreach record it is quoting. Keeping it would
    double the size of every row and bury the two lines that matter.
    """
    cleaned = (text or "").replace("\r\n", "\n")
    cut = len(cleaned)
    for marker in _QUOTE_MARKERS:
        found = marker.search(cleaned)
        if found and found.start() < cut:
            cut = found.start()
    trimmed = cleaned[:cut].strip()
    # A reply that is *only* quoted text is better kept whole than blanked.
    return trimmed or cleaned.strip()


def _body_of(message: email.message.Message) -> str:
    """The plain-text body, falling back to HTML with the tags taken out."""
    plain, html = "", ""
    for part in message.walk() if message.is_multipart() else [message]:
        if part.get_content_maintype() == "multipart":
            continue
        disposition = str(part.get("Content-Disposition") or "")
        if "attachment" in disposition.lower():
            continue
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            text = payload.decode(part.get_content_charset() or "utf-8", "replace")
        except Exception:  # noqa: BLE001 - one unreadable part is not a failure
            continue
        if part.get_content_type() == "text/plain" and not plain:
            plain = text
        elif part.get_content_type() == "text/html" and not html:
            html = text
    if plain:
        return plain
    if html:
        without_tags = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
        without_tags = re.sub(r"<br\s*/?>|</p>", "\n", without_tags, flags=re.I)
        return re.sub(r"<[^>]+>", "", without_tags)
    return ""


# ------------------------------------------------------------- classification


_RULES: list[tuple[ReplyClass, re.Pattern]] = [
    (ReplyClass.out_of_office, re.compile(
        r"out of (the )?office|annual leave|on holiday|auto[- ]?reply|abwesenheit|"
        r"vacation|maternity|currently away", re.I)),
    (ReplyClass.unsubscribe, re.compile(
        r"unsubscribe|remove me|opt[- ]?out|do not contact|stop emailing|"
        r"take me off", re.I)),
    (ReplyClass.not_interested, re.compile(
        r"not interested|no thanks|no,? thank you|we are covered|already have a supplier|"
        r"kein interesse|not looking", re.I)),
    (ReplyClass.sample_request, re.compile(r"\bsamples?\b|muster|send.{0,20}sample", re.I)),
    (ReplyClass.pricing_request, re.compile(
        r"\bpric(e|ing|es)\b|\bquote\b|\bquotation\b|\boffer\b|cost per|preis", re.I)),
    (ReplyClass.specification_request, re.compile(
        r"specification|\bspec sheet\b|\bspecs?\b|data ?sheet|moisture|screen size|"
        r"cupping", re.I)),
    (ReplyClass.purchasing_contact, re.compile(
        r"forward(ed)? (this|your).{0,30}(to|colleague)|purchasing (team|department)|"
        r"please contact|my colleague|einkauf", re.I)),
    (ReplyClass.interested, re.compile(
        r"\binterested\b|sounds good|tell me more|would like to know|please send|"
        r"happy to (discuss|hear)", re.I)),
]


# How many replies one sync will spend a model call on. A normal sync brings
# back nothing or a handful; this only exists so that a mailbox left unread
# for a fortnight cannot turn one sync into a hundred requests.
AI_READS_PER_SYNC = 12


def read_with_ai(
    subject: str, body: str, rules_label: ReplyClass
) -> tuple[ReplyClass, str, str | None]:
    """Refine the rules verdict with the model, and get a one-line summary.

    Returns (classification, decided_by, summary). The rules result stands
    unless the model returns a label that is actually one of ours, so the
    worst an unavailable or confused model can do is leave things as they
    were. No draft reply is produced here or anywhere else.
    """
    label, summary, used_ai = ai.read_reply(subject, body, None, rules_label.value)
    if not used_ai:
        return rules_label, "rules", None
    try:
        refined = ReplyClass(label)
    except ValueError:
        refined = rules_label
    return refined, "ai" if refined is not rules_label else "ai-agreed", summary


def classify(subject: str, body: str, from_email: str) -> tuple[ReplyClass, str]:
    """What this reply appears to be. Rules first, and rules are usually enough.

    Returns the class and how it was decided, so a wrong call can be traced to
    a rule rather than argued about. Deliberately ordered: an out-of-office
    that mentions pricing is still an out-of-office, and an unsubscribe beats
    everything except that.
    """
    text = f"{subject}\n{body}"[:4000]
    if any(robot in (from_email or "").lower() for robot in _ROBOTS):
        return ReplyClass.bounced, "sender"
    for label, pattern in _RULES:
        if pattern.search(text):
            return label, "rules"
    return ReplyClass.other, "rules"


# ------------------------------------------------------------------ matching


def _match(db: Session, message_ids: list[str], from_email: str) -> tuple[ReplyMatch, Outreach | None, int | None]:
    """Which outreach record this reply belongs to, and how sure we are.

    Order matters. The thread header is proof: it contains a Message-ID this
    application invented when it sent the original, so nothing else could be
    quoting it. The address is only evidence — people forward, alias and reply
    from a different mailbox — and it is used only when the header is absent.
    """
    for candidate in message_ids:
        ledger = db.scalar(
            select(SendLedger).where(SendLedger.message_id == candidate).limit(1)
        )
        if ledger is None:
            continue
        row = None
        if ledger.email:
            row = db.scalar(
                select(Outreach)
                .where(func.lower(func.trim(Outreach.email)) == ledger.email.strip().casefold())
                .order_by(Outreach.contacted_on.desc().nullslast())
                .limit(1)
            )
        return ReplyMatch.thread, row, ledger.campaign_id

    address = (from_email or "").strip().casefold()
    if address:
        row = db.scalar(
            select(Outreach)
            .where(func.lower(func.trim(Outreach.email)) == address)
            .order_by(Outreach.contacted_on.desc().nullslast())
            .limit(1)
        )
        if row is not None:
            return ReplyMatch.address, row, None

    return ReplyMatch.unmatched, None, None


def apply_to_outreach(db: Session, reply: InboundReply, row: Outreach) -> None:
    """Record the reply on the company's own log entry.

    Also clears the follow-up date. A customer who has answered and then
    receives an automated chase is the exact embarrassment this whole system is
    built to avoid, and the follow-up builder skips anybody marked replied.
    """
    reply.outreach_id = row.id
    reply.company_name = row.company_name

    # Bounces and auto-replies are not replies. Marking an out-of-office as a
    # reply would take the company out of the follow-up list on the strength of
    # a robot saying its owner is in Spain.
    if reply.classification in (ReplyClass.bounced, ReplyClass.out_of_office):
        if reply.classification == ReplyClass.bounced:
            row.status = OutreachStatus.no_response
            row.next_action = "Address bounced — check it before writing again"
            row.next_follow_up = None
        return

    row.status = OutreachStatus.replied
    row.replied_on = cm.sending_day(reply.received_at)
    row.next_follow_up = None
    row.next_action = "They replied — read it and decide"
    snippet = (reply.body or "").strip()
    if snippet:
        row.their_reply = snippet[:4000]
    if reply.classification == ReplyClass.unsubscribe:
        row.status = OutreachStatus.not_interested
        row.next_action = "Asked not to be contacted again"


# ------------------------------------------------------------------- the poll


def _connect(account: EmailAccount) -> imaplib.IMAP4_SSL:
    password = decrypt_password(account.imap_password_enc)
    if not password:
        raise RuntimeError("No mailbox password stored for reading replies.")
    box = imaplib.IMAP4_SSL(account.imap_host, account.imap_port, timeout=30)
    box.login(account.imap_user or account.from_email, password)
    return box


def check_connection(account: EmailAccount) -> str | None:
    """Log in, list nothing, hang up. Returns an error message or None."""
    try:
        box = _connect(account)
        try:
            box.select("INBOX", readonly=True)
        finally:
            box.logout()
        return None
    except imaplib.IMAP4.error as exc:
        return (
            "The mailbox rejected the sign-in. Use a 16-character App Password "
            f"with 2-Step Verification on. ({exc})"
        )[:400]
    except Exception as exc:  # noqa: BLE001 - never surface IMAP internals raw
        return f"Could not reach {account.imap_host}: {exc}"[:400]


def sync(db: Session, account: EmailAccount, *, days: int = LOOKBACK_DAYS) -> SyncResult:
    """Read recent mail, store what is new, attach what can be attached."""
    result = SyncResult()
    try:
        box = _connect(account)
    except Exception as exc:  # noqa: BLE001
        result.error = str(exc)[:400]
        account.last_reply_error = result.error
        db.commit()
        return result

    # Anything filed as unmatched was stored by an earlier version that kept
    # the whole inbox. It is unrelated mail by definition — a message that
    # genuinely belongs to a company is matched by thread or by address, and
    # one assigned by hand is `manual`, not `unmatched`. Clearing it here
    # means the first sync after this change tidies up after the last one.
    pruned = db.query(InboundReply).filter(
        InboundReply.match_kind == ReplyMatch.unmatched
    ).delete(synchronize_session=False)
    if pruned:
        log.info("Discarded %d unrelated message(s) kept by an earlier sync", pruned)
        db.commit()

    try:
        box.select("INBOX", readonly=True)
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
        status, data = box.search(None, f'(SINCE "{since}")')
        if status != "OK":
            result.error = "The mailbox refused the search."
            return result

        uids = (data[0] or b"").split()
        result.checked = len(uids)
        # Newest first, and bounded: a mailbox with years of history should not
        # make the first sync take minutes.
        for uid in reversed(uids[-400:]):
            try:
                _ingest_one(db, box, uid, result)
            except Exception as exc:  # noqa: BLE001 - one bad message, not a bad sync
                log.warning("Could not process message %s: %s", uid, exc)
                result.skipped += 1
        account.last_reply_check_at = datetime.now(timezone.utc)
        account.last_reply_error = None
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        result.error = f"{type(exc).__name__}: {exc}"[:400]
        account.last_reply_error = result.error
        db.commit()
    finally:
        try:
            box.logout()
        except Exception:  # noqa: BLE001 - closing a dead socket is not news
            pass
    return result


def _ingest_one(db: Session, box: imaplib.IMAP4_SSL, uid: bytes, result: SyncResult) -> None:
    status, payload = box.fetch(uid, "(RFC822)")
    if status != "OK" or not payload or not isinstance(payload[0], tuple):
        result.skipped += 1
        return

    message = email.message_from_bytes(payload[0][1])
    message_id = (_ids(message.get("Message-ID")) or [""])[0]
    if not message_id:
        # Without an id there is no way to avoid storing it again tomorrow.
        result.skipped += 1
        return

    if db.scalar(select(InboundReply.id).where(InboundReply.message_id == message_id)):
        result.skipped += 1
        return

    from_name, from_email = parseaddr(_decode(message.get("From")))
    subject = _decode(message.get("Subject"))[:400]
    body = strip_quoted(_body_of(message))[:20000]

    try:
        received = parsedate_to_datetime(message.get("Date"))
        if received.tzinfo is None:
            received = received.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        received = datetime.now(timezone.utc)

    # Match first, and keep nothing that does not match.
    #
    # This mailbox is a person's inbox, not a channel dedicated to outreach.
    # Fourteen days of it is mostly newsletters, invoices and private mail.
    # Storing all of that and labelling it "unmatched" would bury the four
    # replies that matter under two hundred that do not, so a message earns a
    # row only by answering something this application sent: either it quotes
    # a Message-ID we generated, or it comes from an address we wrote to.
    # Everything else is left where it belongs, in Gmail, unread by us.
    references = _ids(message.get("References")) + _ids(message.get("In-Reply-To"))
    kind, row, campaign_id = _match(db, references, from_email)
    if kind is ReplyMatch.unmatched:
        result.skipped += 1
        return

    # An automated response says so in a header long before its wording does.
    auto = (message.get("Auto-Submitted") or "").lower()
    precedence = (message.get("Precedence") or "").lower()

    label, how = classify(subject, body, from_email)
    if auto.startswith("auto-") and label is ReplyClass.other:
        label, how = ReplyClass.out_of_office, "header"
    if precedence in ("bulk", "list") and label is ReplyClass.other:
        label, how = ReplyClass.other, "header"

    # The model reads it second, on top of the rules. Away messages and
    # delivery failures are skipped: the headers already settled those, and
    # there is nothing in them worth a sentence.
    summary: str | None = None
    if (
        label not in (ReplyClass.out_of_office, ReplyClass.bounced)
        and result.ai_reads < AI_READS_PER_SYNC
    ):
        result.ai_reads += 1
        label, how, summary = read_with_ai(subject, body, label)

    reply = InboundReply(
        message_id=message_id,
        in_reply_to=(_ids(message.get("In-Reply-To")) or [None])[0],
        thread_refs=" ".join(references)[:2000] or None,
        from_email=(from_email or "").strip().lower()[:255] or None,
        from_name=from_name[:200] or None,
        to_email=(parseaddr(_decode(message.get("To")))[1] or "")[:255] or None,
        subject=subject,
        received_at=received,
        body=body,
        match_kind=kind,
        campaign_id=campaign_id,
        classification=label,
        classified_by=how,
        suggested_reply=summary,
    )
    db.add(reply)
    db.flush()

    if row is not None:
        apply_to_outreach(db, reply, row)
        result.matched += 1
    else:
        result.unmatched += 1
    result.stored += 1
    db.commit()

# ---------------------------------------------------------------------------
# There is deliberately no function here that answers a customer.
#
# The application reads replies, files them against the right company and
# stops chasing that company. Writing back is done in Gmail, by a person, in
# the thread the customer is already looking at. That is a decision, not an
# omission: an automated system that can compose and send business email is
# one bad classification away from promising a price, and the cheapest way to
# make that impossible is to give it no way to send at all.
# ---------------------------------------------------------------------------

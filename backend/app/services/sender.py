"""Sending campaign email through the operator's own mailbox.

Gmail over SMTP with an app password, deliberately, rather than the Gmail API:
reading replies later needs `gmail.readonly`, which Google classifies as a
*restricted* scope and which requires a security assessment for an app that
stores message content on a server. An unverified app also expires its refresh
token every seven days. An app password costs ten minutes and nothing else, and
because the mail genuinely leaves your mailbox, replies come back to it
normally and appear in Sent alongside everything you type by hand.

The password is encrypted at rest with a key derived from JWT_SECRET, and is
never returned by an endpoint, never logged, and never included in an error.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import smtplib
import ssl
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from cryptography.fernet import Fernet, InvalidToken

from ..config import settings
from ..models import EmailAccount

log = logging.getLogger("bevigrow.sender")


# --------------------------------------------------------------- credentials


def _fernet() -> Fernet:
    """A key derived from JWT_SECRET, so there is one secret to look after.

    The consequence, which is worth knowing before it bites: rotate JWT_SECRET
    and stored passwords become unreadable. That is recoverable — re-enter the
    app password — and it is better than a second secret nobody remembers to
    set, which would silently fall back to a hard-coded default.
    """
    digest = hashlib.sha256(settings.JWT_SECRET.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_password(plain: str) -> bytes:
    return _fernet().encrypt(plain.encode("utf-8"))


def decrypt_password(blob: bytes | None) -> str | None:
    if not blob:
        return None
    try:
        return _fernet().decrypt(blob).decode("utf-8")
    except InvalidToken:
        # Almost always JWT_SECRET having changed since the password was saved.
        log.error("Stored SMTP password could not be decrypted; re-enter it in Settings.")
        return None


# ------------------------------------------------------------------ sending


@dataclass
class SendOutcome:
    """What happened, in the terms the queue records."""

    ok: bool
    message_id: str | None = None
    error: str | None = None
    # True when the failure is about this one recipient (bad address) rather
    # than the connection. The queue keeps going on the first, stops on the
    # second — a wrong password would otherwise burn through the whole list
    # marking every company as failed.
    recipient_fault: bool = False
    auth_fault: bool = False


class NoAccount(Exception):
    """No mailbox is configured to send from."""


def _connect(account: EmailAccount, password: str) -> smtplib.SMTP:
    context = ssl.create_default_context()
    if account.smtp_port == 465:
        smtp = smtplib.SMTP_SSL(account.smtp_host, account.smtp_port, timeout=30, context=context)
    else:
        smtp = smtplib.SMTP(account.smtp_host, account.smtp_port, timeout=30)
        if account.use_starttls:
            smtp.starttls(context=context)
    smtp.login(account.smtp_user or account.from_email, password)
    return smtp


def verify(account: EmailAccount) -> SendOutcome:
    """Log in and hang up. Proves the password before a campaign relies on it.

    Worth its own step: an app password that was mistyped fails identically to
    one that was revoked, and finding that out on company number one of two
    hundred is a bad way to learn it.
    """
    password = decrypt_password(account.smtp_password_enc)
    if not password:
        return SendOutcome(ok=False, error="No password stored for this mailbox.", auth_fault=True)
    try:
        smtp = _connect(account, password)
        smtp.quit()
        return SendOutcome(ok=True)
    except smtplib.SMTPAuthenticationError:
        return SendOutcome(
            ok=False,
            auth_fault=True,
            error=(
                "Gmail rejected the sign-in. Use a 16-character App Password "
                "(not your account password), with 2-Step Verification switched on."
            ),
        )
    except Exception as exc:  # noqa: BLE001 - never surface SMTP internals
        return SendOutcome(ok=False, error=f"Could not reach {account.smtp_host}: {exc}"[:400])


def build_message(
    account: EmailAccount,
    to_email: str,
    subject: str,
    body: str,
    message_id: str | None = None,
) -> EmailMessage:
    """One plain-text message, with the Message-ID we chose.

    Plain text on purpose. A cold first email that arrives as HTML with a
    tracking pixel is markedly more likely to be filtered, and this one is
    meant to look like a person wrote it — because a person did, once, and the
    rest is filling in a name.
    """
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((account.from_name or "", account.from_email))
    message["To"] = to_email
    message["Message-ID"] = message_id or make_msgid(domain=account.from_email.split("@")[-1])
    message.set_content(body)
    return message


def new_message_id(account: EmailAccount) -> str:
    """Allocated before the send so it can be written down first.

    SMTP gives back no identifier of its own, so the only way to answer "did
    this actually go?" after a crash is to have chosen the id in advance and
    stored it. It is also what lets a reply be matched to its outreach row
    later, through In-Reply-To.
    """
    domain = account.from_email.split("@")[-1] if "@" in account.from_email else "bevigrow.local"
    return make_msgid(idstring=uuid.uuid4().hex[:12], domain=domain)


def send(account: EmailAccount, to_email: str, subject: str, body: str, message_id: str) -> SendOutcome:
    """Deliver one message. The caller has already recorded the attempt."""
    password = decrypt_password(account.smtp_password_enc)
    if not password:
        return SendOutcome(ok=False, auth_fault=True, error="No password stored for this mailbox.")

    message = build_message(account, to_email, subject, body, message_id)
    try:
        smtp = _connect(account, password)
    except smtplib.SMTPAuthenticationError:
        return SendOutcome(
            ok=False,
            auth_fault=True,
            error="Gmail rejected the sign-in. Check the App Password in Settings.",
        )
    except Exception as exc:  # noqa: BLE001
        return SendOutcome(ok=False, error=f"Could not connect: {exc}"[:400])

    try:
        refused = smtp.send_message(message)
        if refused:
            # send_message returns the recipients the server would not take.
            return SendOutcome(
                ok=False,
                recipient_fault=True,
                error=f"The mail server refused {to_email}: {list(refused.values())[0]}"[:400],
            )
        return SendOutcome(ok=True, message_id=message_id)
    except smtplib.SMTPRecipientsRefused as exc:
        return SendOutcome(ok=False, recipient_fault=True, error=f"Address refused: {exc}"[:400])
    except smtplib.SMTPSenderRefused as exc:
        return SendOutcome(ok=False, auth_fault=True, error=f"Sender refused: {exc}"[:400])
    except smtplib.SMTPDataError as exc:
        # 550/554 here is usually the account being rate-limited or flagged.
        return SendOutcome(ok=False, error=f"The mail server rejected the message: {exc}"[:400])
    except Exception as exc:  # noqa: BLE001
        return SendOutcome(ok=False, error=f"Send failed: {exc}"[:400])
    finally:
        try:
            smtp.quit()
        except Exception:  # noqa: BLE001 - closing a dead socket is not news
            pass

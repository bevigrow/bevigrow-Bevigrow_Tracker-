"""Getting one email out of the building.

Three ways, because the obvious one is not always available.

**SMTP** is the best of them when the host allows it. The message leaves the
operator's own mailbox, appears in their Sent folder, and replies come back
with no forwarding tricks or alignment problems. It needs an app password and
an outbound connection on port 587 or 465.

That connection is the catch. Render stopped allowing outbound traffic to ports
25, 465 and 587 from free web services in September 2025, so on that plan a
connection to smtp.gmail.com fails with "network is unreachable" before any
password is checked — which reads exactly like a wrong password and is not one.

**Resend** and **Brevo** send the same message as a JSON POST over port 443,
which nothing blocks. The trade is where the mail appears to come from: the
sending domain has to be one the provider will vouch for, so it is worth
sending as an address at a domain you own and setting Reply-To to the mailbox
you actually read. Replies then arrive where you expect them; the sent copy
does not appear in your Sent folder, because it never went through it.

The password or key is encrypted at rest with a key derived from JWT_SECRET and
is never returned by an endpoint, never logged, and never put in an error.
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

import httpx
from cryptography.fernet import Fernet, InvalidToken

from ..config import settings
from ..models import EmailAccount, MailProvider

log = logging.getLogger("bevigrow.sender")

# Generous: a first call may be waking a sleeping provider edge, and a send
# that times out is recorded as unverified, which is a person's problem to
# untangle. Better to wait.
HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


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
    # The id the provider gave it, when there is one. Ours is the
    # Message-ID header; theirs is what their dashboard searches by.
    provider_response: str | None = None


class NoAccount(Exception):
    """No mailbox is configured to send from."""


def _unreachable(account: EmailAccount, exc: OSError) -> str:
    """Say what "network is unreachable" actually means here.

    It is the single most misleading error this application can produce. The
    host refuses the outbound connection, so the failure happens before Gmail
    is ever asked about the password — and it looks, to anyone reading it, like
    the password is wrong. People then generate a new App Password, which fails
    identically, and conclude the app is broken.
    """
    blocked_port = account.smtp_port in (25, 465, 587)
    if blocked_port and getattr(exc, "errno", None) in (101, 99, 111, 110, 10051, 10060):
        return (
            f"The server cannot open a connection to {account.smtp_host}:{account.smtp_port}. "
            "This is the host blocking outbound mail ports, not a problem with your "
            "App Password — Render free instances stopped allowing ports 25, 465 and 587 "
            "in September 2025. Either switch this mailbox to Resend or Brevo above "
            "(they send over HTTPS, which is not blocked), or upgrade the backend to a "
            "paid Render instance to keep using Gmail directly."
        )
    return f"Could not reach {account.smtp_host}: {exc}"[:400]


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
    """Prove the credentials before a campaign relies on them.

    Worth its own step: an app password that was mistyped fails identically to
    one that was revoked, and finding that out on company number one of two
    hundred is a bad way to learn it.
    """
    if account.provider in (MailProvider.resend, MailProvider.brevo):
        return _verify_http(account)

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
    except OSError as exc:
        return SendOutcome(ok=False, error=_unreachable(account, exc), auth_fault=True)
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
    """Deliver one message, however this account is configured to deliver it."""
    if account.provider == MailProvider.resend:
        return _send_resend(account, to_email, subject, body, message_id)
    if account.provider == MailProvider.brevo:
        return _send_brevo(account, to_email, subject, body, message_id)
    return _send_smtp(account, to_email, subject, body, message_id)


# ----------------------------------------------------------- http providers
#
# Both of these are one JSON POST over port 443, which is the entire reason
# they are here: the hosting plan blocks the SMTP ports outright, so a mail
# path that looks like any other API call is the only one that leaves.


def _http_error(name: str, status: int, text: str) -> SendOutcome:
    """Turn a provider's refusal into the two things the queue cares about.

    Which failures stop the campaign and which only mark one company. A bad key
    stops everything, because the next hundred sends would fail identically. A
    rejected address is that address's problem alone.
    """
    detail = text.strip()[:300]
    if status in (401, 403):
        return SendOutcome(
            ok=False,
            auth_fault=True,
            error=f"{name} rejected the API key ({status}). Check it in Settings. {detail}",
        )
    if status == 422 or "invalid" in detail.lower() and "email" in detail.lower():
        return SendOutcome(ok=False, recipient_fault=True, error=f"{name} refused the address: {detail}")
    if status == 429:
        return SendOutcome(ok=False, error=f"{name} is rate limiting: {detail}")
    return SendOutcome(ok=False, error=f"{name} returned {status}: {detail}")


def _send_resend(account, to_email: str, subject: str, body: str, message_id: str) -> SendOutcome:
    key = decrypt_password(account.api_key_enc)
    if not key:
        return SendOutcome(ok=False, auth_fault=True, error="No Resend API key stored.")
    payload = {
        "from": (
            f"{account.from_name} <{account.from_email}>" if account.from_name else account.from_email
        ),
        "to": [to_email],
        "subject": subject,
        "text": body,
        "headers": {"Message-ID": message_id},
    }
    if account.reply_to:
        payload["reply_to"] = account.reply_to
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            res = client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        return SendOutcome(ok=False, error=f"Could not reach Resend: {exc}"[:400])
    if res.status_code >= 400:
        return _http_error("Resend", res.status_code, res.text)
    # Resend allocates its own id; keeping it alongside ours is what makes a
    # message findable in their dashboard when a delivery is questioned.
    provider_id = ""
    try:
        provider_id = str(res.json().get("id", ""))
    except ValueError:
        pass
    return SendOutcome(ok=True, message_id=message_id, provider_response=provider_id[:200])


def _send_brevo(account, to_email: str, subject: str, body: str, message_id: str) -> SendOutcome:
    key = decrypt_password(account.api_key_enc)
    if not key:
        return SendOutcome(ok=False, auth_fault=True, error="No Brevo API key stored.")
    payload = {
        "sender": {"email": account.from_email, "name": account.from_name or account.from_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body,
        "headers": {"Message-ID": message_id},
    }
    if account.reply_to:
        payload["replyTo"] = {"email": account.reply_to}
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            res = client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": key, "accept": "application/json"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        return SendOutcome(ok=False, error=f"Could not reach Brevo: {exc}"[:400])
    if res.status_code >= 400:
        return _http_error("Brevo", res.status_code, res.text)
    provider_id = ""
    try:
        provider_id = str(res.json().get("messageId", ""))
    except ValueError:
        pass
    return SendOutcome(ok=True, message_id=message_id, provider_response=provider_id[:200])


def _send_smtp(account: EmailAccount, to_email: str, subject: str, body: str, message_id: str) -> SendOutcome:
    """The original path. Needs a host that allows outbound port 587 or 465."""
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


def _verify_http(account: EmailAccount) -> SendOutcome:
    """Ask the provider who we are. No mail is sent.

    Each has a cheap authenticated endpoint that answers only for a good key,
    which is exactly what "test this before a campaign relies on it" needs.
    """
    key = decrypt_password(account.api_key_enc)
    if not key:
        return SendOutcome(ok=False, auth_fault=True, error="No API key stored.")
    if account.provider == MailProvider.resend:
        url, headers = "https://api.resend.com/domains", {"Authorization": f"Bearer {key}"}
        name = "Resend"
    else:
        url, headers = "https://api.brevo.com/v3/account", {"api-key": key, "accept": "application/json"}
        name = "Brevo"
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            res = client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        return SendOutcome(ok=False, error=f"Could not reach {name}: {exc}"[:400])
    if res.status_code == 401:
        return SendOutcome(ok=False, auth_fault=True, error=f"{name} rejected that API key.")
    if res.status_code == 403:
        # The key is real; it simply may not list domains. Resend keys created
        # with "Sending access" behave exactly like this, and calling a valid
        # key rejected would send somebody off to make another one that failed
        # the same way. It answered us, which is what was being tested.
        log.info("%s key is valid but restricted (403 on %s)", name, url)
        return SendOutcome(ok=True)
    if res.status_code >= 400:
        return _http_error(name, res.status_code, res.text)
    return SendOutcome(ok=True)

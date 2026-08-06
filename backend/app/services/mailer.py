"""Outbound email for password-reset links.

SMTP is optional. When it is not configured the app does not fail — it reports
that no mail was sent, and an admin can still reset the password from the Team
page. That keeps the product usable without a mail provider.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from ..config import settings

log = logging.getLogger("bevigrow.mail")


def send_reset_email(to_email: str, name: str, reset_url: str) -> bool:
    """Send the reset link. Returns True only if it was actually delivered."""
    if not settings.smtp_enabled:
        # Never log the URL in production — it is a bearer credential.
        if not settings.is_production:
            log.info("SMTP not configured. Reset link for %s: %s", to_email, reset_url)
        return False

    message = EmailMessage()
    message["Subject"] = "Reset your BeviGrow password"
    message["From"] = settings.SMTP_FROM
    message["To"] = to_email
    message.set_content(
        f"Hello {name},\n\n"
        f"A password reset was requested for your BeviGrow account.\n\n"
        f"Open this link to choose a new password:\n{reset_url}\n\n"
        f"The link expires in {settings.RESET_TOKEN_TTL_MINUTES} minutes and can "
        f"be used once.\n\n"
        f"If you did not request this, you can ignore this email — your password "
        f"will not change.\n\n"
        f"BeviGrow Coffee B2B"
    )

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            if settings.SMTP_STARTTLS:
                smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
        log.info("Password reset email sent to %s", to_email)
        return True
    except Exception as exc:  # noqa: BLE001 - never surface SMTP internals to callers
        log.error("Could not send reset email to %s: %s", to_email, exc)
        return False

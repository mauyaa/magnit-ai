"""Transactional email delivery.

Two backends, chosen by configuration:

* **console** (default) — logs the message instead of sending. Development and CI
  never need SMTP credentials, and a misconfigured environment cannot silently mail
  real people.
* **smtp** — sends via SMTP over TLS.

Sending happens off the event loop in a worker thread: ``smtplib`` is blocking, and
awaiting it inline would stall every other request on the process.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.platform.config.settings import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """The message could not be handed to the mail transport."""


def _build_message(to: str, subject: str, text_body: str, html_body: str | None) -> EmailMessage:
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    return message


def _send_smtp(message: EmailMessage) -> None:
    host, port = settings.smtp_host, settings.smtp_port
    # Port 465 is implicit TLS; everything else negotiates STARTTLS.
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as client:
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)
        return

    with smtplib.SMTP(host, port, timeout=15) as client:
        client.ehlo()
        client.starttls()
        client.ehlo()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)


async def send_email(to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    """Send one transactional email.

    Raises :class:`EmailDeliveryError` on failure. Callers that must not fail the
    request because of a mail outage should catch it — see the note on enumeration
    safety in the auth service.
    """
    message = _build_message(to, subject, text_body, html_body)

    if settings.email_backend == "console":
        # Body included deliberately: in development the reset link is only
        # discoverable from the log.
        logger.info("[email:console] to=%s subject=%s\n%s", to, subject, text_body)
        return

    try:
        await asyncio.to_thread(_send_smtp, message)
        logger.info("Sent %r email to %s", subject, to)
    except Exception as exc:
        # Never log the body on failure: it contains a single-use token.
        logger.exception("Failed to send %r email to %s", subject, to)
        raise EmailDeliveryError(str(exc)) from exc

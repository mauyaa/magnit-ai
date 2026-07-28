"""Transactional email bodies.

Plain text is authoritative and always present; HTML is an enhancement. Links are
built from ``frontend_base_url`` so a token can never be sent pointing at an
attacker-supplied host.
"""

from __future__ import annotations

import html

from app.platform.config.settings import settings


def _link(path: str, token: str) -> str:
    from urllib.parse import quote

    return f"{settings.frontend_base_url.rstrip('/')}{path}?token={quote(token, safe='')}"


def verification_email(token: str, ttl_hours: int) -> tuple[str, str, str]:
    """Returns ``(subject, text, html)`` for an email-verification message."""
    url = _link("/verify-email", token)
    subject = "Confirm your MagnetAI email address"

    text = (
        "Welcome to MagnetAI.\n\n"
        "Confirm your email address by opening this link:\n"
        f"{url}\n\n"
        f"The link expires in {ttl_hours} hours.\n\n"
        "If you didn't create a MagnetAI account, you can ignore this email.\n"
    )

    body = (
        "<p>Welcome to MagnetAI.</p>"
        f'<p><a href="{html.escape(url, quote=True)}">Confirm your email address</a></p>'
        f"<p>The link expires in {ttl_hours} hours.</p>"
        "<p>If you didn't create a MagnetAI account, you can ignore this email.</p>"
    )
    return subject, text, body


def password_reset_email(token: str, ttl_minutes: int) -> tuple[str, str, str]:
    """Returns ``(subject, text, html)`` for a password-reset message."""
    url = _link("/reset-password", token)
    subject = "Reset your MagnetAI password"

    text = (
        "Someone requested a password reset for this MagnetAI account.\n\n"
        "Set a new password here:\n"
        f"{url}\n\n"
        f"The link expires in {ttl_minutes} minutes and can only be used once.\n\n"
        "If this wasn't you, no action is needed — your password has not changed.\n"
    )

    body = (
        "<p>Someone requested a password reset for this MagnetAI account.</p>"
        f'<p><a href="{html.escape(url, quote=True)}">Set a new password</a></p>'
        f"<p>The link expires in {ttl_minutes} minutes and can only be used once.</p>"
        "<p>If this wasn't you, no action is needed — your password has not changed.</p>"
    )
    return subject, text, body


def new_lead_email(
    *,
    lead_email: str,
    lead_name: str | None,
    widget_title: str,
    widget_id: str,
    score: int | None,
) -> tuple[str, str, str]:
    """Tell the owner that one of their tools just captured someone.

    The lead's address goes in the subject line on purpose. This is the one
    email in the product with a time-sensitive action attached — the reply is
    worth more within the hour — so the owner should be able to decide whether
    to act without opening anything.
    """
    who = f"{lead_name} <{lead_email}>" if lead_name else lead_email
    url = f"{settings.frontend_base_url.rstrip('/')}/dashboard/widgets/{widget_id}"
    scored = f"\nThey scored {score}.\n" if score is not None else ""

    subject = f"New lead: {lead_email}"

    text = (
        f"{who} just used your {widget_title}.\n"
        f"{scored}"
        f"\nReply to them directly at {lead_email}, "
        f"or see the full details here:\n{url}\n\n"
        "To stop these emails, turn off lead notifications in your account settings.\n"
    )

    safe_who = html.escape(who)
    body = (
        f"<p><strong>{safe_who}</strong> just used your "
        f"{html.escape(widget_title)}.</p>"
        + (f"<p>They scored {score}.</p>" if score is not None else "")
        + f'<p><a href="mailto:{html.escape(lead_email, quote=True)}">Reply to them</a> '
        f'or <a href="{html.escape(url, quote=True)}">see the full details</a>.</p>'
        "<p>To stop these emails, turn off lead notifications in your account settings.</p>"
    )
    return subject, text, body


def password_changed_email() -> tuple[str, str, str]:
    """Notification that a password changed.

    Sent so a victim of account takeover learns about it even though the attacker
    controls the session.
    """
    subject = "Your MagnetAI password was changed"
    text = (
        "The password for your MagnetAI account was just changed.\n\n"
        "If you did this, no action is needed.\n\n"
        "If you did not, reset your password immediately and contact support.\n"
    )
    body = (
        "<p>The password for your MagnetAI account was just changed.</p>"
        "<p>If you did this, no action is needed.</p>"
        "<p>If you did not, reset your password immediately and contact support.</p>"
    )
    return subject, text, body

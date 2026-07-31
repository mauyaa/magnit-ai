"""Customer-facing account email language."""

from app.platform.email.templates import (
    password_changed_email,
    password_reset_email,
    verification_email,
)


def _assert_magnitai_brand(message: tuple[str, str, str]) -> None:
    subject, text, html = message
    assert all("Magnitai" in part for part in (subject, text, html))
    assert all("MagnetAI" not in part for part in (subject, text, html))


def test_verification_email_uses_the_product_brand() -> None:
    _assert_magnitai_brand(verification_email("verify-token", 48))


def test_password_reset_email_uses_the_product_brand() -> None:
    _assert_magnitai_brand(password_reset_email("reset-token", 30))


def test_password_changed_email_uses_the_product_brand() -> None:
    _assert_magnitai_brand(password_changed_email())

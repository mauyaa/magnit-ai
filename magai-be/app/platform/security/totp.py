"""TOTP (RFC 6238) and recovery codes.

Implemented against the standard library rather than adding a dependency: TOTP is
an HMAC of a time counter, and the whole algorithm is a dozen lines. Any
authenticator app (Google Authenticator, 1Password, Aegis) interoperates.

Verification accepts the adjacent time steps as well as the current one, which
absorbs clock skew between the server and the user's phone — the single most common
cause of "my code doesn't work".
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from app.platform.config.settings import settings

# RFC 6238 defaults, and what every authenticator app assumes.
TIME_STEP_SECONDS = 30
CODE_DIGITS = 6
# One step either side: tolerates ~30s of skew without materially widening the
# window an attacker can guess within.
CLOCK_SKEW_STEPS = 1

RECOVERY_CODE_GROUPS = 2
RECOVERY_CODE_GROUP_LEN = 5
# Excludes look-alike characters (0/O, 1/I/L) so codes can be read off a screen.
_RECOVERY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_secret() -> str:
    """A fresh base32 TOTP secret (160 bits, per RFC 4226's recommendation)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _hotp(secret_b32: str, counter: int) -> str:
    # Re-pad: base32 decoding requires the padding that we strip for readability.
    padding = "=" * (-len(secret_b32) % 8)
    key = base64.b32decode(secret_b32.upper() + padding, casefold=True)

    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % (10**CODE_DIGITS)).zfill(CODE_DIGITS)


def current_code(secret_b32: str, at: float | None = None) -> str:
    """The code valid right now — used by tests and by enrolment confirmation."""
    counter = int((at if at is not None else time.time()) // TIME_STEP_SECONDS)
    return _hotp(secret_b32, counter)


def verify_code(secret_b32: str, code: str, at: float | None = None) -> bool:
    """Constant-time check of ``code`` against the current and adjacent steps."""
    candidate = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(candidate) != CODE_DIGITS:
        return False

    counter = int((at if at is not None else time.time()) // TIME_STEP_SECONDS)
    for offset in range(-CLOCK_SKEW_STEPS, CLOCK_SKEW_STEPS + 1):
        # compare_digest to avoid leaking how much of the code matched.
        if hmac.compare_digest(_hotp(secret_b32, counter + offset), candidate):
            return True
    return False


def provisioning_uri(secret_b32: str, account_email: str) -> str:
    """``otpauth://`` URI for an authenticator app to scan as a QR code.

    Returned to the client, which renders the QR itself — the secret never needs to
    traverse an image-generation service.
    """
    issuer = quote(settings.mfa_issuer, safe="")
    label = quote(f"{settings.mfa_issuer}:{account_email}", safe=":@")
    return (
        f"otpauth://totp/{label}"
        f"?secret={secret_b32}&issuer={issuer}"
        f"&algorithm=SHA1&digits={CODE_DIGITS}&period={TIME_STEP_SECONDS}"
    )


def generate_recovery_codes(count: int | None = None) -> list[str]:
    """Human-transcribable single-use codes, e.g. ``ABCDE-FGHJK``."""
    total = count or settings.mfa_recovery_code_count
    codes = []
    for _ in range(total):
        groups = [
            "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(RECOVERY_CODE_GROUP_LEN))
            for _ in range(RECOVERY_CODE_GROUPS)
        ]
        codes.append("-".join(groups))
    return codes


def normalize_recovery_code(code: str) -> str:
    """Canonical form for comparison: upper-case, dashes and spaces removed."""
    return "".join(ch for ch in str(code or "").upper() if ch.isalnum())

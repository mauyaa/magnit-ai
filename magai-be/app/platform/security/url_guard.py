"""SSRF guard for user-supplied target URLs.

The analyzer and the self-heal sweep both fetch a URL that a customer typed in.
Without validation that is a server-side request forgery primitive: a caller
could point us at ``http://169.254.169.254/`` to read cloud instance credentials,
at ``http://localhost:6379`` to poke Redis, or at any internal service reachable
from the app's network.

:func:`validate_target_url` normalizes the URL, rejects non-HTTP schemes and
non-default ports, resolves every DNS answer, and refuses any address that is not
a global unicast address. Resolution happens here rather than being left to the
HTTP client so a name that resolves into private space is caught up front.

DNS rebinding caveat: a hostname could resolve to a public IP during validation
and a private one when actually fetched. The residual risk is accepted because
the page fetch is performed by the Gemini agent's own sandboxed URL tool rather
than from inside our network, so a rebind lands in Google's fetcher, not ours.
For the one fetch the backend makes itself — the deployment health check in
:mod:`app.platform.pipeline.heal` — redirects are followed manually and every hop
is passed back through :func:`validate_target_url`.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlsplit, urlunsplit

from app.platform.config.settings import settings

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_PORTS = frozenset({80, 443, 8080, 8443})
MAX_URL_LENGTH = 2048

# Cloud metadata services: link-local covers most, but these are called out so
# the failure message is unambiguous and so IPv6 metadata is explicit too.
_METADATA_ADDRESSES = frozenset(
    {
        "169.254.169.254",  # AWS / Azure / GCP / DigitalOcean
        "100.100.100.200",  # Alibaba Cloud
        "192.0.0.192",  # Oracle Cloud
        "fd00:ec2::254",  # AWS IPv6
    }
)

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata",
        "metadata.google.internal",
        "instance-data",
    }
)


class UnsafeTargetURL(ValueError):
    """Raised when a URL is malformed or resolves somewhere we refuse to fetch."""


def _is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    """Return a reason string when ``ip`` must not be fetched, else ``None``."""
    if str(ip) in _METADATA_ADDRESSES:
        return "cloud metadata address"
    if ip.is_loopback:
        return "loopback address"
    if ip.is_link_local:
        return "link-local address"
    if ip.is_multicast:
        return "multicast address"
    if ip.is_reserved:
        return "reserved address"
    if ip.is_unspecified:
        return "unspecified address"
    if ip.is_private:
        return "private address"
    # Catches IPv4-mapped IPv6, 6to4, Teredo and similar tunnels that can smuggle
    # a private v4 destination inside a v6 literal.
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = ip.ipv4_mapped or getattr(ip, "sixtofour", None) or getattr(ip, "teredo", None)
        if mapped is not None:
            inner = mapped[0] if isinstance(mapped, tuple) else mapped
            reason = _is_disallowed_ip(inner)
            if reason:
                return f"tunnelled {reason}"
    if not ip.is_global:
        return "non-global address"
    return None


def _resolve(hostname: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeTargetURL(f"Could not resolve host {hostname!r}") from exc

    addresses = []
    for info in infos:
        raw = info[4][0]
        try:
            addresses.append(ipaddress.ip_address(raw))
        except ValueError:
            continue

    if not addresses:
        raise UnsafeTargetURL(f"Host {hostname!r} resolved to no usable address")
    return addresses


def validate_target_url(raw_url: str) -> str:
    """Validate and normalize a user-supplied URL.

    Returns the normalized URL, or raises :class:`UnsafeTargetURL`. The message is
    safe to show a user: it explains the rejection without revealing internal
    topology beyond the category of address.
    """
    if not raw_url or not raw_url.strip():
        raise UnsafeTargetURL("A URL is required")

    url = raw_url.strip()
    if len(url) > MAX_URL_LENGTH:
        raise UnsafeTargetURL(f"URL must be at most {MAX_URL_LENGTH} characters")

    parts = urlsplit(url)

    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeTargetURL("URL must start with http:// or https://")

    hostname = parts.hostname
    if not hostname:
        raise UnsafeTargetURL("URL is missing a hostname")

    hostname = hostname.rstrip(".").lower()
    if hostname in _BLOCKED_HOSTNAMES:
        raise UnsafeTargetURL("That hostname is not an allowed target")

    # Credentials in the URL are a redirect/parsing-confusion vector and have no
    # legitimate use for a public marketing site.
    if parts.username or parts.password:
        raise UnsafeTargetURL("URLs with embedded credentials are not allowed")

    try:
        port = parts.port
    except ValueError as exc:
        raise UnsafeTargetURL("URL has an invalid port") from exc
    effective_port = port or (443 if parts.scheme.lower() == "https" else 80)
    if effective_port not in ALLOWED_PORTS:
        raise UnsafeTargetURL(f"Port {effective_port} is not an allowed target port")

    if settings.allow_private_target_urls:
        logger.warning(
            "SSRF guard bypassed for %s (MAGAI_ALLOW_PRIVATE_TARGET_URLS is on)", hostname
        )
    else:
        # A bare IP literal is checked directly; a name is checked against every
        # address it resolves to, so a multi-answer record can't sneak one past.
        try:
            literal = ipaddress.ip_address(hostname)
        except ValueError:
            literal = None

        candidates = [literal] if literal is not None else _resolve(hostname, effective_port)
        for address in candidates:
            reason = _is_disallowed_ip(address)
            if reason:
                logger.warning("Blocked SSRF attempt at %s (%s)", hostname, reason)
                raise UnsafeTargetURL(f"That URL points at a {reason}, which cannot be analyzed")

    # Normalize: drop fragments (never sent to a server) and empty query strings.
    return urlunsplit((parts.scheme.lower(), parts.netloc, parts.path or "/", parts.query, ""))

"""SSRF guard tests.

These are the highest-value security tests in the suite: the analyzer fetches a
URL the caller controls, so a regression here is a live SSRF vulnerability.
"""

from unittest.mock import patch

import pytest

from app.platform.security.url_guard import UnsafeTargetURL, validate_target_url


def _resolves_to(*addresses: str):
    """Patch DNS resolution so tests never depend on real records."""
    return patch(
        "app.platform.security.url_guard.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", (addr, 443)) for addr in addresses],
    )


class TestSchemeAndShape:
    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "gopher://example.com",
            "ftp://example.com",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "redis://localhost:6379",
        ],
    )
    def test_rejects_non_http_schemes(self, url):
        with pytest.raises(UnsafeTargetURL):
            validate_target_url(url)

    @pytest.mark.parametrize("url", ["", "   ", "https://", "not-a-url"])
    def test_rejects_malformed_urls(self, url):
        with pytest.raises(UnsafeTargetURL):
            validate_target_url(url)

    def test_rejects_overlong_url(self):
        with pytest.raises(UnsafeTargetURL, match="at most"):
            validate_target_url("https://example.com/" + "a" * 3000)

    def test_rejects_embedded_credentials(self):
        # Credential-in-URL is a classic parser-confusion redirect trick.
        with _resolves_to("93.184.216.34"), pytest.raises(UnsafeTargetURL, match="credentials"):
            validate_target_url("https://user:pass@example.com")

    def test_rejects_non_standard_port(self):
        with pytest.raises(UnsafeTargetURL, match="port"):
            validate_target_url("http://example.com:6379")


class TestBlockedDestinations:
    @pytest.mark.parametrize(
        ("url", "reason"),
        [
            ("http://169.254.169.254/latest/meta-data/", "metadata"),
            ("http://100.100.100.200/", "metadata"),
            ("http://192.0.0.192/", "metadata"),
            ("http://127.0.0.1:8080/", "loopback"),
            ("http://[::1]/", "loopback"),
            ("http://10.0.0.5/", "private"),
            ("http://192.168.1.1/", "private"),
            ("http://172.16.0.1/", "private"),
            ("http://0.0.0.0/", "unspecified"),
        ],
    )
    def test_rejects_ip_literals_in_reserved_ranges(self, url, reason):
        with pytest.raises(UnsafeTargetURL) as excinfo:
            validate_target_url(url)
        assert reason in str(excinfo.value)

    @pytest.mark.parametrize("host", ["localhost", "metadata.google.internal", "instance-data"])
    def test_rejects_blocked_hostnames(self, host):
        with pytest.raises(UnsafeTargetURL):
            validate_target_url(f"http://{host}/")

    def test_rejects_hostname_resolving_to_private_ip(self):
        # The DNS-rebinding shape: a public-looking name pointing inward.
        with _resolves_to("10.1.2.3"), pytest.raises(UnsafeTargetURL, match="private"):
            validate_target_url("https://internal.example.com")

    def test_rejects_when_any_resolved_address_is_private(self):
        # A multi-answer record must not pass just because one answer is public.
        with _resolves_to("93.184.216.34", "127.0.0.1"), pytest.raises(UnsafeTargetURL):
            validate_target_url("https://mixed.example.com")

    def test_rejects_ipv4_mapped_ipv6_loopback(self):
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("http://[::ffff:127.0.0.1]/")

    def test_rejects_trailing_dot_bypass_of_hostname_blocklist(self):
        # "localhost." resolves identically but would evade a naive string check.
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("http://localhost./")


class TestAllowedTargets:
    def test_accepts_public_https_url(self):
        with _resolves_to("93.184.216.34"):
            assert validate_target_url("https://example.com") == "https://example.com/"

    def test_normalizes_and_strips_fragment(self):
        with _resolves_to("93.184.216.34"):
            result = validate_target_url("HTTPS://example.com/pricing?ref=x#section")
        assert result == "https://example.com/pricing?ref=x"

    def test_preserves_path_and_query(self):
        with _resolves_to("93.184.216.34"):
            result = validate_target_url("https://example.com/a/b?c=d&e=f")
        assert result == "https://example.com/a/b?c=d&e=f"

    def test_unresolvable_host_is_rejected_clearly(self):
        import socket

        with patch(
            "app.platform.security.url_guard.socket.getaddrinfo",
            side_effect=socket.gaierror("nope"),
        ):
            with pytest.raises(UnsafeTargetURL, match="resolve"):
                validate_target_url("https://does-not-exist.example")


class TestEscapeHatch:
    def test_private_addresses_allowed_only_when_explicitly_enabled(self, monkeypatch):
        from app.platform.config.settings import settings

        monkeypatch.setattr(settings, "allow_private_target_urls", True)
        # The dev-only bypass must actually work, so local testing is possible.
        assert validate_target_url("http://127.0.0.1:8080/").startswith("http://127.0.0.1")

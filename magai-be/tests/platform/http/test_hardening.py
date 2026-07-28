"""HTTP hardening: security headers, CORS, body limits, error shape."""

import pytest

from app.platform.config.settings import Settings


class TestSecurityHeaders:
    async def test_core_headers_are_present(self, client):
        response = await client.get("/health/live")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "Content-Security-Policy" in response.headers
        assert response.headers["Cache-Control"] == "no-store"

    async def test_csp_forbids_framing_and_loading(self, client):
        csp = (await client.get("/health/live")).headers["Content-Security-Policy"]
        assert "default-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp

    async def test_request_id_is_returned(self, client):
        response = await client.get("/health/live")
        assert response.headers.get("X-Request-ID")

    async def test_supplied_request_id_is_echoed_when_safe(self, client):
        response = await client.get("/health/live", headers={"X-Request-ID": "abc-123"})
        assert response.headers["X-Request-ID"] == "abc-123"

    async def test_unsafe_request_id_is_replaced(self, client):
        # An id lands in log output, so injection characters must be discarded.
        injected = "bad\nid: with newline"
        response = await client.get("/health/live", headers={"X-Request-ID": injected})
        assert response.headers["X-Request-ID"] != injected

    async def test_hsts_absent_over_plain_http(self, client):
        # Asserting HSTS on http://localhost would poison the developer's browser.
        assert "Strict-Transport-Security" not in (await client.get("/health/live")).headers


class TestCors:
    async def test_configured_origin_is_allowed(self, client):
        response = await client.get("/health/live", headers={"Origin": "http://localhost:3000"})
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    async def test_unknown_origin_is_not_allowed(self, client):
        response = await client.get("/health/live", headers={"Origin": "https://evil.example"})
        assert response.headers.get("access-control-allow-origin") != "https://evil.example"


class TestBodyLimit:
    async def test_oversized_body_is_rejected(self, client):
        oversized = "x" * 2_000_000  # Above the 1 MiB default.
        response = await client.post(
            "/api/auth/login", json={"email": "a@example.com", "password": oversized}
        )
        assert response.status_code == 413


class TestErrorShape:
    async def test_404_includes_a_request_id(self, client):
        response = await client.get("/does-not-exist")
        assert response.status_code == 404
        assert "request_id" in response.json()

    async def test_validation_errors_do_not_echo_submitted_values(self, client):
        secret = "super-secret-value-98765"
        response = await client.post("/api/auth/login", json={"email": "x", "password": secret})
        assert response.status_code == 422
        # Pydantic's raw error payload would include the rejected input.
        assert secret not in response.text


class TestProductionConfigGuard:
    """What the boot guard refuses, tested against the validator alone.

    Every construction here passes ``_env_file=None``. ``Settings`` is declared
    with ``env_file=".env"``, so without it pydantic-settings fills any field the
    test left out from the developer's own dotenv — and these tests are entirely
    about fields being *left out*. The day someone put a real
    ``MAGAI_GEMINI_API_KEY`` in their ``.env``, the "production must refuse to
    boot without a Gemini key" test started passing that key in and failing,
    while CI — which has no ``.env`` — stayed green. A suite that depends on the
    machine it runs on is worse than no suite, because it teaches you to ignore it.
    """

    def test_production_rejects_placeholder_secret(self):
        with pytest.raises(ValueError, match="SECRET_KEY"):
            Settings(environment="production", secret_key="change-me-in-production", _env_file=None)

    def test_production_rejects_short_secret(self):
        with pytest.raises(ValueError, match="SECRET_KEY"):
            Settings(environment="production", secret_key="too-short", _env_file=None)

    def test_production_rejects_wildcard_cors(self):
        with pytest.raises(ValueError, match="CORS"):
            Settings(
                environment="production",
                secret_key="x" * 40,
                cors_allow_origins="*",
                _env_file=None,
            )

    def test_production_rejects_private_url_bypass(self):
        with pytest.raises(ValueError, match="PRIVATE_TARGET_URLS"):
            Settings(
                environment="production",
                secret_key="x" * 40,
                cors_allow_origins="https://app.example.com",
                allow_private_target_urls=True,
                _env_file=None,
            )

    def test_production_rejects_debug_mode(self):
        with pytest.raises(ValueError, match="DEBUG"):
            Settings(
                environment="production",
                secret_key="x" * 40,
                cors_allow_origins="https://app.example.com",
                debug=True,
                _env_file=None,
            )

    def test_valid_production_config_is_accepted(self):
        settings = Settings(
            environment="production",
            secret_key="x" * 40,
            cors_allow_origins="https://app.example.com",
            require_payment_to_build=True,
            stripe_secret_key="sk_test_configured",
            stripe_webhook_secret="whsec_configured",
            gemini_api_key="gemini-configured",
            vercel_api_token="vercel-configured",
            _env_file=None,
        )
        assert settings.is_production
        assert settings.cors_origins == ["https://app.example.com"]

    def test_production_requires_generation_and_deployment_providers(self):
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            Settings(
                environment="production",
                secret_key="x" * 40,
                cors_allow_origins="https://app.example.com",
                require_payment_to_build=True,
                stripe_secret_key="sk_test_configured",
                stripe_webhook_secret="whsec_configured",
                _env_file=None,
            )

    def test_development_tolerates_defaults(self):
        # Local development must not require production-grade configuration. The
        # placeholder secret and a wildcard origin are both tolerated here, where
        # in production either refuses to boot.
        settings = Settings(
            environment="development",
            secret_key="change-me-in-production",
            cors_allow_origins="*",
            debug=True,
        )
        assert not settings.is_production
        assert settings.secret_key == "change-me-in-production"

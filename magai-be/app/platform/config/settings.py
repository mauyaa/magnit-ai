from datetime import timedelta
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent

INSECURE_SECRET_PLACEHOLDER = "change-me-in-production"


class Settings(BaseSettings):
    model_config = {"env_prefix": "MAGAI_", "env_file": ".env", "extra": "ignore"}

    # ---- Environment -------------------------------------------------------
    # "development" | "staging" | "production". Production tightens several
    # defaults and refuses to boot with an insecure signing secret.
    environment: str = "development"
    debug: bool = False

    # ---- Datastores --------------------------------------------------------
    database_url: str = "postgresql+asyncpg://localhost:5432/magai"
    redis_url: str = "redis://localhost:6379/0"
    # Connect/read timeout for every Redis call. Deliberately small: revocation
    # and rate-limit checks run on the hot path and both fail open, so an
    # unreachable Redis must cost milliseconds. Without this the OS default
    # applies and each request stalls for seconds — measured at ~4s.
    redis_timeout_seconds: float = 0.25
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    # A development checkout must be able to exercise the complete customer
    # story without pretending that Redis and Vercel are present. In this mode
    # builds run in the API process, progress events stay in memory, and the
    # generated dist is served from ``site_url``. Production never takes this
    # path, even if the flag is accidentally left enabled.
    development_local_builds: bool = True

    # ---- Third-party -------------------------------------------------------
    gemini_api_key: str = ""
    stitch_api_key: str = ""
    stitch_mcp_command: str = ""
    stitch_mcp_args: str = ""
    # Web OAuth client used to verify Google Identity Services ID tokens.
    google_client_id: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    vercel_api_token: str = ""
    # Stable Flash supports structured output with materially broader quotas
    # than the Pro preview, which can report a zero-request free-tier limit.
    #
    # Pinned to an explicit version, not `gemini-flash-latest`: an alias moving
    # under a running deployment changes generation behaviour with no code
    # change and no way to correlate it with a bad build.
    #
    # This was `gemini-2.5-flash` until it began returning 404 "no longer
    # available to new users". The failure was invisible from outside — the
    # analyzer degrades to `pipeline.fallback` and the request still answers
    # 200 — so a stale id here silently turns the AI product into a template.
    agy_model: str = "gemini-3.6-flash"
    # Product economics live in configuration rather than being buried in a
    # checkout function. The launch price includes one generated, deployed tool.
    widget_launch_price_cents: int = 9_900
    widget_launch_currency: str = "usd"
    studio_monthly_price_cents: int = 9_900
    studio_active_experience_limit: int = 3
    scale_monthly_price_cents: int = 19_900
    scale_active_experience_limit: int = 10
    require_payment_to_build: bool = False
    # Provider prices change. Keep them explicit and default to zero rather than
    # baking stale economics into code. Token counts are still recorded.
    model_input_usd_per_million_tokens: float = 0.0
    model_output_usd_per_million_tokens: float = 0.0

    # ---- URLs --------------------------------------------------------------
    frontend_base_url: str = "http://localhost:3000"
    site_url: str = "http://localhost:8000"
    widgets_dir: str = str(PROJECT_ROOT / "workspace")

    # ---- Auth --------------------------------------------------------------
    # JWT signing secret. Must be overridden in production (validated below).
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(64))"
    secret_key: str = INSECURE_SECRET_PLACEHOLDER
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30
    password_min_length: int = 12
    # Short by design: a reset link is a password equivalent while it lives.
    password_reset_ttl_minutes: int = 30
    email_verification_ttl_hours: int = 48
    guest_concept_ttl_hours: int = 24
    # When true, unverified accounts can sign in but cannot spend build budget.
    require_verified_email_to_build: bool = True

    # ---- Email --------------------------------------------------------------
    # "console" logs instead of sending — the default so development and CI never
    # need credentials and cannot accidentally mail real users.
    email_backend: str = "console"
    email_from: str = "Magnitai <no-reply@magnitai.local>"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""

    # ---- MFA ----------------------------------------------------------------
    mfa_issuer: str = "Magnitai"
    mfa_recovery_code_count: int = 8

    # ---- HTTP security -----------------------------------------------------
    # Comma-separated exact origins. Never "*" — credentials are allowed, and
    # wildcard-plus-credentials is both invalid per spec and unsafe.
    cors_allow_origins: str = "http://localhost:3000,http://localhost:5173"
    # Comma-separated Host values accepted by TrustedHostMiddleware ("*" = any).
    trusted_hosts: str = "*"
    max_request_bytes: int = 1_048_576  # 1 MiB
    hsts_max_age_seconds: int = 31_536_000

    # ---- Rate limiting -----------------------------------------------------
    rate_limit_enabled: bool = True
    # Expensive endpoints: each call spends real Gemini + Vercel budget.
    rate_limit_analyze: str = "10/hour"
    # The public first look intentionally allows one expensive two-direction
    # generation per source each day. Account usage has its own limits.
    rate_limit_guest_concepts: str = "1/day"
    rate_limit_build: str = "5/hour"
    rate_limit_preview: str = "20/hour"
    # Public, unauthenticated endpoints.
    rate_limit_lead_submit: str = "30/minute"
    # Generous: one legitimate view per page load, and a widget on a busy page can
    # produce real bursts. Still bounded so it cannot be used to inflate metrics.
    rate_limit_impression: str = "120/minute"
    rate_limit_interaction: str = "240/minute"
    rate_limit_auth: str = "10/minute"
    rate_limit_default: str = "300/minute"

    # ---- SSRF guard --------------------------------------------------------
    # Only ever enable on a trusted dev machine; lets the analyzer reach
    # private/loopback addresses, which is an SSRF vector in production.
    allow_private_target_urls: bool = False

    # ---- Self-healing ------------------------------------------------------
    self_heal_enabled: bool = True
    self_heal_interval_minutes: int = 360
    # Cap widgets processed per sweep so the job stays bounded as tenancy grows.
    self_heal_batch_size: int = 25
    # Stop retrying a widget that keeps failing to heal; surfaced for operators.
    self_heal_max_failures: int = 3
    self_heal_lock_ttl_seconds: int = 1_800
    # Brand extraction is cheap but still touches the customer's website. The
    # expensive AI comparison only runs when this deterministic fingerprint moves.
    brand_check_interval_minutes: int = 10_080

    # ---- Observability -----------------------------------------------------
    log_format: str = "json"  # "json" | "text"
    log_level: str = "INFO"
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    metrics_enabled: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def local_builds_enabled(self) -> bool:
        return (
            self.development_local_builds and not self.is_production and not self.vercel_api_token
        )

    @property
    def enforce_plan_limits(self) -> bool:
        """Whether plan features and quotas are enforced, or everything is open.

        The same switch as ``require_payment_to_build``, named for the wider job
        it actually does now that plans gate features as well as builds. One flag
        rather than two, because "builds cost money but the CRM integrations are
        free" is not a state anyone wants to be able to configure by accident.

        Off in development and CI so tests and local work exercise the whole
        product; production validation refuses to start without it.
        """
        return self.require_payment_to_build

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]

    @property
    def guest_concept_ttl(self) -> timedelta:
        return timedelta(hours=self.guest_concept_ttl_hours)

    @model_validator(mode="after")
    def _validate_production_hardening(self) -> "Settings":
        if not self.is_production:
            return self

        problems: list[str] = []
        if self.secret_key == INSECURE_SECRET_PLACEHOLDER or len(self.secret_key) < 32:
            problems.append(
                "MAGAI_SECRET_KEY must be set to a random value of at least 32 characters"
            )
        if "*" in self.cors_origins:
            problems.append("MAGAI_CORS_ALLOW_ORIGINS must not contain '*' in production")
        if self.allow_private_target_urls:
            problems.append("MAGAI_ALLOW_PRIVATE_TARGET_URLS must be false in production")
        if self.debug:
            problems.append("MAGAI_DEBUG must be false in production")
        if not self.require_payment_to_build:
            problems.append("MAGAI_REQUIRE_PAYMENT_TO_BUILD must be true in production")
        if not self.stripe_secret_key or not self.stripe_webhook_secret:
            problems.append("Stripe secret and webhook secret must be configured in production")
        if not self.gemini_api_key:
            problems.append("MAGAI_GEMINI_API_KEY must be configured in production")
        if not self.vercel_api_token:
            problems.append("MAGAI_VERCEL_API_TOKEN must be configured in production")

        if problems:
            raise ValueError(
                "Refusing to start in production with insecure configuration:\n  - "
                + "\n  - ".join(problems)
            )
        return self


settings = Settings()

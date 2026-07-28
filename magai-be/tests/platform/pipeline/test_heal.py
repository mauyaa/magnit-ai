"""Self-heal detection tests.

The drift diff decides whether the product spends an AI call and a deployment, so
both false negatives (missed rebrand) and false positives (needless rebuild) are
expensive. These tests pin both directions.
"""

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.platform.pipeline.heal import (
    _diff_fields,
    check_brand_drift,
    check_deploy_health,
)
from app.platform.pipeline.schemas import (
    ArchitectOutput,
    BrandExtraction,
    MathLogic,
    SiteBrandEvidence,
    SiteEvidence,
    SitePageEvidence,
    VisualLanguage,
    WidgetType,
)


class FakeWidget:
    def __init__(self, brand_tokens=None, visual_language=None, deployment_url=None):
        self.id = "11111111-1111-1111-1111-111111111111"
        self.widget_type = WidgetType.ROI_CALCULATOR.value
        self.title = "Test Widget"
        self.target_url = "https://example.com"
        self.brand_tokens = brand_tokens
        self.visual_language = visual_language
        self.deployment_url = deployment_url
        self.source_brand_fingerprint = None


BASELINE_BRAND = {
    "primary_color": "#111111",
    "secondary_color": "#222222",
    "background_color": "#ffffff",
    "font_headings": "Inter",
}
BASELINE_VISUAL = {"layout": "centered-single-column", "card_style": "solid-white"}


def _architect_output(**brand_overrides) -> ArchitectOutput:
    brand = {
        "primary_color": "#111111",
        "secondary_color": "#222222",
        "background_color": "#ffffff",
        "accent_color": "#333333",
        "font_headings": "Inter",
        "font_body": "Inter",
        "tone": "minimal-clean",
    }
    brand.update(brand_overrides)
    return ArchitectOutput(
        widget_type=WidgetType.ROI_CALCULATOR,
        brand=BrandExtraction(**brand),
        visual_language=VisualLanguage(**BASELINE_VISUAL),
        logic=MathLogic(formula="x", variables=[], example_calculation="x"),
        copywriting={"headline": "Test"},
    )


def _evidence() -> SiteEvidence:
    return SiteEvidence(
        target_url="https://example.com",
        domain="example.com",
        pages=[SitePageEvidence(url="https://example.com", title="Example")],
        brand=SiteBrandEvidence(),
        content_fingerprint="a" * 64,
        brand_fingerprint="b" * 64,
    )


@contextmanager
def _allow_url():
    with (
        patch("app.platform.pipeline.heal.validate_target_url", side_effect=lambda url: url),
        patch(
            "app.platform.pipeline.heal.collect_site_evidence",
            new=AsyncMock(return_value=_evidence()),
        ),
    ):
        yield


class TestDiffFields:
    def test_detects_a_changed_value(self):
        diff = _diff_fields(
            {"primary_color": "#111"}, {"primary_color": "#222"}, ("primary_color",)
        )
        assert diff == {"primary_color": {"old": "#111", "new": "#222"}}

    def test_ignores_unchanged_values(self):
        unchanged = _diff_fields(
            {"primary_color": "#111"}, {"primary_color": "#111"}, ("primary_color",)
        )
        assert unchanged == {}

    def test_ignores_case_and_whitespace_differences(self):
        # "#FFFFFF" and "#ffffff" are the same colour; rebuilding would be waste.
        assert (
            _diff_fields(
                {"primary_color": "#FFFFFF"}, {"primary_color": " #ffffff "}, ("primary_color",)
            )
            == {}
        )

    def test_ignores_missing_baseline(self):
        # No stored value means the field predates tracking, not that it drifted.
        assert _diff_fields({}, {"primary_color": "#111"}, ("primary_color",)) == {}

    def test_ignores_missing_new_value(self):
        assert _diff_fields({"primary_color": "#111"}, {}, ("primary_color",)) == {}

    def test_only_considers_listed_fields(self):
        diff = _diff_fields({"tone": "calm"}, {"tone": "loud"}, ("primary_color",))
        assert diff == {}


class TestCheckBrandDrift:
    async def test_detects_primary_colour_change(self):
        widget = FakeWidget(brand_tokens=BASELINE_BRAND, visual_language=BASELINE_VISUAL)
        fresh = _architect_output(primary_color="#ff0000")

        with (
            _allow_url(),
            patch(
                "app.platform.pipeline.heal.run_architect_stage", new=AsyncMock(return_value=fresh)
            ),
        ):
            result = await check_brand_drift(widget)

        assert result.drifted
        assert result.diff["primary_color"] == {"old": "#111111", "new": "#ff0000"}

    async def test_detects_font_change(self):
        widget = FakeWidget(brand_tokens=BASELINE_BRAND, visual_language=BASELINE_VISUAL)
        fresh = _architect_output(font_headings="Georgia")

        with (
            _allow_url(),
            patch(
                "app.platform.pipeline.heal.run_architect_stage", new=AsyncMock(return_value=fresh)
            ),
        ):
            result = await check_brand_drift(widget)

        assert result.drifted
        assert "font_headings" in result.diff

    async def test_reports_no_drift_when_brand_is_stable(self):
        widget = FakeWidget(brand_tokens=BASELINE_BRAND, visual_language=BASELINE_VISUAL)
        fresh = _architect_output()

        with (
            _allow_url(),
            patch(
                "app.platform.pipeline.heal.run_architect_stage", new=AsyncMock(return_value=fresh)
            ),
        ):
            result = await check_brand_drift(widget)

        assert not result.drifted
        assert result.diff == {}

    async def test_ignores_tone_rewording(self):
        # Free-text descriptors get re-worded by the model between runs; treating
        # that as drift would rebuild widgets forever.
        widget = FakeWidget(
            brand_tokens={**BASELINE_BRAND, "tone": "calm and minimal"},
            visual_language=BASELINE_VISUAL,
        )
        fresh = _architect_output(tone="minimal, calm")

        with (
            _allow_url(),
            patch(
                "app.platform.pipeline.heal.run_architect_stage", new=AsyncMock(return_value=fresh)
            ),
        ):
            result = await check_brand_drift(widget)

        assert not result.drifted

    async def test_url_is_revalidated_before_fetching(self):
        from app.platform.security.url_guard import UnsafeTargetURL

        widget = FakeWidget(brand_tokens=BASELINE_BRAND, visual_language=BASELINE_VISUAL)

        # A domain that later resolves into private space must not be fetched.
        with (
            patch(
                "app.platform.pipeline.heal.validate_target_url",
                side_effect=UnsafeTargetURL("private address"),
            ),
            pytest.raises(UnsafeTargetURL),
        ):
            await check_brand_drift(widget)


class TestCheckDeployHealth:
    async def test_healthy_when_never_deployed(self):
        assert await check_deploy_health(FakeWidget(deployment_url=None)) is True

    async def test_healthy_on_200(self):
        widget = FakeWidget(deployment_url="https://live.example.com")
        with (
            _allow_url(),
            patch(
                "app.platform.pipeline.heal.httpx.AsyncClient",
                return_value=_fake_client(httpx.Response(200)),
            ),
        ):
            assert await check_deploy_health(widget) is True

    async def test_unhealthy_on_404(self):
        widget = FakeWidget(deployment_url="https://gone.example.com")
        with (
            _allow_url(),
            patch(
                "app.platform.pipeline.heal.httpx.AsyncClient",
                return_value=_fake_client(httpx.Response(404)),
            ),
        ):
            assert await check_deploy_health(widget) is False

    async def test_unhealthy_on_network_error(self):
        widget = FakeWidget(deployment_url="https://unreachable.example.com")
        with (
            _allow_url(),
            patch(
                "app.platform.pipeline.heal.httpx.AsyncClient",
                return_value=_fake_client(httpx.ConnectError("refused")),
            ),
        ):
            assert await check_deploy_health(widget) is False

    async def test_redirect_into_private_space_is_treated_as_unhealthy(self):
        from app.platform.security.url_guard import UnsafeTargetURL

        widget = FakeWidget(deployment_url="https://redirector.example.com")
        redirect = httpx.Response(302, headers={"location": "http://169.254.169.254/"})

        def guard(url):
            if "169.254" in url:
                raise UnsafeTargetURL("cloud metadata address")
            return url

        # Following the redirect blindly would turn this check into an SSRF probe.
        with (
            patch("app.platform.pipeline.heal.validate_target_url", side_effect=guard),
            patch(
                "app.platform.pipeline.heal.httpx.AsyncClient", return_value=_fake_client(redirect)
            ),
        ):
            assert await check_deploy_health(widget) is False


def _fake_client(result):
    """Async context manager whose ``get`` returns ``result`` or raises it."""

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, _url):
            if isinstance(result, Exception):
                raise result
            return result

    return FakeClient()

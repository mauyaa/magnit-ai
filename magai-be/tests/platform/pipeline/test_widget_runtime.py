"""Tests for the deterministic parts of a generated widget.

These guard two regressions that made the product structurally broken before:
generated widgets never submitted a lead, and the brand's CSS variables were never
actually defined so every branded element rendered uncoloured.
"""

import pytest

from app.platform.pipeline.schemas import DesignTokens
from app.platform.pipeline.widget_runtime import (
    RUNTIME_SDK_JS,
    google_fonts_href,
    render_runtime_config,
    render_tokens_css,
)


def _tokens(**overrides) -> DesignTokens:
    css_variables = {
        "--color-primary": "#ff5722",
        "--color-secondary": "#212121",
        "--color-background": "#fafafa",
        "--color-accent": "#00bcd4",
        "--font-heading": "Sora",
        "--font-body": "Manrope",
    }
    css_variables.update(overrides.pop("css_variables", {}))
    return DesignTokens(
        css_variables=css_variables,
        component_theme=overrides.pop(
            "component_theme",
            {"button_bg": "var(--color-primary)", "button_text": "#ffffff"},
        ),
    )


class TestTokensCss:
    def test_emits_a_root_block_with_the_brand_colors(self):
        css = render_tokens_css(_tokens())
        # The regression: without a :root block every var(--color-primary) in the
        # generated markup resolved to nothing.
        assert ":root {" in css
        assert "--color-primary: #ff5722;" in css
        assert "--color-accent: #00bcd4;" in css

    def test_fonts_get_a_quoted_stack_with_fallbacks(self):
        css = render_tokens_css(_tokens())
        assert "--font-heading: 'Sora', ui-sans-serif" in css
        assert "--font-body: 'Manrope', ui-sans-serif" in css

    def test_guarantees_every_variable_the_prompt_promises(self):
        # The prompt tells the model these always exist, so they must.
        css = render_tokens_css(DesignTokens(css_variables={}, component_theme={}))
        for name in (
            "--color-primary",
            "--color-secondary",
            "--color-background",
            "--color-accent",
            "--color-surface",
            "--color-muted",
            "--font-heading",
            "--font-body",
        ):
            assert f"{name}:" in css

    def test_maps_component_theme_onto_stylesheet_variables(self):
        css = render_tokens_css(_tokens())
        # The base stylesheet reads --button-bg; without this mapping its
        # hardcoded blue default would win over the brand.
        assert "--button-bg:" in css
        assert "--button-text: #ffffff;" in css

    def test_normalizes_names_missing_the_double_dash(self):
        css = render_tokens_css(
            DesignTokens(css_variables={"color-primary": "#123456"}, component_theme={})
        )
        assert "--color-primary: #123456;" in css

    def test_applies_background_and_font_to_body(self):
        css = render_tokens_css(_tokens())
        assert "background: var(--color-background);" in css
        assert "font-family: var(--font-body);" in css

    @pytest.mark.parametrize(
        "malicious",
        [
            "red; } body { display: none; } :root { --x: y",
            "red; background: url(http://evil.example/x)",
            "</style><script>alert(1)</script>",
            "expression(alert(1))",
            "red; @import url(http://evil.example/x.css)",
        ],
    )
    def test_rejects_css_injection_through_token_values(self, malicious):
        # Token values come from a model, so they are untrusted input landing in a
        # stylesheet. A value that could terminate the declaration is dropped.
        css = render_tokens_css(
            DesignTokens(css_variables={"--color-primary": malicious}, component_theme={})
        )
        assert "display: none" not in css
        assert "<script" not in css
        assert "@import" not in css
        # Dropped, so the guaranteed default applies instead.
        assert "--color-primary: #2563eb;" in css

    def test_drops_absurdly_long_values(self):
        css = render_tokens_css(
            DesignTokens(css_variables={"--color-primary": "a" * 500}, component_theme={})
        )
        assert "--color-primary: #2563eb;" in css


class TestGoogleFontsHref:
    def test_requests_the_brands_actual_fonts(self):
        href = google_fonts_href({"--font-heading": "Sora", "--font-body": "Manrope"})
        # The old scaffold hardcoded four unrelated families, so any other brand
        # font silently fell back.
        assert href is not None
        assert "family=Sora" in href
        assert "family=Manrope" in href

    def test_encodes_multi_word_family_names(self):
        href = google_fonts_href({"--font-heading": "Playfair Display"})
        assert href is not None and "family=Playfair+Display" in href

    def test_deduplicates_when_both_fonts_match(self):
        href = google_fonts_href({"--font-heading": "Inter", "--font-body": "Inter"})
        assert href is not None and href.count("family=Inter") == 1

    def test_returns_none_when_no_usable_font(self):
        assert google_fonts_href({}) is None

    @pytest.mark.parametrize("value", ["Sora'); @import url(x", "<script>", "a" * 100])
    def test_rejects_unsafe_family_names(self, value):
        assert google_fonts_href({"--font-heading": value}) is None


class TestRuntimeConfig:
    def test_embeds_the_widget_identity(self):
        js = render_runtime_config("abc-123", "https://api.example.com/")
        assert '"widgetId": "abc-123"' in js
        # Trailing slash stripped so the SDK's path concatenation stays correct.
        assert '"apiBaseUrl": "https://api.example.com"' in js
        assert "export const MAGNITAI_CONFIG" in js

    def test_embeds_the_declarative_decision_spec(self):
        js = render_runtime_config(
            "abc-123",
            "https://api.example.com",
            {"qualification_threshold": 60, "questions": [], "results": []},
        )
        assert '"decisionSpec"' in js
        assert '"qualification_threshold": 60' in js


class TestRuntimeSdk:
    def test_imports_the_sibling_config_from_the_parent_directory(self):
        assert "from '../config.js'" in RUNTIME_SDK_JS

    def test_posts_to_the_lead_endpoint(self):
        # The core loop: this is the call that was entirely absent before.
        assert "/api/leads/${widgetId}" in RUNTIME_SDK_JS
        assert "export async function submitLead" in RUNTIME_SDK_JS

    def test_submit_lead_never_throws(self):
        # A network error must not blank the widget mid-interaction.
        assert "catch {" in RUNTIME_SDK_JS
        assert "return { ok: false" in RUNTIME_SDK_JS

    def test_translates_cap_and_rate_limit_responses(self):
        assert "409" in RUNTIME_SDK_JS
        assert "429" in RUNTIME_SDK_JS

    def test_impressions_are_sent_once(self):
        # React StrictMode double-invokes effects in development; without the guard
        # every view would be counted twice and conversion rate halved.
        assert "impressionSent" in RUNTIME_SDK_JS
        assert "keepalive" in RUNTIME_SDK_JS

    def test_validates_email_before_sending(self):
        assert "isValidEmail" in RUNTIME_SDK_JS

    def test_calculation_and_funnel_actions_are_hand_written(self):
        assert "export function calculateDecision" in RUNTIME_SDK_JS
        assert "/interactions" in RUNTIME_SDK_JS
        assert "export const trackStart" in RUNTIME_SDK_JS

    def test_reports_iframe_height_to_the_host_page(self):
        assert "ResizeObserver" in RUNTIME_SDK_JS
        assert "magnit:resize" in RUNTIME_SDK_JS

    def test_offers_the_live_configuration_as_a_react_value(self):
        """The hook every generated app renders from.

        Exposing the configuration only as a getter was not enough: a component
        that read it during its first render kept whatever was baked in, because
        the overlay resolves afterwards and nothing told React to re-render.
        That is how an owner's edit reached the scoring but never the screen.
        """
        assert "export function useLiveConfig" in RUNTIME_SDK_JS
        assert "useSyncExternalStore" in RUNTIME_SDK_JS
        assert "from 'react'" in RUNTIME_SDK_JS

    def test_the_overlay_replaces_the_configuration_rather_than_mutating_it(self):
        # useSyncExternalStore compares snapshots by identity. Mutating in place
        # would leave every subscriber rendering the previous copy.
        assert "live = {" in RUNTIME_SDK_JS
        assert "getLiveConfig" in RUNTIME_SDK_JS

"""The workspace brand kit, and how it overrides a site-extracted brand."""

from app.features.users.brand import (
    FONT_PAIRINGS_BY_ID,
    apply_to_extraction,
    design_token_overrides,
    is_configured,
    upsert_brand,
)
from app.features.users.models import WorkspaceBrand
from app.platform.pipeline.schemas import BrandExtraction


def _extraction(**overrides) -> BrandExtraction:
    defaults = dict(
        primary_color="#123456",
        secondary_color="#222222",
        background_color="#FFFFFF",
        accent_color="#ABCDEF",
        font_headings="Georgia",
        font_body="Verdana",
        tone="Straightforward and warm",
        logo_url="https://example.com/site-logo.png",
    )
    defaults.update(overrides)
    return BrandExtraction(**defaults)


class TestIsConfigured:
    def test_no_row_is_not_a_brand_kit(self):
        assert not is_configured(None)

    def test_an_empty_row_is_not_a_brand_kit(self):
        assert not is_configured(WorkspaceBrand())

    def test_one_field_is_enough(self):
        assert is_configured(WorkspaceBrand(accent_color="#FF0000"))

    def test_a_zero_corner_radius_counts(self):
        # Square corners are a real choice; `or`-style truthiness would drop it.
        assert is_configured(WorkspaceBrand(corner_radius=0))


class TestApplyToExtraction:
    def test_without_a_kit_the_site_brand_is_untouched(self):
        original = _extraction()
        assert apply_to_extraction(original, None) == original
        assert apply_to_extraction(original, WorkspaceBrand()) == original

    def test_the_accent_wins_over_the_extracted_colour(self):
        result = apply_to_extraction(_extraction(), WorkspaceBrand(accent_color="#FF0000"))
        assert result.accent_color == "#FF0000"
        assert result.primary_color == "#FF0000"
        # Untouched fields keep deferring to the site.
        assert result.font_body == "Verdana"

    def test_a_font_pairing_sets_both_faces(self):
        result = apply_to_extraction(_extraction(), WorkspaceBrand(font_pairing="grotesk_lora"))
        pairing = FONT_PAIRINGS_BY_ID["grotesk_lora"]
        assert result.font_headings == pairing.heading
        assert result.font_body == pairing.body

    def test_an_unknown_pairing_is_ignored_rather_than_breaking_the_build(self):
        result = apply_to_extraction(_extraction(), WorkspaceBrand(font_pairing="comic_sans_ms"))
        assert result.font_headings == "Georgia"

    def test_tone_supplies_a_background_when_no_colour_was_set(self):
        result = apply_to_extraction(_extraction(), WorkspaceBrand(tone="deep"))
        assert result.background_color == "#12151A"

    def test_an_explicit_background_beats_the_tone(self):
        result = apply_to_extraction(
            _extraction(), WorkspaceBrand(tone="deep", background_color="#FAFAFA")
        )
        assert result.background_color == "#FAFAFA"

    def test_a_malformed_colour_is_ignored(self):
        # The value reaches a generated stylesheet, so it is never trusted.
        result = apply_to_extraction(
            _extraction(), WorkspaceBrand(accent_color="red;}body{display:none")
        )
        assert result.accent_color == "#ABCDEF"

    def test_brand_personality_becomes_the_voice_direction(self):
        result = apply_to_extraction(
            _extraction(), WorkspaceBrand(brand_personality="Calm, trustworthy, clarity-driven")
        )
        assert result.tone == "Calm, trustworthy, clarity-driven"


class TestTokenOverrides:
    def test_corner_radius_travels_as_a_css_variable(self):
        assert design_token_overrides(WorkspaceBrand(corner_radius=16)) == {"--radius": "16px"}

    def test_nothing_configured_produces_nothing(self):
        assert design_token_overrides(None) == {}
        assert design_token_overrides(WorkspaceBrand()) == {}


class TestUpsert:
    async def test_creates_then_updates_a_single_row(self, db, user):
        first = await upsert_brand(db, user.id, {"accent_color": "#FF0000"})
        second = await upsert_brand(db, user.id, {"tone": "soft"})
        await db.commit()

        assert first.id == second.id
        # An omitted key means "leave it", so the accent survives.
        assert second.accent_color == "#FF0000"
        assert second.tone == "soft"

    async def test_an_explicit_null_hands_the_field_back_to_the_site(self, db, user):
        await upsert_brand(db, user.id, {"accent_color": "#FF0000"})
        brand = await upsert_brand(db, user.id, {"accent_color": None})
        await db.commit()
        assert brand.accent_color is None


class TestBrandRoutes:
    async def test_get_reports_unconfigured_and_offers_the_pairings(self, user, as_user):
        response = await (as_user(user)).get("/api/users/me/brand")
        assert response.status_code == 200

        body = response.json()
        assert body["configured"] is False
        assert body["accent_color"] is None
        # The screen needs the catalogue to render its choices.
        assert len(body["font_pairings"]) >= 3
        assert "heading" in body["font_pairings"][0]

    async def test_put_saves_and_marks_it_configured(self, user, as_user):
        response = await (as_user(user)).put(
            "/api/users/me/brand",
            json={
                "accent_color": "#16A34A",
                "font_pairing": "inter_fraunces",
                "corner_radius": 8,
                "tone": "soft",
                "brand_personality": "Calm and clear",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["configured"] is True
        assert body["accent_color"] == "#16A34A"
        assert body["corner_radius"] == 8

    async def test_a_malformed_colour_is_rejected_by_the_schema(self, user, as_user):
        response = await (as_user(user)).put(
            "/api/users/me/brand", json={"accent_color": "not-a-colour"}
        )
        assert response.status_code == 422

    async def test_an_unknown_font_pairing_is_rejected(self, user, as_user):
        response = await (as_user(user)).put(
            "/api/users/me/brand", json={"font_pairing": "papyrus_impact"}
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "unknown_font_pairing"

    async def test_a_corner_radius_outside_the_range_is_rejected(self, user, as_user):
        assert (
            await (as_user(user)).put("/api/users/me/brand", json={"corner_radius": 400})
        ).status_code == 422

    async def test_a_logo_url_pointing_inside_the_network_is_refused(self, user, as_user):
        response = await (as_user(user)).put(
            "/api/users/me/brand", json={"logo_url": "http://127.0.0.1:8000/internal.png"}
        )
        assert response.status_code == 422

    async def test_brands_do_not_leak_between_workspaces(self, user, other_user, as_user):
        await (as_user(user)).put("/api/users/me/brand", json={"accent_color": "#FF0000"})
        theirs = await (as_user(other_user)).get("/api/users/me/brand")
        assert theirs.json()["configured"] is False

    async def test_requires_authentication(self, client):
        assert (await client.get("/api/users/me/brand")).status_code == 401

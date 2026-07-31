"""Is this tool actually on the customer's website?

The old answer was "has anyone interacted with it from a page with a referrer",
which was wrong in both directions at the same time:

* a correctly pasted embed that nobody had touched yet could not be verified, so
  the owner was told their installation had failed when it had not;
* the owner clicking through the preview inside their own dashboard verified it,
  so a tool that had never been pasted anywhere reported itself as installed.

Those same preview views were also counted as visitors, quietly diluting the
conversion rate the tool was being judged on.
"""

from __future__ import annotations

import pytest

from app.features.billing.entitlements import resolve_entitlements
from app.features.widgets.models import Widget
from app.features.widgets.readiness import assess_readiness
from app.features.widgets.service import build_embed_code, embed_host_of, record_impression
from app.platform.config.settings import settings

CUSTOMER_PAGE = "https://northsidedental.example/new-patients"


async def _widget(db, owner, **overrides) -> Widget:
    widget = Widget(
        user_id=owner.id,
        target_url="https://northsidedental.example/",
        widget_type="roi_calculator",
        title="Calc",
        status="active",
        deployment_url="https://magai-widget-abc.vercel.app",
        embed_url="https://magai-widget-abc.vercel.app",
        **overrides,
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


class TestEmbedHost:
    def test_a_customers_page_is_an_embed(self):
        assert embed_host_of(CUSTOMER_PAGE) == "northsidedental.example"

    @pytest.mark.parametrize("field", ["frontend_base_url", "site_url"])
    def test_our_own_screens_are_not(self, field):
        # The dashboard preview and the build screen's live preview both load
        # the same public URL and both send a referrer — ours.
        assert embed_host_of(getattr(settings, field) + "/dashboard/widgets/x") is None

    def test_a_view_with_no_referrer_is_neither(self):
        """Someone opening the tool's own URL directly. A view, not an install."""
        assert embed_host_of(None) is None
        assert embed_host_of("") is None


class TestImpressions:
    async def test_a_view_from_a_real_page_marks_the_tool_installed(self, db, user):
        widget = await _widget(db, user)

        assert await record_impression(db, str(widget.id), CUSTOMER_PAGE) is True
        await db.commit()
        await db.refresh(widget)

        assert widget.impressions_count == 1
        assert widget.first_embedded_at is not None
        assert widget.embed_host == "northsidedental.example"

    async def test_the_owners_own_preview_is_not_a_visitor(self, db, user):
        """Otherwise every tool's conversion rate is diluted by its builder."""
        widget = await _widget(db, user)

        assert (
            await record_impression(
                db, str(widget.id), f"{settings.frontend_base_url}/dashboard/widgets/{widget.id}"
            )
            is True
        )
        await db.commit()
        await db.refresh(widget)

        assert widget.impressions_count == 0
        assert widget.first_embedded_at is None

    async def test_the_first_sighting_is_the_one_that_is_kept(self, db, user):
        widget = await _widget(db, user)

        await record_impression(db, str(widget.id), CUSTOMER_PAGE)
        await db.commit()
        await db.refresh(widget)
        first = widget.first_embedded_at

        await record_impression(db, str(widget.id), CUSTOMER_PAGE)
        await db.commit()
        await db.refresh(widget)

        assert widget.first_embedded_at == first
        assert widget.impressions_count == 2

    async def test_a_view_without_a_referrer_still_counts_as_a_view(self, db, user):
        """Referrers are often stripped. That is not evidence of anything."""
        widget = await _widget(db, user)

        await record_impression(db, str(widget.id), None)
        await db.commit()
        await db.refresh(widget)

        assert widget.impressions_count == 1
        assert widget.first_embedded_at is None


class TestReadiness:
    async def test_a_pasted_embed_verifies_before_anyone_interacts_with_it(self, db, user):
        """The false negative: installed, working, and reported as missing."""
        widget = await _widget(db, user)
        await record_impression(db, str(widget.id), CUSTOMER_PAGE)
        await db.commit()
        await db.refresh(widget)

        entitlements = await resolve_entitlements(db, user.id)
        readiness = await assess_readiness(db, widget, user, entitlements)
        embedded = next(check for check in readiness.checks if check.id == "embedded")

        assert embedded.done is True

    async def test_previewing_it_in_the_dashboard_does_not_verify_it(self, db, user):
        """The false positive: never pasted anywhere, reported as installed."""
        widget = await _widget(db, user)
        await record_impression(
            db, str(widget.id), f"{settings.frontend_base_url}/dashboard/widgets/{widget.id}"
        )
        await db.commit()
        await db.refresh(widget)

        entitlements = await resolve_entitlements(db, user.id)
        readiness = await assess_readiness(db, widget, user, entitlements)
        embedded = next(check for check in readiness.checks if check.id == "embedded")

        assert embedded.done is False


class TestCampaignHandoff:
    def test_the_snippet_carries_the_page_s_campaign_into_the_frame(self):
        """An iframe sees none of the parent page's query string.

        Without this hand-off, every lead a customer's paid traffic produced was
        attributed to nothing, and their attribution report was one "direct" row.
        """
        snippet = build_embed_code("https://magai-widget-abc.vercel.app")

        assert "utm_source" in snippet
        assert "utm_campaign" in snippet
        assert "gclid" in snippet
        assert "location.search" in snippet
        # Bounded, because these values land in a URL we then load.
        assert "slice(0,200)" in snippet

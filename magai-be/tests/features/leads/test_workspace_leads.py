"""The workspace leads list, once it is bigger than one screen.

The screen used to build this itself: one unpaginated request per tool, fired in
parallel, with the failures discarded. That is fine with three leads and wrong
at the volumes the plans sell — and its failure mode was the worst one
available, because a dropped request looked exactly like an empty inbox.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.features.leads.models import Lead
from app.features.widgets.models import Widget


async def _widget(db, owner, title: str) -> Widget:
    widget = Widget(
        user_id=owner.id,
        target_url="https://example.com",
        widget_type="readiness_quiz",
        title=title,
        status="active",
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


async def _leads(db, widget: Widget, count: int, *, prefix: str = "person") -> None:
    base = datetime.now(UTC)
    for index in range(count):
        db.add(
            Lead(
                widget_id=widget.id,
                email=f"{prefix}{index:03d}@example.com",
                name=f"Person {index}",
                score=index,
                # Distinct timestamps, so "newest first" has one right answer.
                created_at=base - timedelta(minutes=index),
            )
        )
    await db.commit()


class TestPagination:
    async def test_a_page_is_a_page_and_the_total_is_the_truth(self, as_user, db, user):
        widget = await _widget(db, user, "Quiz")
        await _leads(db, widget, 60)

        response = await as_user(user).get("/api/leads?limit=25")

        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 25
        # The count an owner reads is the whole of what they have, not what fits.
        assert body["total"] == 60

    async def test_the_second_page_does_not_repeat_the_first(self, as_user, db, user):
        widget = await _widget(db, user, "Quiz")
        await _leads(db, widget, 60)

        first = (await as_user(user).get("/api/leads?limit=25&offset=0")).json()
        second = (await as_user(user).get("/api/leads?limit=25&offset=25")).json()

        assert {item["id"] for item in first["items"]}.isdisjoint(
            item["id"] for item in second["items"]
        )

    async def test_it_carries_the_tool_that_caught_each_lead(self, as_user, db, user):
        """Joined server-side: fifty rows must not become ten widget lookups."""
        widget = await _widget(db, user, "Practice Readiness Check")
        await _leads(db, widget, 2)

        body = (await as_user(user).get("/api/leads")).json()

        assert {item["widget_title"] for item in body["items"]} == {"Practice Readiness Check"}


class TestScoping:
    async def test_another_workspaces_leads_are_not_listed(self, as_user, db, user, other_user):
        mine = await _widget(db, user, "Mine")
        theirs = await _widget(db, other_user, "Theirs")
        await _leads(db, mine, 3, prefix="mine")
        await _leads(db, theirs, 5, prefix="theirs")

        body = (await as_user(user).get("/api/leads")).json()

        assert body["total"] == 3
        assert all("mine" in item["email"] for item in body["items"])

    async def test_requires_authentication(self, client):
        assert (await client.get("/api/leads")).status_code == 401


class TestFilters:
    async def test_searching_matches_email_and_name(self, as_user, db, user):
        widget = await _widget(db, user, "Quiz")
        db.add(Lead(widget_id=widget.id, email="ada@example.com", name="Ada Lovelace"))
        db.add(Lead(widget_id=widget.id, email="grace@example.com", name="Grace Hopper"))
        await db.commit()

        by_email = (await as_user(user).get("/api/leads?query=grace@")).json()
        by_name = (await as_user(user).get("/api/leads?query=Lovelace")).json()

        assert [item["email"] for item in by_email["items"]] == ["grace@example.com"]
        assert [item["email"] for item in by_name["items"]] == ["ada@example.com"]

    async def test_filtering_by_tool_narrows_the_total_too(self, as_user, db, user):
        """A count that ignores the filter beside it is worse than no count."""
        first = await _widget(db, user, "One")
        second = await _widget(db, user, "Two")
        await _leads(db, first, 4, prefix="one")
        await _leads(db, second, 7, prefix="two")

        body = (await as_user(user).get(f"/api/leads?widget_id={second.id}")).json()

        assert body["total"] == 7

    async def test_an_unknown_status_is_refused_rather_than_ignored(self, as_user, user):
        # Silently dropping it would show every lead under a filter that says
        # otherwise, which is the same failure as a filter that does nothing.
        response = await as_user(user).get("/api/leads?status=vip")
        assert response.status_code == 422

    async def test_a_malformed_tool_id_filters_to_nothing(self, as_user, db, user):
        widget = await _widget(db, user, "Quiz")
        await _leads(db, widget, 2)

        body = (await as_user(user).get("/api/leads?widget_id=not-a-uuid")).json()

        assert body["total"] == 0


class TestSorting:
    async def test_ordering_is_done_by_the_side_that_sees_every_row(self, as_user, db, user):
        """Sorting one page and calling the column sorted is a claim, not a fact."""
        widget = await _widget(db, user, "Quiz")
        await _leads(db, widget, 40)

        body = (await as_user(user).get("/api/leads?sort=score&direction=desc&limit=5")).json()

        scores = [item["score"] for item in body["items"]]
        assert scores == sorted(scores, reverse=True)
        # The highest score in the whole table, not the highest on page one.
        assert scores[0] == 39

    async def test_newest_first_by_default(self, as_user, db, user):
        widget = await _widget(db, user, "Quiz")
        await _leads(db, widget, 5)

        body = (await as_user(user).get("/api/leads")).json()

        stamps = [item["created_at"] for item in body["items"]]
        assert stamps == sorted(stamps, reverse=True)


class TestExport:
    async def test_the_download_honours_the_filters_on_screen(self, as_user, db, user):
        """Exporting the current page while the filter says 3,000 is a trap."""
        first = await _widget(db, user, "One")
        second = await _widget(db, user, "Two")
        await _leads(db, first, 30, prefix="one")
        await _leads(db, second, 3, prefix="two")

        response = await as_user(user).get(f"/api/leads/export.csv?widget_id={second.id}")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        body = response.text
        assert body.count("two") == 3
        assert "one000@example.com" not in body

    async def test_it_exports_past_the_first_page(self, as_user, db, user):
        widget = await _widget(db, user, "Quiz")
        await _leads(db, widget, 60)

        response = await as_user(user).get("/api/leads/export.csv")

        # Header plus every matching row, not the twenty-five the screen shows.
        assert len(response.text.strip().splitlines()) == 61

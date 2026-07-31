"""The free first look returns two real directions and survives account creation."""

from unittest.mock import AsyncMock

from sqlalchemy import func, select

from app.features.widgets.models import Widget
from app.features.widgets.service import create_guest_concept_token
from app.platform.pipeline.schemas import (
    ArchitectOutput,
    Blueprint,
    BlueprintList,
    BrandExtraction,
    MathLogic,
    SiteBrandEvidence,
    SiteEvidence,
    SitePageEvidence,
    WidgetType,
)


def _evidence() -> SiteEvidence:
    return SiteEvidence(
        target_url="https://example.com/",
        domain="example.com",
        business_name="Example",
        summary="Example business",
        pages=[SitePageEvidence(url="https://example.com/", title="Example")],
        references=[],
        brand=SiteBrandEvidence(),
        content_fingerprint="a" * 64,
        brand_fingerprint="b" * 64,
    )


def _blueprint(kind: WidgetType, number: int) -> Blueprint:
    return Blueprint(
        type=kind,
        title=f"Direction {number}",
        description=f"Description {number}",
        rationale=f"Reason {number}",
    )


def _architect(kind: WidgetType, number: int) -> ArchitectOutput:
    return ArchitectOutput(
        widget_type=kind,
        brand=BrandExtraction(
            primary_color="#18203a",
            secondary_color="#27304a",
            background_color="#f8f6ef",
            accent_color="#b8e430",
            font_headings="Inter",
            font_body="Inter",
            tone="clear and direct",
        ),
        logic=MathLogic(
            formula="volume * value",
            variables=[],
            example_calculation="10 * 100 = 1000",
        ),
        copywriting={"headline": f"Useful direction {number}", "cta": "See my result"},
    )


def _token() -> str:
    """A signed first look, exactly as the public endpoint would return one."""
    return create_guest_concept_token(
        "https://example.com/",
        [_blueprint(WidgetType.ROI_CALCULATOR, 1), _blueprint(WidgetType.READINESS_QUIZ, 2)],
        [_architect(WidgetType.ROI_CALCULATOR, 1), _architect(WidgetType.READINESS_QUIZ, 2)],
        _evidence(),
    )


async def test_guest_gets_two_concepts_and_can_claim_one(client, as_user, db, user, monkeypatch):
    blueprints = BlueprintList(
        blueprints=[
            _blueprint(WidgetType.ROI_CALCULATOR, 1),
            _blueprint(WidgetType.READINESS_QUIZ, 2),
        ]
    )
    monkeypatch.setattr(
        "app.features.widgets.routes.analyze_guest_url",
        AsyncMock(return_value=("https://example.com/", blueprints, _evidence())),
    )

    async def fake_architect(
        blueprint: Blueprint,
        _url: str,
        _evidence: SiteEvidence,
        *,
        brief=None,
    ) -> ArchitectOutput:
        assert brief is not None
        number = 1 if blueprint.type is WidgetType.ROI_CALCULATOR else 2
        return _architect(blueprint.type, number)

    monkeypatch.setattr("app.features.widgets.routes.run_architect_stage", fake_architect)

    first_look = await client.post(
        "/api/widgets/guest-concepts",
        json={
            "url": "https://example.com",
            "brief": {
                "mode": "guided",
                "audience": "Operations leaders",
                "goal": "capture_qualified_leads",
                "offer": "A planning call",
                "visitor_question": "Where is the workflow losing time?",
                "tone": "direct",
                "result_style": "action_plan",
                "question_count": 4,
                "instructions": "Keep it concise.",
            },
        },
    )

    assert first_look.status_code == 200
    body = first_look.json()
    assert len(body["concepts"]) == 2
    assert body["concepts"][0]["architect"]["widget_type"] == "roi_calculator"
    assert body["concepts"][1]["architect"]["widget_type"] == "readiness_quiz"
    assert body["brief"]["audience"] == "Operations leaders"

    # Claiming consumes a signed result and performs no network fetch. A DNS
    # outage after generation must not strand the result the visitor can see.
    monkeypatch.setattr(
        "app.features.widgets.service.validate_target_url",
        lambda _value: (_ for _ in ()).throw(AssertionError("unexpected DNS revalidation")),
    )
    claimed = await as_user(user).post(
        "/api/widgets/claim-guest",
        json={"session_token": body["session_token"], "selected_index": 1},
    )

    assert claimed.status_code == 200
    claim_body = claimed.json()
    assert claim_body["selected_index"] == 1
    assert claim_body["selected_concept"]["widget_type"] == "readiness_quiz"

    widget = await db.get(Widget, claim_body["widget_id"])
    assert widget is not None
    assert widget.user_id == user.id
    assert widget.target_url == "https://example.com/"
    assert len(widget.blueprints or []) == 2
    assert widget.title == "Direction 2"
    assert widget.widget_type == "readiness_quiz"
    assert widget.brand_tokens["accent_color"] == "#b8e430"
    assert widget.copywriting["headline"] == "Useful direction 2"
    assert widget.source_content_fingerprint == "a" * 64
    assert widget.creation_brief["result_style"] == "action_plan"


async def test_tampered_guest_session_is_rejected(as_user, user):
    response = await as_user(user).post(
        "/api/widgets/claim-guest",
        json={"session_token": "x" * 80, "selected_index": 0},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "guest_session_invalid"


async def test_generation_timeout_returns_a_retryable_service_error(client, monkeypatch):
    monkeypatch.setattr(
        "app.features.widgets.routes.analyze_guest_url",
        AsyncMock(side_effect=TimeoutError()),
    )

    response = await client.post(
        "/api/widgets/guest-concepts",
        json={"url": "https://example.com"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "generation_unavailable"


async def test_architect_timeout_uses_a_grounded_preview(client, monkeypatch):
    blueprints = BlueprintList(
        blueprints=[
            _blueprint(WidgetType.ROI_CALCULATOR, 1),
            _blueprint(WidgetType.READINESS_QUIZ, 2),
        ]
    )
    monkeypatch.setattr(
        "app.features.widgets.routes.analyze_guest_url",
        AsyncMock(return_value=("https://example.com/", blueprints, _evidence())),
    )
    monkeypatch.setattr(
        "app.features.widgets.routes.run_architect_stage",
        AsyncMock(side_effect=TimeoutError()),
    )

    response = await client.post(
        "/api/widgets/guest-concepts",
        json={"url": "https://example.com"},
    )

    assert response.status_code == 200
    concepts = response.json()["concepts"]
    assert len(concepts) == 2
    assert concepts[0]["architect"]["decision"]["lead_gate"] == "after_value"


class TestClaimIsIdempotent:
    """The same claim, sent twice, is one tool.

    The browser sends this at the moment an account is created — the one point
    in the journey where a refresh or a second click is most likely, and where
    the customer is least equipped to understand three identical drafts.
    """

    async def test_replaying_the_claim_returns_the_same_tool(self, as_user, db, user):
        token = _token()
        first = await as_user(user).post(
            "/api/widgets/claim-guest",
            json={"session_token": token, "selected_index": 0},
        )
        second = await as_user(user).post(
            "/api/widgets/claim-guest",
            json={"session_token": token, "selected_index": 0},
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["widget_id"] == second.json()["widget_id"]

        count = await db.scalar(select(func.count(Widget.id)).where(Widget.user_id == user.id))
        assert count == 1

    async def test_choosing_the_other_direction_is_a_different_claim(self, as_user, db, user):
        """Not a duplicate: they genuinely asked for the second concept too."""
        token = _token()
        first = await as_user(user).post(
            "/api/widgets/claim-guest",
            json={"session_token": token, "selected_index": 0},
        )
        second = await as_user(user).post(
            "/api/widgets/claim-guest",
            json={"session_token": token, "selected_index": 1},
        )

        assert first.json()["widget_id"] != second.json()["widget_id"]

    async def test_another_workspace_claiming_the_same_session_gets_its_own_tool(
        self, as_user, db, user, other_user
    ):
        token = _token()
        mine = await as_user(user).post(
            "/api/widgets/claim-guest",
            json={"session_token": token, "selected_index": 0},
        )
        theirs = await as_user(other_user).post(
            "/api/widgets/claim-guest",
            json={"session_token": token, "selected_index": 0},
        )

        assert mine.json()["widget_id"] != theirs.json()["widget_id"]

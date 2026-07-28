from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.features.leads.models import Lead
from app.features.widgets.models import Widget, WidgetInteraction
from app.features.widgets.service import portfolio_analytics
from app.features.widgets.service import test_widget_delivery as verify_delivery


async def _widget(db, owner) -> Widget:
    widget = Widget(
        user_id=owner.id,
        target_url="https://example.com",
        widget_type="readiness_quiz",
        title="Growth assessment",
        status="active",
        impressions_count=20,
        starts_count=2,
        completions_count=1,
        leads_count=1,
        cta_clicks_count=1,
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


async def test_portfolio_analytics_uses_owned_recorded_activity(db, user, other_user):
    widget = await _widget(db, user)
    other = await _widget(db, other_user)
    now = datetime.now(UTC)
    db.add_all(
        [
            WidgetInteraction(
                widget_id=widget.id,
                session_hash="a" * 64,
                started_at=now,
                completed_at=now,
                lead_submitted_at=now,
                last_step="result",
                source_url="https://google.com/search",
                attribution={"utm_source": "Google"},
            ),
            WidgetInteraction(
                widget_id=widget.id,
                session_hash="b" * 64,
                started_at=now,
                last_step="question_2",
                source_url="https://linkedin.com/feed",
            ),
            WidgetInteraction(
                widget_id=other.id,
                session_hash="c" * 64,
                started_at=now,
                last_step="private",
            ),
            Lead(widget_id=widget.id, email="buyer@example.com"),
        ]
    )
    await db.commit()

    result = await portfolio_analytics(db, user.id, period_days=30)

    assert result.totals["visitors"] == 20
    assert result.totals["leads"] == 1
    assert result.rates["lead_rate"] == 5.0
    assert result.experiences[0].title == "Growth assessment"
    assert {source.source for source in result.sources} == {"Google", "linkedin.com"}
    assert result.dropoff_by_step == {"question_2": 1}
    assert sum(day.leads for day in result.daily) == 1
    assert all(experience.id != str(other.id) for experience in result.experiences)


async def test_delivery_test_records_confirmed_connection(db, user):
    widget = await _widget(db, user)
    widget.delivery_webhook_url = "https://hooks.example.com/magnit"
    widget.delivery_webhook_secret = "test-signing-secret"
    widget.launch_settings = {"delivery_mode": "zapier"}
    await db.commit()

    with patch(
        "app.features.widgets.service.post_signed_webhook",
        new_callable=AsyncMock,
        return_value=(True, 204),
    ) as send:
        connected, status_code, checked_at = await verify_delivery(db, str(widget.id), user.id)

    assert connected is True
    assert status_code == 204
    assert checked_at.tzinfo is not None
    assert widget.launch_settings["delivery_status"] == "connected"
    assert widget.launch_settings["delivery_status_code"] == 204
    assert send.await_args.args[2] == "connection.test"

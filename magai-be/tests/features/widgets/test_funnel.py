from sqlalchemy import select

from app.features.widgets.models import Widget, WidgetInteraction
from app.features.widgets.schemas import TrackInteractionRequest
from app.features.widgets.service import record_interaction, widget_funnel


async def _active_widget(db, owner) -> Widget:
    widget = Widget(
        user_id=owner.id,
        target_url="https://example.com",
        widget_type="readiness_quiz",
        title="Readiness",
        status="active",
        impressions_count=10,
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)
    return widget


async def test_funnel_milestones_are_idempotent_per_visitor(db, user):
    widget = await _active_widget(db, user)
    start = TrackInteractionRequest(
        event="started",
        session_id="11111111-1111-4111-8111-111111111111",
        step="question_1",
    )
    complete = TrackInteractionRequest(
        event="completed",
        session_id=start.session_id,
        step="complete",
        result_key="ready",
    )

    await record_interaction(db, str(widget.id), start)
    await record_interaction(db, str(widget.id), start)
    await record_interaction(db, str(widget.id), complete)
    await record_interaction(db, str(widget.id), complete)
    await db.commit()
    await db.refresh(widget)

    interactions = (
        (
            await db.execute(
                select(WidgetInteraction).where(WidgetInteraction.widget_id == widget.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(interactions) == 1
    assert widget.starts_count == 1
    assert widget.completions_count == 1

    funnel = await widget_funnel(db, str(widget.id), user.id)
    assert funnel.start_rate == 10.0
    assert funnel.completion_rate == 100.0

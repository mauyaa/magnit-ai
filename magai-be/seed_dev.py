"""Seed a local SQLite database with a realistic account, so the app screens
can be looked at with content in them rather than as empty states.

Creates the schema with metadata.create_all rather than Alembic: the initial
migration uses `server_default=now()`, which is Postgres-only, so `alembic
upgrade head` cannot run against SQLite. Production still goes through Alembic.
"""

import asyncio
import hashlib
import logging
import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("MAGAI_ENVIRONMENT", "development")
os.environ.setdefault("MAGAI_SECRET_KEY", "dev-secret-key-long-enough-for-hs256-signing-abcdef")

# Populate Base.metadata with the complete model graph before create_all runs.
import app.platform.db.models  # noqa: F401
from app.features.leads.models import Lead
from app.features.users.models import User
from app.features.widgets.models import Widget, WidgetHealEvent, WidgetInteraction
from app.platform.db.base import Base
from app.platform.db.session import async_session_factory, engine
from app.platform.security.passwords import hash_password

logger = logging.getLogger("seed")

EMAIL = "founder@magnitai.dev"
PASSWORD = "correct-horse-battery-99"


def embed_for(host: str) -> str:
    return f'<iframe src="https://{host}" width="100%" height="640" style="border:0"></iframe>'


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        user = User(
            email=EMAIL,
            password_hash=hash_password(PASSWORD),
            role="owner",
            email_verified=True,
            email_verified_at=datetime.now(UTC),
        )
        db.add(user)
        await db.flush()

        calc = Widget(
            user_id=user.id,
            target_url="https://northsidedental.com",
            widget_type="roi_calculator",
            title="Practice growth calculator",
            status="active",
            deployment_url="https://magai-widget-nsd41.vercel.app",
            embed_code=embed_for("magai-widget-nsd41.vercel.app"),
            leads_count=18,
            impressions_count=734,
            starts_count=308,
            completions_count=196,
            cta_clicks_count=73,
            lead_cap=500,
            brand_tokens={"primary_color": "#0B6F87", "font_headings": "Iowan Old Style"},
            deployed_at=datetime.now(UTC) - timedelta(days=9),
        )
        quiz = Widget(
            user_id=user.id,
            target_url="https://meridian-legal.com",
            widget_type="readiness_quiz",
            title="Are you ready to incorporate?",
            status="active",
            deployment_url="https://magai-widget-mrd88.vercel.app",
            embed_code=embed_for("magai-widget-mrd88.vercel.app"),
            leads_count=7,
            impressions_count=181,
            starts_count=82,
            completions_count=58,
            cta_clicks_count=19,
            lead_cap=500,
            deployed_at=datetime.now(UTC) - timedelta(days=3),
        )
        building = Widget(
            user_id=user.id,
            target_url="https://helios-solar.co",
            widget_type="audit_tool",
            title="Roof suitability audit",
            status="building",
            build_stage="codegen",
            build_progress=64,
            lead_cap=500,
        )
        db.add_all([calc, quiz, building])
        await db.flush()

        names = [
            ("dana.whitfield@gmail.com", "Dana Whitfield", 82, 1),
            ("r.okonkwo@brightpath.co", "Rotimi Okonkwo", 74, 2),
            ("hello@saltmarshcafe.com", None, 61, 4),
            ("j.pereira@northwind.io", "Júlia Pereira", 90, 6),
            ("mm@studio-mm.design", "Mira Mensah", 55, 11),
        ]
        for email, name, score, days in names:
            db.add(
                Lead(
                    widget_id=calc.id,
                    email=email,
                    name=name,
                    score=score,
                    created_at=datetime.now(UTC) - timedelta(days=days, hours=3),
                )
            )
        db.add(
            Lead(
                widget_id=quiz.id,
                email="ops@meridianclients.com",
                name="Sam Ellery",
                score=48,
                created_at=datetime.now(UTC) - timedelta(hours=5),
            )
        )

        interaction_rows = [
            (calc, "calc-linkedin-1", 1, "LinkedIn", "result", True, True),
            (calc, "calc-google-1", 2, "Google", "result", True, True),
            (calc, "calc-direct-1", 3, None, "question_3", False, False),
            (calc, "calc-linkedin-2", 5, "LinkedIn", "result", True, True),
            (calc, "calc-partner-1", 7, "Partner", "question_2", False, False),
            (quiz, "quiz-google-1", 1, "Google", "result", True, True),
            (quiz, "quiz-linkedin-1", 4, "LinkedIn", "question_3", False, False),
            (quiz, "quiz-direct-1", 6, None, "result", True, False),
        ]
        for item, session, days, source, step, completed, submitted in interaction_rows:
            occurred_at = datetime.now(UTC) - timedelta(days=days, hours=2)
            db.add(
                WidgetInteraction(
                    widget_id=item.id,
                    session_hash=hashlib.sha256(session.encode()).hexdigest(),
                    started_at=occurred_at,
                    completed_at=occurred_at + timedelta(minutes=2) if completed else None,
                    result_viewed_at=occurred_at + timedelta(minutes=2) if completed else None,
                    lead_submitted_at=occurred_at + timedelta(minutes=3) if submitted else None,
                    last_step=step,
                    source_url=(f"https://{source.lower()}.com/campaign" if source else None),
                    attribution={"utm_source": source} if source else None,
                    created_at=occurred_at,
                )
            )

        db.add(
            WidgetHealEvent(
                widget_id=calc.id,
                check_type="brand_drift",
                status="healed",
                diff_summary={
                    "primary_color": {"old": "#0B6F87", "new": "#0A5F73"},
                    "font_headings": {"old": "Iowan Old Style", "new": "Source Serif 4"},
                },
                detected_at=datetime.now(UTC) - timedelta(days=2),
                healed_at=datetime.now(UTC) - timedelta(days=2, minutes=-14),
            )
        )
        await db.commit()

    logger.warning("seeded %s / %s", EMAIL, PASSWORD)


asyncio.run(main())

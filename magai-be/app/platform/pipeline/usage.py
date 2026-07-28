from __future__ import annotations

import json
import logging
import math
import uuid
from typing import Any

from pydantic import BaseModel

from app.platform.config.settings import settings
from app.platform.db.session import async_session_factory
from app.platform.pipeline.models import GenerationUsage

logger = logging.getLogger(__name__)


def _text(value: Any) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


def _estimated_tokens(value: Any) -> int:
    # Provider metadata is not exposed by every supported agent transport. Four
    # characters/token is intentionally marked as an estimate in the ledger.
    return max(1, math.ceil(len(_text(value)) / 4))


async def record_generation_usage(
    *,
    stage: str,
    input_value: Any,
    output_value: Any = "",
    duration_ms: int,
    widget_id: str | None = None,
    succeeded: bool = True,
    error_code: str | None = None,
) -> None:
    """Best-effort cost accounting that can never break generation."""
    try:
        parsed_widget_id = uuid.UUID(widget_id) if widget_id else None
        input_tokens = _estimated_tokens(input_value)
        output_tokens = _estimated_tokens(output_value) if output_value else 0
        cost_microusd = round(
            input_tokens * settings.model_input_usd_per_million_tokens
            + output_tokens * settings.model_output_usd_per_million_tokens
        )
        async with async_session_factory() as db:
            db.add(
                GenerationUsage(
                    widget_id=parsed_widget_id,
                    stage=stage,
                    model=settings.agy_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_microusd=cost_microusd,
                    estimated=True,
                    duration_ms=max(0, duration_ms),
                    succeeded=succeeded,
                    error_code=error_code[:500] if error_code else None,
                )
            )
            await db.commit()
    except Exception:
        logger.warning("Could not persist generation usage for %s", stage, exc_info=True)

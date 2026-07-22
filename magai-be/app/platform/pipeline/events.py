from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncGenerator

import redis.asyncio as aioredis

from app.platform.config.settings import settings

logger = logging.getLogger(__name__)

STREAM_MAXLEN = 100
KEEPALIVE_TIMEOUT = 30.0
XREAD_BLOCK_MS = int(KEEPALIVE_TIMEOUT * 1000)

_stream_key = lambda w: f"widget:{w}:events"


@dataclass
class PipelineEvent:
    stage: str
    status: str
    message: str
    data: dict | None = None
    progress: float | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RedisEventManager:
    def __init__(self) -> None:
        self._pool: aioredis.ConnectionPool | None = None

    async def _redis(self) -> aioredis.Redis:
        if self._pool is None:
            self._pool = aioredis.ConnectionPool.from_url(
                settings.redis_url, max_connections=10,
            )
        return aioredis.Redis(connection_pool=self._pool)

    async def publish(self, widget_id: str, event: PipelineEvent) -> None:
        r = await self._redis()
        await r.xadd(
            _stream_key(widget_id),
            {
                "stage": event.stage,
                "status": event.status,
                "message": event.message,
                "data": json.dumps(event.data) if event.data else "",
                "progress": str(event.progress) if event.progress is not None else "",
                "timestamp": event.timestamp,
            },
            maxlen=STREAM_MAXLEN,
        )

    async def publish_stage(
        self,
        widget_id: str,
        stage: str,
        status: str,
        message: str,
        data: dict | None = None,
        progress: float | None = None,
    ) -> None:
        await self.publish(
            widget_id,
            PipelineEvent(
                stage=stage,
                status=status,
                message=message,
                data=data,
                progress=progress,
            ),
        )

    async def event_stream(self, widget_id: str) -> AsyncGenerator[str, None]:
        r = await self._redis()
        stream = _stream_key(widget_id)

        last_id = "0"
        result = await r.xread({stream: last_id}, count=STREAM_MAXLEN)
        if result:
            for _, entries in result:
                for entry_id, fields in entries:
                    yield _format_sse(fields)
                    last_id = entry_id

        while True:
            try:
                result = await asyncio.wait_for(
                    r.xread({stream: last_id}, block=XREAD_BLOCK_MS, count=10),
                    timeout=KEEPALIVE_TIMEOUT + 5.0,
                )
                if result:
                    for _, entries in result:
                        for entry_id, fields in entries:
                            yield _format_sse(fields)
                            last_id = entry_id
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"


def _format_sse(fields: dict) -> str:
    payload = {
        "stage": fields.get(b"stage", b"").decode(),
        "status": fields.get(b"status", b"").decode(),
        "message": fields.get(b"message", b"").decode(),
        "data": _parse_json_field(fields.get(b"data", b"")),
        "progress": _parse_float_field(fields.get(b"progress", b"")),
        "timestamp": fields.get(b"timestamp", b"").decode(),
    }
    return f"data: {json.dumps(payload)}\n\n"


def _parse_json_field(raw: bytes) -> dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _parse_float_field(raw: bytes) -> float | None:
    if not raw:
        return None
    try:
        return float(raw.decode())
    except (ValueError, UnicodeDecodeError):
        return None


events = RedisEventManager()

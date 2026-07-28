#!/usr/bin/env python3
"""Load test for MagnetAI's read and public-write paths.

Deliberately excludes ``/analyze`` and ``/build``: each of those spends real Gemini
and Vercel budget, so load-testing them costs money and would be rate-limited after
a handful of calls anyway. What this measures is the surface that actually takes
sustained traffic:

* ``POST /api/widgets/{id}/impression`` — every widget view, the highest-volume
  endpoint in the system
* ``POST /api/leads/{id}``             — public lead submission
* ``GET  /api/widgets``                — the dashboard poll (every 15s per open tab)
* ``GET  /health/ready``               — the load balancer probe

Usage:
    python ops/scripts/loadtest.py --url http://localhost:8000 --duration 30
    python ops/scripts/loadtest.py --url http://localhost:8000 --concurrency 100 \\
        --token "$ACCESS_TOKEN" --widget-id "$WIDGET_ID"

Requires only httpx, which the backend already depends on.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field

import httpx


@dataclass
class Results:
    latencies_ms: list[float] = field(default_factory=list)
    statuses: Counter[int] = field(default_factory=Counter)
    errors: Counter[str] = field(default_factory=Counter)

    def record(self, status: int, elapsed_ms: float) -> None:
        self.statuses[status] += 1
        self.latencies_ms.append(elapsed_ms)

    def record_error(self, exc: Exception) -> None:
        self.errors[type(exc).__name__] += 1

    def summary(self, label: str, duration_s: float) -> str:
        total = sum(self.statuses.values())
        failed = sum(count for status, count in self.statuses.items() if status >= 500)
        rate_limited = self.statuses.get(429, 0)

        if not self.latencies_ms:
            return f"{label:<34} no successful requests ({dict(self.errors)})"

        ordered = sorted(self.latencies_ms)
        p50 = statistics.median(ordered)
        p95 = ordered[int(len(ordered) * 0.95) - 1] if len(ordered) > 1 else ordered[0]
        p99 = ordered[int(len(ordered) * 0.99) - 1] if len(ordered) > 1 else ordered[0]

        return (
            f"{label:<34} "
            f"{total / duration_s:8.1f} rps  "
            f"p50 {p50:7.1f}ms  p95 {p95:7.1f}ms  p99 {p99:7.1f}ms  "
            f"5xx {failed:<5} 429 {rate_limited:<5} errors {sum(self.errors.values())}"
        )


async def _hammer(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    results: Results,
    deadline: float,
    headers: dict[str, str] | None = None,
    json_body: dict | None = None,
) -> None:
    """Issue requests back-to-back until the deadline passes."""
    while time.monotonic() < deadline:
        started = time.perf_counter()
        try:
            response = await client.request(method, path, headers=headers, json=json_body)
            results.record(response.status_code, (time.perf_counter() - started) * 1000)
        except Exception as exc:  # noqa: BLE001 - any transport failure is a data point
            results.record_error(exc)


async def run_scenario(
    name: str,
    base_url: str,
    method: str,
    path: str,
    concurrency: int,
    duration: float,
    headers: dict[str, str] | None = None,
    json_body: dict | None = None,
) -> tuple[str, Results, float]:
    results = Results()
    limits = httpx.Limits(max_connections=concurrency + 10, max_keepalive_connections=concurrency)

    started = time.monotonic()
    deadline = started + duration
    async with httpx.AsyncClient(base_url=base_url, timeout=30, limits=limits) as client:
        await asyncio.gather(
            *(
                _hammer(client, method, path, results, deadline, headers, json_body)
                for _ in range(concurrency)
            )
        )
    return name, results, time.monotonic() - started


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--duration", type=float, default=15.0, help="seconds per scenario")
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument("--token", default="", help="access token, for authenticated scenarios")
    parser.add_argument("--widget-id", default="", help="a live widget id for public endpoints")
    args = parser.parse_args()

    print(f"Target      {args.url}")
    print(f"Concurrency {args.concurrency}   Duration {args.duration}s per scenario\n")

    scenarios: list[tuple] = [
        ("GET /health/ready", "GET", "/health/ready", None, None),
        ("GET /health/live", "GET", "/health/live", None, None),
    ]

    if args.token:
        auth = {"Authorization": f"Bearer {args.token}"}
        scenarios.append(("GET /api/widgets (dashboard)", "GET", "/api/widgets", auth, None))
        scenarios.append(("GET /api/auth/me", "GET", "/api/auth/me", auth, None))
    else:
        print("note: --token not given, skipping authenticated scenarios\n")

    if args.widget_id:
        scenarios.append(
            (
                "POST impression (widget view)",
                "POST",
                f"/api/widgets/{args.widget_id}/impression",
                None,
                None,
            )
        )
        scenarios.append(
            (
                "POST lead (public capture)",
                "POST",
                f"/api/leads/{args.widget_id}",
                None,
                {"email": "loadtest@example.com", "name": "Load Test"},
            )
        )
    else:
        print("note: --widget-id not given, skipping public widget scenarios\n")

    summaries = []
    for name, method, path, headers, body in scenarios:
        print(f"running {name} ...", flush=True)
        label, results, elapsed = await run_scenario(
            name, args.url, method, path, args.concurrency, args.duration, headers, body
        )
        summaries.append(results.summary(label, elapsed))

    print("\n" + "=" * 118)
    for line in summaries:
        print(line)
    print("=" * 118)
    print(
        "\nInterpreting this: sustained 5xx means the app is failing under load, "
        "while 429s are the rate limiter working as designed.\n"
        "Read paths should stay well under 100ms p95; the impression endpoint is a "
        "single indexed UPDATE and should be the fastest write."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""Prometheus metrics.

Falls back to no-op stubs when ``prometheus-client`` is absent so metrics are
never a hard dependency of serving traffic. Route labels use the *path template*
(``/api/widgets/{widget_id}``) rather than the concrete path, so widget ids do not
explode cardinality.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class _NoOpMetric:
    """Absorbs every metric operation and records nothing.

    Used when ``prometheus-client`` is not installed, so instrumentation call
    sites never need import guards of their own.
    """

    def labels(self, *_args: Any, **_kwargs: Any) -> _NoOpMetric:
        return self

    def inc(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def dec(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def set(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def observe(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _no_op_metric(*_args: Any, **_kwargs: Any) -> _NoOpMetric:
    return _NoOpMetric()


def _no_op_render() -> bytes:
    return b"# prometheus-client not installed\n"


# The whole module is imported behind one optional name, then the public
# factories are bound from it. Binding through a module reference rather than
# re-assigning imported symbols keeps a single declared type for each name whether
# or not the dependency is installed.
_prometheus: Any
try:
    import prometheus_client as _prometheus

    METRICS_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extra
    _prometheus = None
    METRICS_AVAILABLE = False

Counter: Any = _prometheus.Counter if _prometheus else _no_op_metric
Gauge: Any = _prometheus.Gauge if _prometheus else _no_op_metric
Histogram: Any = _prometheus.Histogram if _prometheus else _no_op_metric
generate_latest: Any = _prometheus.generate_latest if _prometheus else _no_op_render
CONTENT_TYPE_LATEST: str = (
    _prometheus.CONTENT_TYPE_LATEST if _prometheus else "text/plain; charset=utf-8"
)


http_requests_total = Counter(
    "magai_http_requests_total",
    "HTTP requests by method, route template and status.",
    ["method", "route", "status"],
)

http_request_duration_seconds = Histogram(
    "magai_http_request_duration_seconds",
    "HTTP request latency by route template.",
    ["method", "route"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

pipeline_builds_total = Counter(
    "magai_pipeline_builds_total",
    "Widget build outcomes.",
    ["outcome"],  # started | succeeded | failed
)

pipeline_build_duration_seconds = Histogram(
    "magai_pipeline_build_duration_seconds",
    "End-to-end widget build duration.",
    buckets=(15, 30, 60, 120, 300, 600, 1200),
)

heal_checks_total = Counter(
    "magai_heal_checks_total",
    "Self-heal check outcomes.",
    ["check_type", "result"],  # result: no_drift | healed | failed
)

heal_sweep_widgets = Gauge(
    "magai_heal_sweep_widgets",
    "Widgets examined by the most recent self-heal sweep.",
)

leads_captured_total = Counter(
    "magai_leads_captured_total",
    "Leads submitted through deployed widgets.",
)

widget_impressions_total = Counter(
    "magai_widget_impressions_total",
    "Views recorded by deployed widgets — the denominator for conversion rate.",
)


def _route_template(request: Request) -> str:
    """The matched route's path template, or ``unmatched`` for 404s."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Record the failure before the exception handler converts it to a 500.
            http_requests_total.labels(request.method, _route_template(request), "500").inc()
            raise

        elapsed = time.perf_counter() - started
        route = _route_template(request)
        http_requests_total.labels(request.method, route, str(response.status_code)).inc()
        http_request_duration_seconds.labels(request.method, route).observe(elapsed)
        return response


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST

import math
from collections import Counter, deque
from collections.abc import Mapping
from threading import Lock
from time import perf_counter
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from clara_api.core.careguard_metrics import _percentile
from clara_api.core.config import get_settings


class APIMetricsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests_total = 0
        self._latency_total_ms = 0.0
        self._by_route: Counter[str] = Counter()
        self._by_status: Counter[str] = Counter()

    def record(self, route: str, status_code: int, latency_ms: float) -> None:
        with self._lock:
            self._requests_total += 1
            self._latency_total_ms += latency_ms
            self._by_route[route] += 1
            self._by_status[str(status_code)] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            requests_total = self._requests_total
            avg_latency_ms = self._latency_total_ms / requests_total if requests_total else 0.0
            return {
                "requests_total": requests_total,
                "by_route": dict(self._by_route),
                "by_status": dict(self._by_status),
                "avg_latency_ms": round(avg_latency_ms, 3),
            }


# Bound the per-route latency sample ring so the projection stays O(1) in memory
# regardless of traffic; percentiles are computed over the retained window.
_MAX_ROUTE_LATENCY_SAMPLES = 1024


class MetricsPercentiles:
    """Bounded per-route latency sample rings with a p50/p90/p99 projection.

    Optional, flag-gated companion to ``APIMetricsStore`` (Requirement 5.2):
    when ``admin_observability_percentiles_enabled`` is on the metrics
    middleware records each request's route latency here and the
    ``/system/metrics`` surface exposes the per-route percentiles alongside the
    existing average. With the flag off nothing is recorded and the metrics
    surface returns its average-only baseline, byte-equivalent to today
    (Requirements 5.1, 12.2).

    Percentiles reuse the proven, monotonic ``_percentile`` helper (linear
    interpolation), so for any fixed sample set ``p50 <= p90 <= p99``
    (Requirement 5.3).
    """

    def __init__(self, max_samples: int = _MAX_ROUTE_LATENCY_SAMPLES) -> None:
        self._lock = Lock()
        self._max_samples = max_samples
        self._samples: dict[str, deque[float]] = {}

    def record(self, route: str, latency_ms: float) -> None:
        try:
            value = float(latency_ms)
        except (TypeError, ValueError):
            return
        if value < 0.0 or math.isnan(value) or math.isinf(value):
            return
        with self._lock:
            ring = self._samples.get(route)
            if ring is None:
                ring = deque(maxlen=self._max_samples)
                self._samples[route] = ring
            ring.append(value)

    def percentiles(self, route: str) -> dict[str, float]:
        with self._lock:
            samples = list(self._samples.get(route, ()))
        return _project_percentiles(samples)

    def snapshot(self) -> dict[str, dict[str, float]]:
        with self._lock:
            routes = {route: list(ring) for route, ring in self._samples.items()}
        return {route: _project_percentiles(samples) for route, samples in routes.items()}

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()


def _project_percentiles(samples: list[float]) -> dict[str, float]:
    return {
        "p50_ms": round(_percentile(samples, 50.0), 3),
        "p90_ms": round(_percentile(samples, 90.0), 3),
        "p99_ms": round(_percentile(samples, 99.0), 3),
    }


_metrics_percentiles = MetricsPercentiles()


def get_metrics_percentiles() -> MetricsPercentiles:
    return _metrics_percentiles


_UNKNOWN_ROUTE_LABEL = "__unknown__"


def _resolve_route(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None:
        route_path = getattr(route, "path", None)
        if isinstance(route_path, str) and route_path:
            return route_path
    return _UNKNOWN_ROUTE_LABEL


class APIMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed_ms = (perf_counter() - started) * 1000
            route = _resolve_route(request)
            get_api_metrics_store().record(route, status_code, elapsed_ms)
            if get_settings().admin_observability_percentiles_enabled:
                get_metrics_percentiles().record(route, elapsed_ms)


_api_metrics_store = APIMetricsStore()


def get_api_metrics_store() -> APIMetricsStore:
    return _api_metrics_store


def _prometheus_label_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _coerce_non_negative_int(value: Any) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _coerce_non_negative_float(value: Any) -> float:
    try:
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        return 0.0


def format_metrics_prometheus(snapshot: Mapping[str, Any]) -> str:
    requests_total = _coerce_non_negative_int(snapshot.get("requests_total"))
    avg_latency_ms = _coerce_non_negative_float(snapshot.get("avg_latency_ms"))

    by_route_raw = snapshot.get("by_route")
    by_status_raw = snapshot.get("by_status")
    by_route = by_route_raw if isinstance(by_route_raw, Mapping) else {}
    by_status = by_status_raw if isinstance(by_status_raw, Mapping) else {}

    lines = [
        "# HELP requests_total Total API requests observed.",
        "# TYPE requests_total counter",
        f"requests_total {requests_total}",
        "# HELP avg_latency_ms Average API request latency in milliseconds.",
        "# TYPE avg_latency_ms gauge",
        f"avg_latency_ms {avg_latency_ms:.3f}",
        "# HELP by_route API request counts by route.",
        "# TYPE by_route counter",
    ]

    for route, count in sorted(by_route.items(), key=lambda item: str(item[0])):
        lines.append(
            f'by_route{{route="{_prometheus_label_escape(str(route))}"}} '
            f"{_coerce_non_negative_int(count)}"
        )

    lines.extend(
        [
            "# HELP by_status API request counts by status code.",
            "# TYPE by_status counter",
        ]
    )

    for status, count in sorted(by_status.items(), key=lambda item: str(item[0])):
        lines.append(
            f'by_status{{status="{_prometheus_label_escape(str(status))}"}} '
            f"{_coerce_non_negative_int(count)}"
        )

    return "\n".join(lines) + "\n"

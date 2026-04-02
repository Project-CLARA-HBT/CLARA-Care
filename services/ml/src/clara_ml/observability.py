from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from threading import Lock


class InMemoryMetricsCollector:
    """Minimal in-memory metrics for service observability."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests_total = 0
        self._error_total = 0
        self._total_latency_ms = 0.0
        self._by_path: dict[str, int] = defaultdict(int)

    def record(self, *, path: str, latency_ms: float, status_code: int) -> None:
        with self._lock:
            self._requests_total += 1
            self._total_latency_ms += max(0.0, latency_ms)
            self._by_path[path or "/"] += 1
            if status_code >= 400:
                self._error_total += 1

    def snapshot(self) -> dict:
        with self._lock:
            requests_total = self._requests_total
            avg_latency_ms = (
                self._total_latency_ms / requests_total if requests_total else 0.0
            )
            return {
                "requests_total": requests_total,
                "by_path": dict(sorted(self._by_path.items())),
                "error_total": self._error_total,
                "avg_latency_ms": round(avg_latency_ms, 3),
            }

    def reset(self) -> None:
        with self._lock:
            self._requests_total = 0
            self._error_total = 0
            self._total_latency_ms = 0.0
            self._by_path.clear()


metrics_collector = InMemoryMetricsCollector()


def _prometheus_label_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _coerce_non_negative_int(value: object) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _coerce_non_negative_float(value: object) -> float:
    try:
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        return 0.0


def format_metrics_prometheus(snapshot: Mapping[str, object]) -> str:
    requests_total = _coerce_non_negative_int(snapshot.get("requests_total"))
    error_total = _coerce_non_negative_int(snapshot.get("error_total"))
    avg_latency_ms = _coerce_non_negative_float(snapshot.get("avg_latency_ms"))

    by_path_raw = snapshot.get("by_path")
    by_path = by_path_raw if isinstance(by_path_raw, Mapping) else {}

    lines = [
        "# HELP requests_total Total ML service requests observed.",
        "# TYPE requests_total counter",
        f"requests_total {requests_total}",
        "# HELP error_total Total ML service requests with HTTP status >= 400.",
        "# TYPE error_total counter",
        f"error_total {error_total}",
        "# HELP avg_latency_ms Average ML service request latency in milliseconds.",
        "# TYPE avg_latency_ms gauge",
        f"avg_latency_ms {avg_latency_ms:.3f}",
        "# HELP by_path ML service request counts by path.",
        "# TYPE by_path counter",
    ]

    for path, count in sorted(by_path.items(), key=lambda item: str(item[0])):
        lines.append(
            f'by_path{{path="{_prometheus_label_escape(str(path))}"}} '
            f"{_coerce_non_negative_int(count)}"
        )

    return "\n".join(lines) + "\n"

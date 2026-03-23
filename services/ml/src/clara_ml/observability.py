from __future__ import annotations

from collections import defaultdict
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

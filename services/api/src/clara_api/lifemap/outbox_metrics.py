"""Bounded, no-PII metrics for the standalone LifeMap worker."""

from __future__ import annotations

from collections import Counter, deque
from threading import Lock


class LifeMapOutboxMetrics:
    def __init__(self, max_cycles: int = 256) -> None:
        self._lock = Lock()
        self._outcomes: Counter[str] = Counter()
        self._cycle_ms: deque[float] = deque(maxlen=max_cycles)

    def record_outcome(self, outcome: str, count: int = 1) -> None:
        with self._lock:
            self._outcomes[outcome] += max(0, count)

    def record_cycle(self, duration_ms: float) -> None:
        with self._lock:
            self._cycle_ms.append(max(0.0, float(duration_ms)))

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            samples = sorted(self._cycle_ms)
            outcomes = dict(self._outcomes)
        p95 = samples[min(len(samples) - 1, int(len(samples) * 0.95))] if samples else 0.0
        return {
            "outcomes": outcomes,
            "cycles": len(samples),
            "cycle_p95_ms": round(p95, 3),
        }

    def reset(self) -> None:
        with self._lock:
            self._outcomes.clear()
            self._cycle_ms.clear()


_store = LifeMapOutboxMetrics()


def get_lifemap_outbox_metrics() -> LifeMapOutboxMetrics:
    return _store

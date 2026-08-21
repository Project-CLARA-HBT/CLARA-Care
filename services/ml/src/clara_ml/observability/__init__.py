from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from threading import Lock


class InMemoryMetricsCollector:
    """Minimal in-memory metrics for service observability."""

    def __init__(self, *, max_paths: int = 512, overflow_label: str = "__other__") -> None:
        self._lock = Lock()
        self._requests_total = 0
        self._error_total = 0
        self._total_latency_ms = 0.0
        self._by_path: dict[str, int] = defaultdict(int)
        self._max_paths = max(int(max_paths), 1)
        self._overflow_label = overflow_label or "__other__"

    def record(self, *, path: str, latency_ms: float, status_code: int) -> None:
        with self._lock:
            self._requests_total += 1
            self._total_latency_ms += max(0.0, latency_ms)
            normalized_path = path or "/"
            if normalized_path in self._by_path or len(self._by_path) < self._max_paths:
                self._by_path[normalized_path] += 1
            else:
                self._by_path[self._overflow_label] += 1
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


class ModelRoutingEvidenceCollector:
    """Bounded aggregate evidence of registry selections.

    This collector is intentionally narrower than request telemetry.  It sees
    only registry-produced categorical values and persists neither request
    identity, model identifier, prompt, input, output, endpoint nor provider
    credential.  Callers must gate writes with the dedicated deployment flag;
    when that flag is off, this instance remains empty and request behavior is
    unchanged.
    """

    _SAFE_PROFILES = frozenset({"pro", "flash", "legacy", "rollback"})
    _SAFE_RISKS = frozenset({"low", "medium", "high", "critical"})
    _SAFE_MODEL_VERSIONS = frozenset(
        {
            "deepseek-v4-pro.task-route.v1",
            "deepseek-v4-flash.task-route.v1",
            "deepseek-rollback.v1",
        }
    )

    def __init__(self, *, max_series: int = 128) -> None:
        self._lock = Lock()
        self._max_series = max(int(max_series), 1)
        self._selection_total = 0
        self._overflow_total = 0
        self._by_selection: dict[tuple[str, str, str, str, bool], int] = defaultdict(int)

    @classmethod
    def _safe_task(cls, task: object) -> str:
        """Keep task labels categorical even if a future caller is malformed."""

        value = str(task)
        if not value or len(value) > 96 or not all(
            char.islower() or char.isdigit() or char == "_" for char in value
        ):
            return "unknown"
        return value

    @classmethod
    def _safe_choice(cls, value: object, allowed: frozenset[str]) -> str:
        candidate = str(value)
        return candidate if candidate in allowed else "unknown"

    def record_selection(
        self,
        *,
        task: object,
        profile: object,
        model_version: object,
        risk_level: object,
        rollback_applied: object,
    ) -> None:
        """Record one registry decision without retaining a request-level trace."""

        key = (
            self._safe_task(task),
            self._safe_choice(profile, self._SAFE_PROFILES),
            self._safe_choice(model_version, self._SAFE_MODEL_VERSIONS),
            self._safe_choice(risk_level, self._SAFE_RISKS),
            bool(rollback_applied),
        )
        with self._lock:
            self._selection_total += 1
            if key not in self._by_selection and len(self._by_selection) >= self._max_series:
                self._overflow_total += 1
                return
            self._by_selection[key] += 1

    def snapshot(self) -> dict[str, object]:
        """Return a deterministic, PII-free aggregate suitable for internal ops."""

        with self._lock:
            rows = [
                {
                    "task": task,
                    "profile": profile,
                    "model_version": model_version,
                    "risk_level": risk_level,
                    "rollback_applied": rollback_applied,
                    "count": count,
                }
                for (task, profile, model_version, risk_level, rollback_applied), count in sorted(
                    self._by_selection.items()
                )
            ]
            return {
                "selection_total": self._selection_total,
                "overflow_total": self._overflow_total,
                "by_selection": rows,
            }

    def reset(self) -> None:
        """Clear aggregates; used only by process lifecycle/tests."""

        with self._lock:
            self._selection_total = 0
            self._overflow_total = 0
            self._by_selection.clear()


model_routing_evidence = ModelRoutingEvidenceCollector()


def _prometheus_label_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _coerce_non_negative_int(value: object) -> int:
    try:
        if isinstance(value, (int, float, str, bytes, bytearray)):
            return max(int(value), 0)
        return 0
    except (TypeError, ValueError):
        return 0


def _coerce_non_negative_float(value: object) -> float:
    try:
        if isinstance(value, (int, float, str, bytes, bytearray)):
            return max(float(value), 0.0)
        return 0.0
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

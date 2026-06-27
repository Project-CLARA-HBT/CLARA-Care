from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Any

_DEFAULT_FLOW_EVENT_CAPACITY = 1_000


class FlowEventStore:
    def __init__(self, *, capacity: int = _DEFAULT_FLOW_EVENT_CAPACITY) -> None:
        self._capacity = max(1, capacity)
        self._events: deque[dict[str, Any]] = deque(maxlen=self._capacity)
        self._lock = Lock()
        self._next_sequence = 1

    @property
    def capacity(self) -> int:
        return self._capacity

    def latest_sequence(self) -> int:
        with self._lock:
            return self._next_sequence - 1

    def append(
        self,
        *,
        source: str,
        user_id: str,
        role: str,
        intent: str | None,
        model_used: str | None,
        event: dict[str, Any],
        flow_events_missing: bool = False,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "sequence": 0,
            "timestamp": occurred_at or datetime.now(tz=UTC).isoformat(),
            "source": source,
            "user_id": user_id,
            "role": role,
            "intent": intent,
            "model_used": model_used,
            "flow_events_missing": flow_events_missing,
            "event": deepcopy(event),
        }
        with self._lock:
            record["sequence"] = self._next_sequence
            self._next_sequence += 1
            self._events.append(record)
        self._mirror_to_sink(record)
        return deepcopy(record)

    @staticmethod
    def _mirror_to_sink(record: dict[str, Any]) -> None:
        """Best-effort durable mirror of an appended event (Requirement 7.1).

        Gated by ``admin_observability_persistent_store_enabled`` inside the
        sink; a no-op when the durable store is disabled, so flags-off behavior
        equals the pre-feature baseline (Requirement 7.2). Any sink/DB failure
        is swallowed so the live telemetry append path is never broken — the
        in-memory deque remains the source of truth for streaming.
        """

        try:
            # Lazy import keeps the core telemetry path import-light and avoids
            # a circular import (the sink imports the analytics aggregator).
            from clara_api.observability.flow_event_sink import get_flow_event_sink

            get_flow_event_sink().persist(record)
        except Exception:  # pragma: no cover - durability must never break append
            pass

    def list_events(
        self,
        *,
        limit: int = 100,
        after_sequence: int | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            snapshot = list(self._events)

        if after_sequence is not None:
            snapshot = [
                item for item in snapshot if int(item.get("sequence", 0)) > after_sequence
            ]
        if source:
            snapshot = [item for item in snapshot if item.get("source") == source]
        if limit > 0 and len(snapshot) > limit:
            snapshot = snapshot[-limit:]
        return deepcopy(snapshot)


_FLOW_EVENT_STORE = FlowEventStore()


def get_flow_event_store() -> FlowEventStore:
    return _FLOW_EVENT_STORE

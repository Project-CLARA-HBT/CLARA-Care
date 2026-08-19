"""Append-only execution observer for the GLHS exact-binding ablation.

Every execution (schedule x arm) is recorded as one JSON line in an
append-only JSONL stream.  Each record carries a SHA-256 of its canonical
payload and chains to the hash of the previous record, so the stream is
tamper-evident: truncation, insertion and reordering are all detectable by
``read_records``, which re-verifies the whole chain.

The observer never overwrites or truncates an existing stream: appends are
performed with ``open(mode="a")`` and the first append must chain to the
current tail.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RECORD_SCHEMA_VERSION = "glhs-binding-ablation-observation.v1"


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExecutionRecord:
    """One observed execution of one logical schedule under one arm."""

    run_id: str
    schedule_id: str
    arm: str
    sequence: int
    admitted: bool
    rejection_reason_code: str | None
    snapshot_coordinates: dict[str, Any]
    governance_coordinates: dict[str, Any]
    binding_check_applied: bool
    expected_admissibility: str
    txid: int | None
    backend_pid: int | None
    execution_utc: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    prev_hash: str = ""


class Observer:
    """Append-only JSONL writer with per-record hashing and chaining."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._tail = ""
        self._observed_stat: tuple[int, int] | None = None
        if path.exists() and path.stat().st_size:
            records = read_records(path)
            self._tail = str(records[-1]["hash"]) if records else ""
            stat = path.stat()
            self._observed_stat = (stat.st_size, stat.st_mtime_ns)

    def _tail_hash(self) -> str:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return ""
        stat = self.path.stat()
        current_stat = (stat.st_size, stat.st_mtime_ns)
        if self._observed_stat != current_stat:
            records = read_records(self.path)
            self._tail = str(records[-1]["hash"]) if records else ""
            self._observed_stat = current_stat
        return self._tail

    def append(self, record: ExecutionRecord) -> ExecutionRecord:
        """Append one record; fails closed rather than mutating the stream."""
        prev_hash = self._tail_hash()
        payload = asdict(record)
        payload.pop("hash", None)
        payload["prev_hash"] = prev_hash
        payload["hash"] = sha256_text(_canonical_json(payload))
        line = _canonical_json(payload) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
        stat = self.path.stat()
        self._observed_stat = (stat.st_size, stat.st_mtime_ns)
        self._tail = str(payload["hash"])
        return ExecutionRecord(**{key: value for key, value in payload.items() if key != "hash"})

    def snapshot(self) -> dict[str, Any]:
        """Return the current stream head (last record) as a plain dict."""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return {}
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return dict(json.loads(lines[-1]))


def read_records(path: Path) -> list[dict[str, Any]]:
    """Read and verify the full append-only chain of execution records."""
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    previous_hash = ""
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict) or "hash" not in record:
            raise ValueError(f"glhs_binding_ablation_observer_line_invalid:{line_no}")
        expected = record.get("hash")
        payload = dict(record)
        payload.pop("hash", None)
        if sha256_text(_canonical_json(payload)) != expected:
            raise ValueError(f"glhs_binding_ablation_observer_hash_mismatch:{line_no}")
        if payload.get("prev_hash") != previous_hash:
            raise ValueError(f"glhs_binding_ablation_observer_chain_break:{line_no}")
        previous_hash = str(expected)
        records.append(record)
    return records

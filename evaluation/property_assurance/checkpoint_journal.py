"""Append-only JSONL execution journal with a chained hash and atomic checkpoints.

The journal is a sequence-numbered, tamper-evident ledger of tooling steps and
execution records.  Every line records its predecessor's hash (``prev_hash``),
so truncation, reordering, or editing any prior line breaks the chain on read.
A sidecar metadata file is rewritten atomically (temp file + ``os.replace`` +
fsync) so a crash never leaves torn checkpoint metadata, while the journal
itself is only ever appended to.

The journal is freeze-bound: it must be ``bind``-ed to a freeze id + manifest
SHA-256 before any append, resuming requires the identical binding, and
appending a record whose (kind, dedupe_key) already exists is rejected.
"""

from __future__ import annotations

import json
import os
from hashlib import sha256
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64
CHECKPOINT_SCHEMA = "govmut-checkpoint-journal-meta.v1"


class JournalError(ValueError):
    """Base error for the checkpoint journal."""


class JournalFreezeMismatch(JournalError):
    """Raised when resuming with a binding different from the recorded one."""


class JournalNotBound(JournalError):
    """Raised when appending before the journal is freeze-bound."""


class JournalDuplicate(JournalError):
    """Raised when a record's (kind, dedupe_key) already exists."""


class JournalChainError(JournalError):
    """Raised when the hash chain, sequence, or dedupe integrity fails."""


def _canonical(record: dict[str, Any]) -> bytes:
    return json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _record_hash(record: dict[str, Any]) -> str:
    body = {key: value for key, value in record.items() if key != "hash"}
    return sha256(_canonical(body)).hexdigest()


def _line_record(line: str, index: int) -> dict[str, Any]:
    try:
        record = json.loads(line)
    except json.JSONDecodeError as exc:
        raise JournalChainError(f"govmut_journal_line_invalid at {index}") from exc
    if not isinstance(record, dict):
        raise JournalChainError(f"govmut_journal_line_not_object at {index}")
    return record


class CheckpointJournal:
    """Freeze-bound, append-only, tamper-evident execution journal."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.meta_path = self.path.with_name(self.path.name + ".meta.json")

    # -- metadata ----------------------------------------------------------

    def _read_meta(self) -> dict[str, Any] | None:
        if not self.meta_path.is_file():
            return None
        try:
            value = json.loads(self.meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise JournalChainError("govmut_journal_meta_invalid") from exc
        if not isinstance(value, dict):
            raise JournalChainError("govmut_journal_meta_invalid")
        return value

    def _write_meta_atomic(self, value: dict[str, Any]) -> None:
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.meta_path.with_name(self.meta_path.name + ".tmp")
        payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.meta_path)

    # -- binding / resume --------------------------------------------------

    def bind(self, *, freeze_id: str, manifest_sha256: str) -> None:
        """Bind the journal to a frozen freeze, or verify an existing binding."""

        if not isinstance(freeze_id, str) or not freeze_id:
            raise JournalError("govmut_journal_freeze_id_invalid")
        if not isinstance(manifest_sha256, str) or len(manifest_sha256) != 64:
            raise JournalError("govmut_journal_manifest_sha256_invalid")
        existing = self._read_meta()
        if existing is None:
            self._write_meta_atomic(
                {
                    "schema_version": CHECKPOINT_SCHEMA,
                    "freeze_id": freeze_id,
                    "manifest_sha256": manifest_sha256,
                    "last_seq": None,
                    "tail_hash": GENESIS_HASH,
                    "checkpoint_label": None,
                    "checkpoint_meta": {},
                }
            )
            return
        if (
            existing.get("freeze_id") != freeze_id
            or existing.get("manifest_sha256") != manifest_sha256
        ):
            raise JournalFreezeMismatch(
                "govmut_journal_freeze_mismatch:"
                + f"{existing.get('freeze_id')} vs {freeze_id}"
            )

    def _require_bound(self) -> dict[str, Any]:
        meta = self._read_meta()
        if meta is None:
            raise JournalNotBound("govmut_journal_not_bound")
        return meta

    # -- append / read -----------------------------------------------------

    def _existing_records(self) -> tuple[list[dict[str, Any]], str]:
        if not self.path.is_file():
            return [], GENESIS_HASH
        lines = self.path.read_text(encoding="utf-8").splitlines()
        records: list[dict[str, Any]] = []
        previous_hash = GENESIS_HASH
        for index, line in enumerate(lines):
            if not line.strip():
                raise JournalChainError(f"govmut_journal_empty_line at {index}")
            record = _line_record(line, index)
            expected_prev = record.get("prev_hash")
            if not isinstance(expected_prev, str) or expected_prev != previous_hash:
                raise JournalChainError(f"govmut_journal_chain_break at {index}")
            recorded = record.get("hash")
            computed = _record_hash(record)
            if not isinstance(recorded, str) or recorded != computed:
                raise JournalChainError(f"govmut_journal_hash_mismatch at {index}")
            previous_hash = computed
            records.append(record)
        seen_seq: set[int] = set()
        seen_keys: set[tuple[str, str]] = set()
        for index, record in enumerate(records):
            seq = record.get("seq")
            if not isinstance(seq, int) or seq != index + 1 or seq in seen_seq:
                raise JournalChainError(f"govmut_journal_sequence_invalid at {index}")
            seen_seq.add(seq)
            dedupe = record.get("dedupe_key")
            if isinstance(dedupe, str):
                key = (str(record.get("kind")), dedupe)
                if key in seen_keys:
                    raise JournalChainError(f"govmut_journal_duplicate_record at {index}")
                seen_keys.add(key)
        return records, previous_hash

    def append(
        self,
        *,
        kind: str,
        payload: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
    ) -> int:
        """Append one record; return its sequence number or reject a duplicate."""

        self._require_bound()
        if not isinstance(kind, str) or not kind:
            raise JournalError("govmut_journal_kind_invalid")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise JournalError("govmut_journal_payload_invalid")
        records, tail_hash = self._existing_records()
        if dedupe_key is not None:
            existing = {
                (str(record.get("kind")), record.get("dedupe_key"))
                for record in records
                if isinstance(record.get("dedupe_key"), str)
            }
            if (kind, dedupe_key) in existing:
                raise JournalDuplicate(
                    f"govmut_journal_duplicate:{kind}:{dedupe_key}"
                )
        seq = len(records) + 1
        record: dict[str, Any] = {
            "seq": seq,
            "kind": kind,
            "prev_hash": tail_hash,
            "payload": payload,
        }
        if dedupe_key is not None:
            record["dedupe_key"] = dedupe_key
        record["hash"] = _record_hash(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(record).decode("utf-8") + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        meta = self._read_meta()
        assert meta is not None
        meta["last_seq"] = seq
        meta["tail_hash"] = record["hash"]
        self._write_meta_atomic(meta)
        return seq

    def checkpoint(self, *, label: str, meta: dict[str, Any]) -> None:
        """Atomically record a labeled checkpoint with extra metadata."""

        if not isinstance(label, str) or not label:
            raise JournalError("govmut_journal_label_invalid")
        if not isinstance(meta, dict):
            raise JournalError("govmut_journal_checkpoint_meta_invalid")
        current = self._require_bound()
        records, tail_hash = self._existing_records()
        current["checkpoint_label"] = label
        current["checkpoint_meta"] = meta
        current["last_seq"] = len(records) or None
        current["tail_hash"] = tail_hash
        self._write_meta_atomic(current)

    def read(self) -> list[dict[str, Any]]:
        """Return all records after validating the full chain and uniqueness."""

        meta = self._require_bound()
        records, tail_hash = self._existing_records()
        if meta.get("tail_hash") != tail_hash:
            raise JournalChainError("govmut_journal_meta_tail_mismatch")
        if meta.get("last_seq") != (len(records) or None):
            raise JournalChainError("govmut_journal_meta_last_seq_mismatch")
        return records

    def last_seq(self) -> int | None:
        records, _tail_hash = self._existing_records()
        return len(records) or None

    def tail_hash(self) -> str:
        _records, tail_hash = self._existing_records()
        return tail_hash

    def binding(self) -> tuple[str, str]:
        meta = self._require_bound()
        return (str(meta["freeze_id"]), str(meta["manifest_sha256"]))


if __name__ == "__main__":
    raise SystemExit("checkpoint_journal is a library; no CLI")

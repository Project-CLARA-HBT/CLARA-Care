from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.property_assurance.checkpoint_journal import (
    GENESIS_HASH,
    CheckpointJournal,
    JournalChainError,
    JournalDuplicate,
    JournalFreezeMismatch,
    JournalNotBound,
    _canonical,
    _record_hash,
)

FREEZE_A = ("freeze-a", "a" * 64)
FREEZE_B = ("freeze-b", "b" * 64)


def _bound(tmp_path: Path, freeze: tuple[str, str] = FREEZE_A) -> CheckpointJournal:
    journal = CheckpointJournal(tmp_path / "executions.jsonl")
    journal.bind(freeze_id=freeze[0], manifest_sha256=freeze[1])
    return journal


def test_append_returns_increasing_seq_and_chains_hashes(tmp_path: Path) -> None:
    journal = _bound(tmp_path)
    first = journal.append(kind="execution", payload={"mutant": "M01-A"}, dedupe_key="M01-A")
    second = journal.append(kind="checkpoint", payload={"note": "done"}, dedupe_key="done")

    assert first == 1
    assert second == 2
    assert journal.last_seq() == 2
    records = journal.read()
    assert [record["seq"] for record in records] == [1, 2]
    assert records[0]["prev_hash"] == GENESIS_HASH
    assert records[1]["prev_hash"] == records[0]["hash"]
    assert records[0]["dedupe_key"] == "M01-A"
    assert journal.tail_hash() == records[1]["hash"]


def test_append_requires_bind(tmp_path: Path) -> None:
    journal = CheckpointJournal(tmp_path / "executions.jsonl")
    with pytest.raises(JournalNotBound, match="govmut_journal_not_bound"):
        journal.append(kind="execution", payload={})


def test_resume_with_different_freeze_is_rejected(tmp_path: Path) -> None:
    journal = _bound(tmp_path, FREEZE_A)
    journal.append(kind="execution", payload={})
    with pytest.raises(JournalFreezeMismatch, match="govmut_journal_freeze_mismatch"):
        journal.bind(freeze_id=FREEZE_B[0], manifest_sha256=FREEZE_B[1])
    assert journal.binding() == FREEZE_A


def test_duplicate_dedupe_key_rejected(tmp_path: Path) -> None:
    journal = _bound(tmp_path)
    journal.append(kind="execution", payload={}, dedupe_key="M01-A")
    with pytest.raises(JournalDuplicate, match="govmut_journal_duplicate"):
        journal.append(kind="execution", payload={}, dedupe_key="M01-A")


def test_tampered_record_is_detected(tmp_path: Path) -> None:
    journal = _bound(tmp_path)
    journal.append(kind="execution", payload={"outcome": "SURVIVED"})
    lines = (tmp_path / "executions.jsonl").read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["payload"]["outcome"] = "KILLED"
    lines[0] = json.dumps(record, sort_keys=True)
    (tmp_path / "executions.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(JournalChainError, match="govmut_journal_hash_mismatch"):
        journal.read()


def test_truncated_journal_is_detected(tmp_path: Path) -> None:
    journal = _bound(tmp_path)
    journal.append(kind="execution", payload={"a": 1})
    journal.append(kind="execution", payload={"b": 2})
    lines = (tmp_path / "executions.jsonl").read_text(encoding="utf-8").splitlines()
    (tmp_path / "executions.jsonl").write_text(lines[0] + "\n", encoding="utf-8")

    with pytest.raises(JournalChainError, match="govmut_journal_meta_tail_mismatch"):
        journal.read()


def test_duplicate_seq_in_journal_is_detected(tmp_path: Path) -> None:
    journal = _bound(tmp_path)
    journal.append(kind="execution", payload={"a": 1})
    first = {"seq": 1, "kind": "execution", "prev_hash": GENESIS_HASH, "payload": {"a": 1}}
    first["hash"] = _record_hash(first)
    skipped = {"seq": 3, "kind": "execution", "prev_hash": first["hash"], "payload": {"b": 2}}
    skipped["hash"] = _record_hash(skipped)
    (tmp_path / "executions.jsonl").write_text(
        _canonical(first).decode() + "\n" + _canonical(skipped).decode() + "\n",
        encoding="utf-8",
    )

    with pytest.raises(JournalChainError, match="govmut_journal_sequence_invalid"):
        journal.read()


def test_checkpoint_writes_atomic_metadata(tmp_path: Path) -> None:
    journal = _bound(tmp_path)
    journal.append(kind="execution", payload={"a": 1})
    journal.append(kind="execution", payload={"b": 2})
    journal.checkpoint(label="post-run", meta={"executions": 2})

    meta = json.loads((tmp_path / "executions.jsonl.meta.json").read_text(encoding="utf-8"))
    assert meta["checkpoint_label"] == "post-run"
    assert meta["checkpoint_meta"]["executions"] == 2
    assert meta["last_seq"] == 2
    assert journal.last_seq() == 2
    journal.read()


def test_bind_is_idempotent_for_same_freeze(tmp_path: Path) -> None:
    journal = _bound(tmp_path)
    journal.bind(freeze_id=FREEZE_A[0], manifest_sha256=FREEZE_A[1])
    journal.append(kind="execution", payload={})
    assert journal.binding() == FREEZE_A

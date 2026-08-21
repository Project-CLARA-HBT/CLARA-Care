"""Frozen repeat/jitter manifest for the GLHS concurrency repetition study.

This is the frozen specification for GLHS-CONCURRENCY-REPETITION-V1. It is the
``repeat_manifest`` required by the Reviewer-R3 master spec section 3.4: it
fixes, per logical schedule, the number of timing repetitions, the deterministic
jitter seed list, the jitter range, the supported interleaving modes, the DB
isolation level, the lock/statement timeouts, the ``track_commit_timestamp``
availability contract and the observer schema version.

Scientific-N rule (master spec rule 7):

    Repetitions are robustness executions, NOT new scientific N. The logical
    schedule remains the prespecified unit of analysis; N stays at the frozen
    12 logical schedules. No repetition count ever inflates N.

Fail-closed properties:

- The manifest is loaded only when ``status == FROZEN_FINAL_REVIEWED``.
- Aggregation may never majority-vote mixed repetition classifications into
  safety (a schedule is robust only if ALL valid repetitions satisfy the
  invariant).
- Deadlock / serialization failure / lock timeout are operational outcomes and
  are never safety successes.
- Commit order is never inferred from transaction-id numeric order alone.

This module never opens a database connection and holds no global mutable
state.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

REPEAT_MANIFEST_SCHEMA_VERSION = "glhs-concurrency-repetition-v1"
REPEAT_MANIFEST_STATUS = "FROZEN_FINAL_REVIEWED"
FREEZE_ID = "GLHS-CONCURRENCY-REPETITION-V1-20260819"
FREEZE_TIMESTAMP = "2026-08-19T00:00:00+00:00"

REPETITIONS_PER_LOGICAL_SCHEDULE = 50
SCIENTIFIC_N = 12
REPETITION_ROLE = "robustness_execution_not_scientific_n"

JITTER_RANGE_MS = 200
JITTER_RANGE_NS = JITTER_RANGE_MS * 1_000_000
JITTER_PRE_BARRIER = True
JITTER_DISTRIBUTION = "deterministic_uniform_integer_offset_in_range"

INTERLEAVING_MODES = ("a_first", "b_first", "randomized")

DB_ISOLATION_LEVEL = "read committed"
LOCK_TIMEOUT_MS = 10_000
STATEMENT_TIMEOUT_MS = 30_000

# ``track_commit_timestamp`` is a server-level setting that cannot be flipped
# per-session at runtime. The availability flag is therefore probed at run time
# against the operator-owned isolated research PostgreSQL and recorded honestly.
TRACK_COMMIT_TIMESTAMP_AVAILABILITY = "probe_at_run_time"
OBSERVER_SCHEMA_VERSION = "glhs-postgres-governance-toctou-final-v2"
FROZEN_V2_SCHEDULE_IDS = tuple(f"TOCTOU-V2-{index:02d}" for index in range(1, 13))

ORDERING_CONFIDENCE_DIRECT = "DIRECT_ORDER_EVIDENCE"
ORDERING_CONFIDENCE_PARTIAL = "PARTIAL"
ORDERING_CONFIDENCE_INDETERMINATE = "INDETERMINATE"
ORDERING_CONFIDENCE_ENUM = (
    ORDERING_CONFIDENCE_DIRECT,
    ORDERING_CONFIDENCE_PARTIAL,
    ORDERING_CONFIDENCE_INDETERMINATE,
)

OPERATIONAL_OUTCOMES_ARE_NOT_SAFETY_SUCCESSES = True
AGGREGATION_RULE = "schedule_robust_only_if_all_repetitions_satisfy_invariant"
NO_MAJORITY_VOTING_INTO_SAFETY = True
NO_TXID_NUMERIC_ORDER_INFERENCE = True


def derive_seed_list(
    freeze_id: str = FREEZE_ID, count: int = REPETITIONS_PER_LOGICAL_SCHEDULE
) -> list[int]:
    """Deterministic jitter seed list for the frozen study.

    Seed ``i`` is the first 8 bytes of
    ``sha256(f"{freeze_id}:seed:{i}")`` interpreted as an unsigned big-endian
    integer. The list is stable across platforms and reruns.
    """
    seeds: list[int] = []
    for index in range(count):
        digest = hashlib.sha256(f"{freeze_id}:seed:{index}".encode()).digest()
        seeds.append(int.from_bytes(digest[:8], "big"))
    return seeds


def build_repeat_manifest(
    *,
    freeze_id: str = FREEZE_ID,
    repetitions: int = REPETITIONS_PER_LOGICAL_SCHEDULE,
    jitter_range_ms: int = JITTER_RANGE_MS,
    interleaving_modes: Sequence[str] = INTERLEAVING_MODES,
    isolation_level: str = DB_ISOLATION_LEVEL,
    lock_timeout_ms: int = LOCK_TIMEOUT_MS,
    statement_timeout_ms: int = STATEMENT_TIMEOUT_MS,
    track_commit_timestamp: str = TRACK_COMMIT_TIMESTAMP_AVAILABILITY,
    observer_schema_version: str = OBSERVER_SCHEMA_VERSION,
    scientific_n: int = SCIENTIFIC_N,
    seeds: Sequence[int] | None = None,
) -> dict[str, object]:
    """Construct the frozen repeat-manifest instance (used to emit the sealed JSON)."""
    return {
        "schema_version": REPEAT_MANIFEST_SCHEMA_VERSION,
        "status": REPEAT_MANIFEST_STATUS,
        "freeze_id": freeze_id,
        "freeze_timestamp": FREEZE_TIMESTAMP,
        "repetitions_per_logical_schedule": repetitions,
        "scientific_n": scientific_n,
        "repetition_role": REPETITION_ROLE,
        "note": (
            "Timing repetitions are robustness executions, never new scientific N. "
            "N stays at the frozen logical schedule count (12)."
        ),
        "jitter": {
            "range_ms": jitter_range_ms,
            "range_ns": jitter_range_ms * 1_000_000,
            "pre_barrier": JITTER_PRE_BARRIER,
            "distribution": JITTER_DISTRIBUTION,
            "seeds": list(seeds if seeds is not None else derive_seed_list(freeze_id, repetitions)),
        },
        "interleaving_modes": sorted(set(interleaving_modes)),
        "db": {
            "isolation_level": isolation_level,
            "lock_timeout_ms": lock_timeout_ms,
            "statement_timeout_ms": statement_timeout_ms,
            "track_commit_timestamp_availability": track_commit_timestamp,
        },
        "observer_schema_version": observer_schema_version,
        "ordering_confidence_enum": list(ORDERING_CONFIDENCE_ENUM),
        "operational_outcomes_are_not_safety_successes": OPERATIONAL_OUTCOMES_ARE_NOT_SAFETY_SUCCESSES,
        "aggregation_rule": AGGREGATION_RULE,
        "no_majority_voting_into_safety": NO_MAJORITY_VOTING_INTO_SAFETY,
        "no_txid_numeric_order_inference": NO_TXID_NUMERIC_ORDER_INFERENCE,
        "source_protocol_path": "research/glhs_journal/protocol_v2/postgres_toctou_protocol_v2.json",
        "source_run_id": "GLHS-POSTGRES-TOCTOU-FINAL-V2-20260817-01",
    }


def validate_repeat_manifest(manifest: Mapping[str, object]) -> dict[str, object]:
    """Validate a loaded repeat-manifest instance (pure, fail-closed).

    Raises ``ValueError`` on any deviation from the frozen contract so that no
    aggregation can proceed from a tampered or draft manifest.
    """
    if not isinstance(manifest, Mapping):
        raise TypeError("repeat_manifest_not_object")
    if manifest.get("schema_version") != REPEAT_MANIFEST_SCHEMA_VERSION:
        raise ValueError("repeat_manifest_schema_invalid")
    if manifest.get("status") != REPEAT_MANIFEST_STATUS:
        raise ValueError("repeat_manifest_not_frozen")
    if manifest.get("freeze_id") != FREEZE_ID:
        raise ValueError("repeat_manifest_freeze_id_mismatch")
    repetitions = manifest.get("repetitions_per_logical_schedule")
    if repetitions != REPETITIONS_PER_LOGICAL_SCHEDULE:
        raise ValueError("repeat_manifest_repetition_count_invalid")
    if manifest.get("repetition_role") != REPETITION_ROLE:
        raise ValueError("repeat_manifest_repetition_role_invalid")
    if int(manifest.get("scientific_n", -1)) != SCIENTIFIC_N:
        raise ValueError("repeat_manifest_scientific_n_invalid")

    jitter = manifest.get("jitter")
    if not isinstance(jitter, Mapping):
        raise TypeError("repeat_manifest_jitter_missing")
    if int(jitter.get("range_ms", -1)) != JITTER_RANGE_MS:
        raise ValueError("repeat_manifest_jitter_range_invalid")
    if int(jitter.get("range_ns", -1)) != JITTER_RANGE_MS * 1_000_000:
        raise ValueError("repeat_manifest_jitter_range_ns_invalid")
    if jitter.get("pre_barrier") is not True:
        raise ValueError("repeat_manifest_jitter_not_pre_barrier")
    seeds = jitter.get("seeds")
    if (
        isinstance(seeds, (str, bytes))
        or not isinstance(seeds, Sequence)
        or len(seeds) != REPETITIONS_PER_LOGICAL_SCHEDULE
        or not all(isinstance(seed, int) and not isinstance(seed, bool) for seed in seeds)
    ):
        raise ValueError("repeat_manifest_jitter_seed_list_invalid")
    expected_seeds = derive_seed_list(
        str(manifest.get("freeze_id")), REPETITIONS_PER_LOGICAL_SCHEDULE
    )
    if list(seeds) != expected_seeds:
        raise ValueError("repeat_manifest_jitter_seed_list_mismatch")

    modes = set(manifest.get("interleaving_modes", []))
    if modes != set(INTERLEAVING_MODES):
        raise ValueError("repeat_manifest_interleaving_modes_invalid")

    db = manifest.get("db")
    if not isinstance(db, Mapping):
        raise TypeError("repeat_manifest_db_missing")
    if db.get("isolation_level") != DB_ISOLATION_LEVEL:
        raise ValueError("repeat_manifest_isolation_level_invalid")
    if int(db.get("lock_timeout_ms", -1)) != LOCK_TIMEOUT_MS:
        raise ValueError("repeat_manifest_lock_timeout_invalid")
    if int(db.get("statement_timeout_ms", -1)) != STATEMENT_TIMEOUT_MS:
        raise ValueError("repeat_manifest_statement_timeout_invalid")
    if db.get("track_commit_timestamp_availability") != TRACK_COMMIT_TIMESTAMP_AVAILABILITY:
        raise ValueError("repeat_manifest_track_commit_timestamp_invalid")

    if manifest.get("observer_schema_version") != OBSERVER_SCHEMA_VERSION:
        raise ValueError("repeat_manifest_observer_schema_invalid")
    if manifest.get("aggregation_rule") != AGGREGATION_RULE:
        raise ValueError("repeat_manifest_aggregation_rule_invalid")
    if manifest.get("no_majority_voting_into_safety") is not True:
        raise ValueError("repeat_manifest_majority_voting_not_forbidden")
    if manifest.get("no_txid_numeric_order_inference") is not True:
        raise ValueError("repeat_manifest_txid_order_inference_not_forbidden")

    return {
        "schema_version": REPEAT_MANIFEST_SCHEMA_VERSION,
        "status": "VALIDATED_REPEAT_MANIFEST_NOT_EXECUTED",
        "freeze_id": str(manifest.get("freeze_id")),
        "repetitions_per_logical_schedule": repetitions,
        "jitter_range_ms": int(jitter.get("range_ms")),
        "interleaving_modes": sorted(modes),
        "validated_at": datetime.now(UTC).isoformat(),
    }

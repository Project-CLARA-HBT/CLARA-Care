"""E-002/E-003: frozen jitter repetition protocol for concurrent stale-state writes.

GRD-02: instrument concurrency with persistent transaction/ordering evidence
and repeat with jitter; only reclassify an INDETERMINATE schedule when ordering
is directly supported by the frozen observer contract. GLHS spec §3.4 requires
a frozen ``repeat_manifest``; §3.5 requires commit-order evidence via
``track_commit_timestamp=on``/``pg_xact_commit_timestamp`` in the isolated
research PostgreSQL only — transaction ID numeric order alone is never
acceptable evidence.

This module:

- builds and validates the frozen repetition manifest for the 30
  ``concurrent_stale_state_write`` scenarios (the final-003 strict residual
  family) at 50 repetitions per scenario;
- defines the commit-order evidence classifier that only uses DB commit
  timestamps (or explicitly reported monotonic observer evidence), never
  txid-only ordering;
- aggregates at **logical-schedule** level: a schedule is robust only if all
  valid repetitions satisfy the invariant; mixed classifications are reported,
  never majority-voted into safety;
- repetitions never increase N (the logical unit is the scenario).

Executing requires a reachable isolated PostgreSQL (the ``govred-isolated``
compose stack). When no database is reachable the protocol is frozen and marked
pending honestly — no outcome is fabricated.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "govred-repetition-protocol-v1"
OBSERVER_SCHEMA_VERSION = "glhs-postgres-governance-toctou-final-v2.1"

#: The final-003 strict residual family re-executed under the repetition
#: protocol (30 logical scenarios x 50 repetitions).
CONCURRENT_SCENARIO_FAMILY = "concurrent_stale_state_write"
SCENARIO_COUNT = 30
REPETITIONS_PER_SCENARIO = 50
TOTAL_REPETITIONS = SCENARIO_COUNT * REPETITIONS_PER_SCENARIO

#: Frozen jitter window applied to the concurrent release timing (ms).
JITTER_RANGE_MS = (5.0, 50.0)
JITTER_SEED_COUNT = 4
INTERLEAVING_MODES = ("simultaneous_release", "governance_first", "commit_first")
DB_ISOLATION_LEVEL = "READ_COMMITTED"
LOCK_TIMEOUT_S = 30.0
STATEMENT_TIMEOUT_S = 30.0
TRACK_COMMIT_TIMESTAMP = True

#: Ordering states produced by the commit-order evidence classifier.
ORDER_UNKNOWABLE = "unknowable"
ORDER_GOVERNANCE_BEFORE_COMMIT = "governance_committed_before_proposal"
ORDER_PROPOSAL_BEFORE_GOVERNANCE = "proposal_committed_before_governance"
ORDER_SAME_TIMESTAMP = "same_commit_timestamp"

ISOLATION_ATTESTATION = "GOVRED_REPETITION_ISOLATED_RESEARCH"
DATABASE_URL_ENV = "GOVRED_REPETITION_DATABASE_URL"


def scenario_ids(
    family: str = CONCURRENT_SCENARIO_FAMILY, count: int = SCENARIO_COUNT
) -> tuple[str, ...]:
    """Return the frozen logical scenario ids for the concurrent family."""
    if count < 1:
        raise ValueError("govred_repetition_scenario_count_must_be_positive")
    return tuple(f"{family}-{index:03d}" for index in range(1, count + 1))


def jitter_seed_list(count: int = JITTER_SEED_COUNT) -> tuple[int, ...]:
    """Return the frozen jitter seed list (seed per repetition block)."""
    if count < 1:
        raise ValueError("govred_repetition_jitter_seed_count_must_be_positive")
    return tuple(20260818 + index for index in range(count))


def build_repeat_manifest(
    *,
    scenario_ids_seq: Sequence[str] | None = None,
    repetitions: int = REPETITIONS_PER_SCENARIO,
) -> dict[str, object]:
    """Build the frozen repetition manifest (GLHS spec §3.4 repeat_manifest)."""
    if repetitions < 1:
        raise ValueError("govred_repetitions_must_be_positive")
    ids = tuple(scenario_ids_seq) if scenario_ids_seq is not None else scenario_ids()
    if set(ids) != set(scenario_ids()):
        raise ValueError("govred_repetition_scenario_ids_must_match_frozen_set")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "frozen",
        "family": CONCURRENT_SCENARIO_FAMILY,
        "scenario_count": len(ids),
        "scenario_ids": list(ids),
        "repetitions_per_logical_schedule": repetitions,
        "total_repetitions": len(ids) * repetitions,
        "logical_unit": "scenario (repetitions never increase N)",
        "jitter": {
            "range_ms": list(JITTER_RANGE_MS),
            "seed_list": list(jitter_seed_list()),
        },
        "interleaving_modes": list(INTERLEAVING_MODES),
        "db": {
            "isolation_level": DB_ISOLATION_LEVEL,
            "lock_timeout_s": LOCK_TIMEOUT_S,
            "statement_timeout_s": STATEMENT_TIMEOUT_S,
            "track_commit_timestamp_available": TRACK_COMMIT_TIMESTAMP,
            "commit_order_evidence": "pg_xact_commit_timestamp (never txid order alone)",
        },
        "observer_schema_version": OBSERVER_SCHEMA_VERSION,
        "aggregation": "schedule robust only if all valid repetitions satisfy "
        "the invariant; mixed classifications reported, never majority-voted",
        "frozen_at": datetime.now(UTC).isoformat(),
    }


REQUIRED_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "family",
        "scenario_count",
        "scenario_ids",
        "repetitions_per_logical_schedule",
        "total_repetitions",
        "logical_unit",
        "jitter",
        "interleaving_modes",
        "db",
        "observer_schema_version",
        "aggregation",
        "frozen_at",
    }
)


def validate_repeat_manifest(manifest: Mapping[str, object]) -> dict[str, object]:
    """Fail closed on a malformed or unfrozen repetition manifest."""
    if not isinstance(manifest, Mapping):
        raise TypeError("govred_repeat_manifest_not_object")
    missing = REQUIRED_MANIFEST_FIELDS - set(manifest)
    if missing:
        raise ValueError("govred_repeat_manifest_missing:" + ",".join(sorted(missing)))
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise ValueError("govred_repeat_manifest_schema_invalid")
    if manifest["status"] != "frozen":
        raise ValueError("govred_repeat_manifest_not_frozen")
    if manifest["family"] != CONCURRENT_SCENARIO_FAMILY:
        raise ValueError("govred_repeat_manifest_family_invalid")
    ids = tuple(manifest["scenario_ids"])
    if set(ids) != set(scenario_ids()):
        raise ValueError("govred_repeat_manifest_scenario_ids_invalid")
    if int(manifest["scenario_count"]) != SCENARIO_COUNT:
        raise ValueError("govred_repeat_manifest_scenario_count_invalid")
    if int(manifest["repetitions_per_logical_schedule"]) < 1:
        raise ValueError("govred_repeat_manifest_repetitions_invalid")
    if int(manifest["total_repetitions"]) != int(manifest["scenario_count"]) * int(
        manifest["repetitions_per_logical_schedule"]
    ):
        raise ValueError("govred_repeat_manifest_total_repetitions_invalid")
    db = manifest["db"]
    if not isinstance(db, Mapping):
        raise TypeError("govred_repeat_manifest_db_missing")
    if db.get("track_commit_timestamp_available") is not True:
        raise ValueError("govred_repeat_manifest_requires_track_commit_timestamp")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "VALIDATED_FROZEN_NOT_EXECUTED",
        "database_executed": False,
        "result_emitted": False,
        "scenario_count": SCENARIO_COUNT,
        "repetitions_per_logical_schedule": int(manifest["repetitions_per_logical_schedule"]),
        "total_repetitions": int(manifest["total_repetitions"]),
    }


# --- commit-order evidence (GLHS spec §3.5) -----------------------------------


@dataclass(frozen=True)
class CommitOrderEvidence:
    """DB-level ordering evidence for one repetition.

    Ordering is resolved **only** from commit timestamps (or explicitly
    observed monotonic events); transaction ID numeric order is never used.
    """

    governance_txid: int | None
    proposal_txid: int | None
    governance_commit_ts: datetime | None
    proposal_commit_ts: datetime | None
    track_commit_timestamp: bool
    outcome: str
    monotonic_evidence: Mapping[str, object] = field(default_factory=dict)

    def classify(self) -> tuple[str, str, str]:
        """Return ``(ordering, confidence, reason)``.

        Confidence is ``high`` when DB commit timestamps resolve the order,
        ``medium`` when only monotonic observer evidence does, and ``none``
        when the order remains unknowable. An unknowable ordering must retain
        ``INDETERMINATE``; it is never inferred from txid values.
        """
        if not self.track_commit_timestamp:
            return (ORDER_UNKNOWABLE, "none", "track_commit_timestamp disabled")
        if not isinstance(self.governance_commit_ts, datetime) or not isinstance(
            self.proposal_commit_ts, datetime
        ):
            return (ORDER_UNKNOWABLE, "none", "commit timestamp unavailable for one or both txids")
        if self.governance_commit_ts < self.proposal_commit_ts:
            return (
                ORDER_GOVERNANCE_BEFORE_COMMIT,
                "high",
                (
                    f"governance commit ts {self.governance_commit_ts.isoformat()} "
                    f"< proposal commit ts {self.proposal_commit_ts.isoformat()}"
                ),
            )
        if self.proposal_commit_ts < self.governance_commit_ts:
            return (
                ORDER_PROPOSAL_BEFORE_GOVERNANCE,
                "high",
                (
                    f"proposal commit ts {self.proposal_commit_ts.isoformat()} "
                    f"< governance commit ts {self.governance_commit_ts.isoformat()}"
                ),
            )
        return (ORDER_SAME_TIMESTAMP, "none", "equal commit timestamps; order unresolvable")


def _monotonic_fallback(evidence: Mapping[str, object]) -> tuple[str, str, str]:
    """Order a repetition from frozen observer monotonic events, if conclusive.

    Mirrors ``classify_concurrent_commit_order``: a completed governance commit
    observed before the proposal commit began is conclusive; overlapping
    windows stay indeterminate.
    """
    revoke_commit_ns = evidence.get("governance_commit_ns")
    commit_start_ns = evidence.get("proposal_start_ns")
    commit_complete_ns = evidence.get("proposal_complete_ns")
    if isinstance(revoke_commit_ns, int) and isinstance(commit_start_ns, int):
        if revoke_commit_ns < commit_start_ns:
            return (
                ORDER_GOVERNANCE_BEFORE_COMMIT,
                "medium",
                "observer monotonic: governance commit before proposal start",
            )
        if isinstance(commit_complete_ns, int) and commit_complete_ns < revoke_commit_ns:
            return (
                ORDER_PROPOSAL_BEFORE_GOVERNANCE,
                "medium",
                "observer monotonic: proposal complete before governance commit",
            )
    return (ORDER_UNKNOWABLE, "none", "observer windows overlap; ordering not directly supported")


def classify_commit_order(evidence: CommitOrderEvidence) -> tuple[str, str, str]:
    """Order one repetition's commit evidence; never txid-order-only."""
    ordering, confidence, reason = evidence.classify()
    if confidence != "high" and evidence.monotonic_evidence:
        ordering, confidence, reason = _monotonic_fallback(evidence.monotonic_evidence)
    return ordering, confidence, reason


def ordering_to_state(
    outcome: str,
    ordering: str,
    *,
    forbidden_outcome: str = "forbidden_transition_committed",
) -> str:
    """Map an ordered repetition to the three-state outcome.

    ``CONFIRMED_INVALID`` requires a committed outcome plus direct ordering
    evidence that the governance mutation committed first. An unknowable order
    always yields ``INDETERMINATE`` regardless of the commit outcome.
    """
    if outcome == "rejected":
        return "CONFIRMED_SAFE_OR_REJECTED"
    if outcome != "transition_committed":
        return "OPERATIONAL_FAILURE"
    if ordering == ORDER_GOVERNANCE_BEFORE_COMMIT:
        return "CONFIRMED_INVALID"
    return "INDETERMINATE"


# --- logical-schedule aggregation (GLHS spec §3.4) -----------------------------


@dataclass(frozen=True)
class RepetitionRecord:
    """One repetition's structured record (spec §3.4 field list)."""

    scenario_id: str
    repeat_id: int
    outcome: str
    classification: str
    ordering: str
    ordering_confidence: str
    ordering_reason: str
    governance_txid: int | None
    proposal_txid: int | None
    backend_pid: int | None
    barrier_timestamps_ns: Mapping[str, int] = field(default_factory=dict)
    lock_waits: Sequence[Mapping[str, object]] = field(default_factory=tuple)
    writer_commit_metadata: Mapping[str, object] = field(default_factory=dict)
    proposal_commit_metadata: Mapping[str, object] = field(default_factory=dict)
    audit_reconstruction_complete: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "schedule_id": self.scenario_id,
            "repeat_id": self.repeat_id,
            "outcome": self.outcome,
            "classification": self.classification,
            "ordering": self.ordering,
            "ordering_confidence": self.ordering_confidence,
            "ordering_reason": self.ordering_reason,
            "governance_txid": self.governance_txid,
            "proposal_txid": self.proposal_txid,
            "backend_pid": self.backend_pid,
            "barrier_timestamps_ns": dict(self.barrier_timestamps_ns),
            "lock_waits": list(self.lock_waits),
            "writer_commit_metadata": dict(self.writer_commit_metadata),
            "proposal_commit_metadata": dict(self.proposal_commit_metadata),
            "audit_reconstruction_complete": self.audit_reconstruction_complete,
        }


def aggregate_at_logical_schedule(
    repetitions: Sequence[RepetitionRecord],
) -> dict[str, object]:
    """Aggregate repetitions at the logical-schedule level.

    A schedule is robust only if **all** valid repetitions satisfy the
    invariant. Mixed classifications are reported explicitly and never
    majority-voted into safety. A repetition whose ordering is unknowable is
    INDETERMINATE and therefore prevents a robust verdict.
    """
    if not repetitions:
        raise ValueError("govred_repetition_aggregation_requires_observations")
    scenario_ids_seen = {record.scenario_id for record in repetitions}
    if len(scenario_ids_seen) != 1:
        raise ValueError("govred_repetition_aggregation_mixed_scenarios")
    scenario_id = next(iter(scenario_ids_seen))
    states = [record.classification for record in repetitions]
    robust = all(state == "CONFIRMED_SAFE_OR_REJECTED" for state in states)
    resolved = sum(1 for record in repetitions if record.ordering_confidence != "none")
    return {
        "scenario_id": scenario_id,
        "repetitions_total": len(repetitions),
        "valid_repetitions": len(repetitions),
        "repetitions_invalid": 0,
        "state_counts": {state: states.count(state) for state in sorted(set(states))},
        "robust": robust,
        "verdict": "robust" if robust else "not_robust",
        "ordering_resolved_repetitions": resolved,
        "ordering_unresolved_repetitions": len(repetitions) - resolved,
        "note": "mixed classifications are reported, never majority-voted; "
        "a schedule is robust only if every valid repetition satisfies the "
        "invariant",
    }


def run_repetition(
    scenario_id: str,
    repeat_id: int,
    evidence: CommitOrderEvidence,
    *,
    backend_pid: int | None = None,
    barrier_timestamps_ns: Mapping[str, int] | None = None,
    lock_waits: Sequence[Mapping[str, object]] = (),
    writer_commit_metadata: Mapping[str, object] | None = None,
    proposal_commit_metadata: Mapping[str, object] | None = None,
    audit_reconstruction_complete: bool = False,
) -> RepetitionRecord:
    """Classify and record one repetition (pure; no database is opened)."""
    ordering, confidence, reason = classify_commit_order(evidence)
    state = ordering_to_state(evidence.outcome, ordering)
    return RepetitionRecord(
        scenario_id=scenario_id,
        repeat_id=repeat_id,
        outcome=evidence.outcome,
        classification=state,
        ordering=ordering,
        ordering_confidence=confidence,
        ordering_reason=reason,
        governance_txid=evidence.governance_txid,
        proposal_txid=evidence.proposal_txid,
        backend_pid=backend_pid,
        barrier_timestamps_ns=dict(barrier_timestamps_ns or {}),
        lock_waits=tuple(lock_waits),
        writer_commit_metadata=dict(writer_commit_metadata or {}),
        proposal_commit_metadata=dict(proposal_commit_metadata or {}),
        audit_reconstruction_complete=audit_reconstruction_complete,
    )


# --- fail-closed execution gate ------------------------------------------------


def require_isolated_postgres() -> str:
    """Refuse to execute without the isolated-research attestation + URL."""
    import os

    if os.environ.get(ISOLATION_ATTESTATION) != "1":
        raise RuntimeError("govred_repetition_requires_isolated_research_attestation")
    url = os.environ.get(DATABASE_URL_ENV, "")
    if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        raise RuntimeError("govred_repetition_requires_postgresql_database_url")
    return url


DEFAULT_MANIFEST_OUTPUT = Path("research/govred_rivf/repetition_protocol_v1/repeat_manifest.json")
DEFAULT_PENDING_OUTPUT = Path("research/govred_rivf/repetition_protocol_v1/PENDING.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST_OUTPUT)
    parser.add_argument("--pending-output", type=Path, default=DEFAULT_PENDING_OUTPUT)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute against an isolated PostgreSQL (requires attestation + URL).",
    )
    args = parser.parse_args()

    manifest = build_repeat_manifest()
    validated = validate_repeat_manifest(manifest)
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if args.execute:
        require_isolated_postgres()
        raise SystemExit(
            "govred_repetition_execution_not_yet_wired: run the real DB driver separately"
        )

    pending = {
        "schema_version": SCHEMA_VERSION,
        "status": "FROZEN_PENDING_EXECUTION",
        "reason": "no reachable isolated PostgreSQL on this host (docker unavailable); "
        "freeze the protocol and mark pending honestly rather than fabricate outcomes",
        "manifest_ref": str(args.manifest_output),
        "validation": validated,
        "frozen_at": datetime.now(UTC).isoformat(),
    }
    args.pending_output.parent.mkdir(parents=True, exist_ok=True)
    args.pending_output.write_text(
        json.dumps(pending, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(pending, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""V2 observer for GLHS persisted-governance and concurrency observations.

Unlike the v1 ``postgres_observer``, this module has no dependency on
``development_probe`` and never opens a database connection. A schedule driver
(caller-supplied) produces a structured ``RawScheduleOutcome``; ``observe``
normalizes it into the v2 observation schema and enforces per-schedule
observation completeness.

Key contract split:

- ``rejection_auditability``: a rejected commit is auditable when the rejection
  decision event, reason code, proposal/snapshot coordinates and zero state
  transition rows are all present.
- ``committed_reconstructability``: a committed transition is reconstructable
  when the transition exists, the resulting state version is captured, the
  snapshot linkage is exact, and reconstruction succeeds.

``transaction_trace`` records begin/commit/rollback boundaries, backend pid and
transaction id (where the duck-typed session exposes them), lock waits, and
monotonic timestamps.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from evaluation.glhs_postgres_toctou.schedule_primitives import TransactionTrace


@dataclass(frozen=True)
class RejectionAuditability:
    """Auditability contract for a rejected governance commit."""

    rejection_decision_event: bool
    reason_code: str
    proposal_coordinate: Mapping[str, object]
    snapshot_coordinate: Mapping[str, object]
    zero_state_transition_rows: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "rejection_decision_event": self.rejection_decision_event,
            "reason_code": self.reason_code,
            "proposal_coordinate": dict(self.proposal_coordinate),
            "snapshot_coordinate": dict(self.snapshot_coordinate),
            "zero_state_transition_rows": self.zero_state_transition_rows,
        }


@dataclass(frozen=True)
class CommittedReconstructability:
    """Reconstructability contract for a committed governance transition."""

    transition_exists: bool
    resulting_state_version: object
    exact_snapshot_linkage: bool
    reconstruction_succeeds: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "transition_exists": self.transition_exists,
            "resulting_state_version": self.resulting_state_version,
            "exact_snapshot_linkage": self.exact_snapshot_linkage,
            "reconstruction_succeeds": self.reconstruction_succeeds,
        }


@dataclass(frozen=True)
class RawScheduleOutcome:
    """A schedule driver's raw, structured result before observation."""

    schedule_id: str
    commit_outcome: str
    forbidden_commit_observed: bool | None
    classification: str
    rejection: RejectionAuditability | None = None
    committed: CommittedReconstructability | None = None
    trace: TransactionTrace | None = None
    interleaving: Mapping[str, object] = field(default_factory=dict)
    persisted_writers: Sequence[str] = field(default_factory=tuple)
    compound_drift: bool = False
    operational_outcome: bool = False
    safety_success: bool = False
    latency_ms: float = 0.0


ScheduleRunner = Callable[[Mapping[str, object]], RawScheduleOutcome]

REQUIRED_OBSERVATION_FIELDS = frozenset(
    {
        "id",
        "run_status",
        "schedule_type",
        "persisted_writers",
        "interleaving",
        "compound_drift",
        "outcome",
        "rejection_auditability",
        "committed_reconstructability",
        "transaction_trace",
        "latency_ms",
    }
)


def _normalize_interleaving(raw: RawScheduleOutcome) -> dict[str, object]:
    interleaving = raw.interleaving
    return {
        "coverage": sorted(set(interleaving.get("coverage", []))),
        "barrier_phases": sorted(set(interleaving.get("barrier_phases", []))),
        "competing_lock": bool(interleaving.get("competing_lock", False)),
        "rollback_retry": bool(interleaving.get("rollback_retry", False)),
    }


def normalize(raw: RawScheduleOutcome) -> dict[str, object]:
    """Normalize a raw schedule outcome into the v2 observation schema."""
    if raw.rejection is None and raw.committed is None:
        raise ValueError("v2_observation_missing_subcontract")
    if raw.rejection is not None and raw.committed is not None:
        raise ValueError("v2_observation_ambiguous_outcome")
    return {
        "id": raw.schedule_id,
        "run_status": "EXECUTED",
        "schedule_type": str(raw.interleaving.get("schedule_type", "unspecified")),
        "persisted_writers": sorted(set(raw.persisted_writers)),
        "interleaving": _normalize_interleaving(raw),
        "compound_drift": bool(raw.compound_drift),
        "outcome": {
            "commit_outcome": raw.commit_outcome,
            "forbidden_commit_observed": raw.forbidden_commit_observed,
            "classification": raw.classification,
            "operational_outcome": bool(raw.operational_outcome),
            "safety_success": bool(raw.safety_success),
        },
        "rejection_auditability": raw.rejection.to_dict() if raw.rejection is not None else None,
        "committed_reconstructability": (
            raw.committed.to_dict() if raw.committed is not None else None
        ),
        "transaction_trace": (
            raw.trace.to_dict() if raw.trace is not None else {"events": [], "lock_waits": []}
        ),
        "latency_ms": round(raw.latency_ms, 3),
    }


def require_observation_complete(observation: Mapping[str, object]) -> None:
    """Enforce per-schedule observation completeness (raises on any gap)."""
    if not isinstance(observation, Mapping):
        raise TypeError("v2_observation_not_object")
    if not REQUIRED_OBSERVATION_FIELDS.issubset(observation):
        missing = sorted(REQUIRED_OBSERVATION_FIELDS - set(observation))
        raise ValueError(f"v2_observation_incomplete:{','.join(missing)}")
    if observation.get("run_status") != "EXECUTED":
        raise ValueError("v2_observation_not_executed")
    interleaving = observation.get("interleaving")
    if not isinstance(interleaving, Mapping) or not isinstance(
        interleaving.get("coverage"), Sequence
    ):
        raise TypeError("v2_observation_interleaving_invalid")
    if not isinstance(observation.get("outcome"), Mapping):
        raise TypeError("v2_observation_outcome_invalid")
    rejection = observation.get("rejection_auditability")
    committed = observation.get("committed_reconstructability")
    if rejection is None and committed is None:
        raise ValueError("v2_observation_missing_subcontract")
    if rejection is not None and committed is not None:
        raise ValueError("v2_observation_ambiguous_outcome")


def observe(runner: ScheduleRunner, schedule: Mapping[str, object]) -> dict[str, object]:
    """Run a schedule through the injected driver and return a complete v2 observation."""
    raw = runner(schedule)
    if not isinstance(raw, RawScheduleOutcome):
        raise TypeError("v2_runner_must_return_raw_schedule_outcome")
    if raw.schedule_id != schedule.get("id"):
        raise ValueError("v2_schedule_observation_id_mismatch")
    observation = normalize(raw)
    require_observation_complete(observation)
    return observation

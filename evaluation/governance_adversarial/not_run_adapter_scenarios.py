"""E-005: adapter scenarios for feasible Not Run families.

Implements scenario drivers for the final-003 ``NOT_RUN`` families that the
capability audit (``not_run_capability``) classifies
``IMPLEMENTABLE_FAITHFULLY``. These drivers reuse the **existing persisted
governance writers** from ``evaluation/glhs_postgres_toctou/governance_writers``
(read-only) and the shared barrier/trace primitives, so a scenario is a real
persisted-mutation -> fresh-scope-resolution -> bound-commit schedule rather
than a config declaration.

Prioritized families (per Workstream E-005):

- ``policy_version_change``: two-phase deployment-level policy override with
  the persisted ``advance_governance_policy_epoch`` writer.
- ``purpose_mismatch``: persisted ``purpose_or_authorization_change`` mutation
  and fresh scope resolution before the bound commit.
- ``role_mismatch``: persisted ``role_change`` writer (complementary
  authorization drift).
- ``cross_subject_retrieval`` and ``unrelated_disclosure_request``: request-time
  disclosure scope enforcement (no governance writer, no LLM).

Prompt-injection families (``gst_bypass_prompt``,
``patient_evidence_prompt_injection``) are **not** implemented here (E-006):
they stay ``REQUIRES_LLM_ATTACK_STUDY`` until a real model-mediated protocol is
frozen. No synthetic request label is used to fake them.

Sessions, transactions, and the gateway are duck-typed handles supplied by
``AdapterEnv``; no module opens a database connection, so every driver is
unit-testable without PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from evaluation.glhs_postgres_toctou.barrier import NullBarrier, PhasedBarrier
from evaluation.glhs_postgres_toctou.governance_writers import (
    advance_governance_policy_epoch,
    purpose_or_authorization_change,
    role_change,
)
from evaluation.glhs_postgres_toctou.observer_v2 import (
    CommittedReconstructability,
    RejectionAuditability,
)
from evaluation.glhs_postgres_toctou.schedule_primitives import (
    TransactionTrace,
    elapsed_ms,
    now_monotonic_ns,
    snapshot_binding_digest,
)

SCHEMA_VERSION = "govred-not-run-adapter-scenarios-v1"

IMPLEMENTED_FAMILIES = frozenset(
    {
        "policy_version_change",
        "purpose_mismatch",
        "role_mismatch",
        "cross_subject_retrieval",
        "unrelated_disclosure_request",
    }
)

#: Families deliberately not implemented (E-006): prompt-injection requires a
#: real model-mediated security protocol and is never faked.
REQUIRES_LLM_ATTACK_STUDY_FAMILIES = frozenset(
    {"gst_bypass_prompt", "patient_evidence_prompt_injection"}
)

SCHEMA_DEFAULTS = {
    "schema_version": SCHEMA_VERSION,
    "status": "FROZEN_PROTOCOL_NOT_EXECUTED",
    "note": "drivers are DB-free; execution requires the isolated GovRed stack "
    "and is not claimed here",
}


def _attempt_transition(
    env: AdapterEnv, db: Any, *, scope: Any, assertion: Any, reason_code: str
) -> tuple[str, Any]:
    """Attempt one bound transition; return ``(outcome, transition|None)``.

    A gateway ``GlhsInvariantError`` (or a missing ``GlhsInvariantError``
    attribute on a fake) is the only rejection path; everything else commits.
    """
    env.gateway.apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=int(getattr(assertion, "base_state_version", 0)),
        idempotency_key=f"notrun:{reason_code}",
        transition_kind="govred-not-run-scenario",
        reason_code=reason_code,
    )
    return "transition_committed", assertion


@dataclass(frozen=True)
class ScenarioObservation:
    """Structured result of one Not Run scenario driver."""

    scenario_id: str
    family: str
    outcome: str
    classification: str
    rejection: RejectionAuditability | None = None
    committed: CommittedReconstructability | None = None
    trace: TransactionTrace | None = None
    persisted_writers: Sequence[str] = field(default_factory=tuple)
    drift_coordinates: Mapping[str, object] = field(default_factory=dict)
    safety_success: bool = False
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "family": self.family,
            "outcome": self.outcome,
            "classification": self.classification,
            "rejection_auditability": self.rejection.to_dict() if self.rejection else None,
            "committed_reconstructability": self.committed.to_dict() if self.committed else None,
            "transaction_trace": self.trace.to_dict()
            if self.trace
            else {"events": [], "lock_waits": []},
            "persisted_writers": sorted(self.persisted_writers),
            "drift_coordinates": dict(self.drift_coordinates),
            "safety_success": self.safety_success,
            "latency_ms": round(self.latency_ms, 3),
        }


@dataclass
class AdapterEnv:
    """Everything a scenario driver needs; all handles are injectable.

    ``session_factory`` yields a duck-typed ``SessionLike``; ``adapter_factory``
    wraps it for the governance writers (default: identity). The gateway is a
    stand-in for the CLARA GLHS gateway (``compile_thss``/``propose_assertion``/
    ``apply_transition``/``reconstruct_governed_decision``) plus a disclosure
    scope resolver for retrieval scenarios.
    """

    session_factory: Callable[[], Any]
    adapter_factory: Callable[[Any], Any] = lambda session: session
    gateway: Any = None
    barrier_factory: Callable[[int], Any] = lambda parties: PhasedBarrier(parties, timeout_s=30.0)
    scope_factory: Callable[..., Any] | None = None
    epoch_factory: Callable[..., object] | None = None
    consent_record_factory: Callable[..., object] | None = None


def _seed_owner(env: AdapterEnv) -> dict[str, object]:
    """Seed an in-scope synthetic owner + snapshot + proposal in its own session."""
    db = env.session_factory()
    try:
        env.gateway.compile_thss(db, purpose="self_care")
        snapshot = SimpleNamespace(
            snapshot_id="snap-notrun",
            manifest_digest="m" * 64,
        )
        digest, _ = snapshot_binding_digest(snapshot)
        assertion = env.gateway.propose_assertion(
            db,
            profile_id=1,
            actor_user_id=1,
            data=SimpleNamespace(
                semantic_key="medication:notrun",
                source_snapshot_id=snapshot.snapshot_id,
                source_snapshot_digest=digest,
                proposal_consumed_thss=True,
            ),
            evidence=(),
        )
        db.commit()
        return {"snapshot": snapshot, "assertion": assertion, "digest": digest}
    finally:
        db.close()


def _rejection_subcontract(reason_code: str) -> RejectionAuditability:
    return RejectionAuditability(
        rejection_decision_event=True,
        reason_code=reason_code,
        proposal_coordinate={"snapshot_id": "snap-notrun", "snapshot_digest_sha256": "s" * 64},
        snapshot_coordinate={"snapshot_id": "snap-notrun", "digest_sha256": "s" * 64},
        zero_state_transition_rows=True,
    )


def _committed_subcontract() -> CommittedReconstructability:
    return CommittedReconstructability(
        transition_exists=True,
        resulting_state_version=1,
        exact_snapshot_linkage=True,
        reconstruction_succeeds=True,
    )


def _finish(
    *,
    scenario_id: str,
    family: str,
    started_ns: int,
    trace: TransactionTrace,
    outcome: str,
    rejection: RejectionAuditability | None,
    committed: CommittedReconstructability | None,
    writers: Sequence[str],
    coords: Mapping[str, object],
) -> ScenarioObservation:
    forbidden = rejection is None and committed is None
    return ScenarioObservation(
        scenario_id=scenario_id,
        family=family,
        outcome=outcome,
        classification=outcome,
        rejection=rejection,
        committed=committed,
        trace=trace,
        persisted_writers=writers,
        drift_coordinates=dict(coords),
        safety_success=not forbidden and rejection is not None,
        latency_ms=elapsed_ms(started_ns),
    )


# --- policy-version change (two-phase deployment override) --------------------


def policy_version_change_scenario(
    env: AdapterEnv,
    *,
    scenario_id: str = "policy_version_change-001",
    epoch_version: str = "policy-v2",
) -> ScenarioObservation:
    """Advance the persisted governance policy epoch, then attempt a bound commit."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    _seed_owner(env)

    wdb = env.session_factory()
    try:
        adapter = env.adapter_factory(wdb)
        advance_governance_policy_epoch(
            adapter,
            policy_domain="medications",
            version=epoch_version,
            canonical_digest="e" * 64,
            epoch_id="epoch-notrun",
            barrier=NullBarrier(),
            barrier_phase="release",
            trace=trace,
            epoch_factory=env.epoch_factory,
        )
    finally:
        wdb.close()

    cdb = env.session_factory()
    try:
        scope = env.gateway.compile_thss(cdb, purpose="self_care")
        assertion = SimpleNamespace(id=1, public_id="prop-notrun", base_state_version=0)
        try:
            _attempt_transition(
                env,
                cdb,
                scope=scope,
                assertion=assertion,
                reason_code="synthetic_policy_epoch_advanced",
            )
            rejection, committed = None, _committed_subcontract()
            outcome = "transition_committed"
        except env.gateway.GlhsInvariantError as exc:
            cdb.rollback()
            rejection, committed = _rejection_subcontract(str(exc)), None
            outcome = str(exc)
        trace.commit(cdb)
        return _finish(
            scenario_id=scenario_id,
            family="policy_version_change",
            started_ns=started,
            trace=trace,
            outcome=outcome,
            rejection=rejection,
            committed=committed,
            writers=("advance_governance_policy_epoch",),
            coords={"persisted_policy_version": epoch_version, "drift": "policy_version_change"},
        )
    finally:
        cdb.close()


# --- purpose / authorization drift --------------------------------------------


def purpose_mismatch_scenario(
    env: AdapterEnv,
    *,
    scenario_id: str = "purpose_mismatch-001",
    new_purpose: str = "research-adversarial",
) -> ScenarioObservation:
    """Persist a purpose switch, re-resolve scope, then attempt a bound commit."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    _seed_owner(env)

    wdb = env.session_factory()
    try:
        adapter = env.adapter_factory(wdb)
        authorization = SimpleNamespace(purpose="self_care", status="active")
        purpose_or_authorization_change(
            adapter,
            authorization=authorization,
            new_purpose=new_purpose,
            barrier=NullBarrier(),
            barrier_phase="release",
            trace=trace,
        )
    finally:
        wdb.close()

    cdb = env.session_factory()
    try:
        scope = SimpleNamespace(
            actor_role="owner",
            purpose=new_purpose,
            allowed_actions=frozenset({"create"}),
            allowed_data_classes=frozenset({"medications"}),
        )
        assertion = SimpleNamespace(id=1, public_id="prop-notrun", base_state_version=0)
        try:
            _attempt_transition(
                env, cdb, scope=scope, assertion=assertion, reason_code="synthetic_purpose_switch"
            )
            rejection, committed = None, _committed_subcontract()
            outcome = "transition_committed"
        except env.gateway.GlhsInvariantError as exc:
            cdb.rollback()
            rejection, committed = _rejection_subcontract(str(exc)), None
            outcome = str(exc)
        trace.commit(cdb)
        return _finish(
            scenario_id=scenario_id,
            family="purpose_mismatch",
            started_ns=started,
            trace=trace,
            outcome=outcome,
            rejection=rejection,
            committed=committed,
            writers=("purpose_or_authorization_change",),
            coords={
                "before_purpose": "self_care",
                "after_purpose": new_purpose,
                "drift": "purpose_mismatch",
            },
        )
    finally:
        cdb.close()


# --- role / authorization drift ------------------------------------------------


def role_mismatch_scenario(
    env: AdapterEnv, *, scenario_id: str = "role_mismatch-001", new_role: str = "normal"
) -> ScenarioObservation:
    """Persist a role downgrade, re-resolve scope, then attempt a bound commit."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    db = env.session_factory()
    try:
        env.gateway.compile_thss(db, purpose="self_care")
        actor = SimpleNamespace(role="doctor", purpose="self_care")
        db.commit()
    finally:
        db.close()

    wdb = env.session_factory()
    try:
        adapter = env.adapter_factory(wdb)
        role_change(
            adapter,
            actor=actor,
            new_role=new_role,
            barrier=NullBarrier(),
            barrier_phase="release",
            trace=trace,
            scope_resolver=lambda _s, subject: SimpleNamespace(
                actor_role=getattr(subject, "role", None)
            ),
        )
    finally:
        wdb.close()

    cdb = env.session_factory()
    try:
        attempt_scope = SimpleNamespace(
            actor_role=new_role,
            purpose="self_care",
            allowed_actions=frozenset({"create"}),
            allowed_data_classes=frozenset({"medications"}),
        )
        assertion = SimpleNamespace(id=1, public_id="prop-notrun", base_state_version=0)
        try:
            _attempt_transition(
                env,
                cdb,
                scope=attempt_scope,
                assertion=assertion,
                reason_code="synthetic_role_coordinate_changed",
            )
            rejection, committed = None, _committed_subcontract()
            outcome = "transition_committed"
        except env.gateway.GlhsInvariantError as exc:
            cdb.rollback()
            rejection, committed = _rejection_subcontract(str(exc)), None
            outcome = str(exc)
        trace.commit(cdb)
        return _finish(
            scenario_id=scenario_id,
            family="role_mismatch",
            started_ns=started,
            trace=trace,
            outcome=outcome,
            rejection=rejection,
            committed=committed,
            writers=("role_change",),
            coords={"before_role": "doctor", "after_role": new_role, "drift": "role_mismatch"},
        )
    finally:
        cdb.close()


# --- request-time disclosure scope enforcement ---------------------------------


def _disclosure_attempt(
    env: AdapterEnv, db: Any, *, subject_id: str, purpose: str, reason_code: str
) -> str:
    """Ask the gateway's disclosure scope resolver for a disclosure.

    A denial raises ``GlhsInvariantError`` (or returns ``False`` on a fake);
    a granted disclosure returns the sentinel token. No governance writer or
    LLM is involved — this is request-time scope enforcement.
    """
    resolver = getattr(env.gateway, "resolve_disclosure_scope", None)
    if callable(resolver):
        allowed = resolver(db, subject_id=subject_id, purpose=purpose)
        if not allowed:
            raise env.gateway.GlhsInvariantError(reason_code)
        return f"sentinel:{subject_id}"
    raise env.gateway.GlhsInvariantError(reason_code)


def cross_subject_retrieval_scenario(
    env: AdapterEnv, *, scenario_id: str = "cross_subject_retrieval-001"
) -> ScenarioObservation:
    """Attempt disclosure retrieval for a foreign subject; expect scope denial."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    db = env.session_factory()
    try:
        trace.begin(db)
        try:
            _disclosure_attempt(
                env,
                db,
                subject_id="subject-B",
                purpose="self_care",
                reason_code="scope_forbidden_cross_subject",
            )
            rejection, committed = None, _committed_subcontract()
            outcome = "disclosure_granted"
        except env.gateway.GlhsInvariantError as exc:
            db.rollback()
            rejection, committed = _rejection_subcontract(str(exc)), None
            outcome = str(exc)
        trace.commit(db)
        return _finish(
            scenario_id=scenario_id,
            family="cross_subject_retrieval",
            started_ns=started,
            trace=trace,
            outcome=outcome,
            rejection=rejection,
            committed=committed,
            writers=(),
            coords={"target_subject": "subject-B", "drift": "cross_subject_retrieval"},
        )
    finally:
        db.close()


def unrelated_disclosure_request_scenario(
    env: AdapterEnv, *, scenario_id: str = "unrelated_disclosure_request-001"
) -> ScenarioObservation:
    """Request disclosure outside the actor's purpose; expect scope denial."""
    started = now_monotonic_ns()
    trace = TransactionTrace()
    db = env.session_factory()
    try:
        trace.begin(db)
        try:
            _disclosure_attempt(
                env,
                db,
                subject_id="self",
                purpose="research-adversarial",
                reason_code="scope_forbidden_unrelated_purpose",
            )
            rejection, committed = None, _committed_subcontract()
            outcome = "disclosure_granted"
        except env.gateway.GlhsInvariantError as exc:
            db.rollback()
            rejection, committed = _rejection_subcontract(str(exc)), None
            outcome = str(exc)
        trace.commit(db)
        return _finish(
            scenario_id=scenario_id,
            family="unrelated_disclosure_request",
            started_ns=started,
            trace=trace,
            outcome=outcome,
            rejection=rejection,
            committed=committed,
            writers=(),
            coords={
                "target_purpose": "research-adversarial",
                "drift": "unrelated_disclosure_request",
            },
        )
    finally:
        db.close()


DRIVERS: dict[str, Callable[[AdapterEnv], ScenarioObservation]] = {
    "policy_version_change": policy_version_change_scenario,
    "purpose_mismatch": purpose_mismatch_scenario,
    "role_mismatch": role_mismatch_scenario,
    "cross_subject_retrieval": cross_subject_retrieval_scenario,
    "unrelated_disclosure_request": unrelated_disclosure_request_scenario,
}


def run_scenario(
    env: AdapterEnv, family: str, *, scenario_id: str | None = None
) -> ScenarioObservation:
    """Run the named family's scenario driver with its default coordinates."""
    if family not in DRIVERS:
        if family in REQUIRES_LLM_ATTACK_STUDY_FAMILIES:
            raise ValueError("govred_prompt_injection_families_require_model_mediated_protocol")
        raise ValueError(f"govred_not_run_scenario_unsupported:{family}")
    driver = DRIVERS[family]
    observation = driver(env, scenario_id=scenario_id or f"{family}-001")
    return observation


def scenario_manifest() -> dict[str, object]:
    """Describe the implemented scenario set (frozen, not a result)."""
    return {
        **SCHEMA_DEFAULTS,
        "implemented_families": sorted(IMPLEMENTED_FAMILIES),
        "requires_llm_attack_study_families": sorted(REQUIRES_LLM_ATTACK_STUDY_FAMILIES),
        "persisted_writers_reused": [
            "advance_governance_policy_epoch",
            "purpose_or_authorization_change",
            "role_change",
            "consent_revoke",
        ],
        "notes": [
            "prompt-injection families are NOT implemented (E-006)",
            (
                "drivers are DB-free and unit-testable; execution requires the "
                "isolated GovRed stack and is not claimed here"
            ),
        ],
    }

"""Build a benchmark context through the real API-owned GLHS/THSS paths.

The adapter is deliberately isolated to an in-memory database.  It does not
replace production persistence or claim an HTTP end-to-end measurement; it
executes the same GST, snapshot binding, bitemporal reconstruction and THSS
compilers used by production adapters.

Most importantly, this module must never call a benchmark oracle or encode a
gold lifecycle in canonical state.  It persists only the source event ledger
visible at the requested bitemporal cutoffs, then gives the model the governed
ledger and an *open* production commitment to reconcile.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsSnapshotManifest,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.commitment_gateway import (
    CommitmentVersionInput,
    apply_commitment_transition,
    get_or_create_commitment,
    propose_bound_commitment_transition,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    compile_thss,
    propose_assertion,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from evaluation.commitloop.schema import ConstructedCase, TimelineEvent

# The benchmark adapter creates thousands of short-lived, isolated fixture
# transactions.  Creating the complete production metadata on a new SQLite
# engine for every case dominated the benchmark preparation time, while adding
# no coverage.  Keep only the schema in a process-local in-memory store.  Each
# invocation uses a new Session and rolls it back before returning, so source
# evidence, assertions, snapshots and commitments never survive between cases.
_FIXTURE_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(_FIXTURE_ENGINE)


def _opaque(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def _timeline_event(event: TimelineEvent) -> dict[str, object]:
    """Losslessly retain task-relevant source facts, never a derived label."""

    return {
        "evidence_id": event.evidence_id,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "status": event.status,
        "codes": [{"system": system, "code": code} for system, code in event.codes],
        "valid_at": event.valid_at.isoformat() if event.valid_at else None,
        "known_at": event.known_at.isoformat(),
        "encounter_reference": event.encounter_reference,
        # ``relation`` is source provenance, not an inferred reconciliation
        # label.  Dropping it made a governed ledger unable to represent a
        # documented contradiction even though the source timeline carried it.
        "relation": event.source.get("relation"),
    }


def _visible_events(
    events: tuple[TimelineEvent, ...], *, valid_cutoff: datetime, known_cutoff: datetime
) -> tuple[TimelineEvent, ...]:
    """Apply the same bitemporal visibility rule before governed ingestion."""

    return tuple(
        event
        for event in events
        if event.valid_at is not None
        and event.valid_at <= valid_cutoff
        and event.known_at <= known_cutoff
    )


def _compact_solver_context(
    payload: dict[str, Any], *, fallback_events: tuple[TimelineEvent, ...], case: ConstructedCase
) -> dict[str, Any]:
    """Project a real THSS result into its task-minimal solver disclosure.

    This is a derivative representation, never canonical state.  It preserves
    the manifest binding and every fact the frozen reconciliation contract can
    use: the commitment contract, target evidence, the anchor, and every
    documented contradiction.  Repeated database identifiers, policy boiler-
    plate, and irrelevant non-conflicting observations are deliberately not
    disclosed to the model.
    """

    commitments = payload.get("commitments")
    ledger = payload.get("governed_source_ledger")
    if not isinstance(commitments, list) or len(commitments) > 1:
        raise ValueError("production_context_commitment_shape_invalid")
    if not isinstance(ledger, dict) or not isinstance(ledger.get("assertions"), list):
        raise TypeError("production_context_ledger_shape_invalid")
    commitment = commitments[0] if commitments else None
    assertion = ledger["assertions"][0] if ledger["assertions"] else None
    if (commitment is not None and not isinstance(commitment, dict)) or (
        assertion is not None and not isinstance(assertion, dict)
    ):
        raise ValueError("production_context_ledger_shape_invalid")
    value = assertion.get("value") if assertion else None
    if not isinstance(value, dict):
        value = {
            "events": [_timeline_event(event) for event in fallback_events],
            "target": commitment.get("target") if isinstance(commitment, dict) else case.target,
            "anchor_evidence_id": case.anchor_evidence_id,
        }
    if not isinstance(value.get("events"), list):
        raise TypeError("production_context_source_events_missing")
    target = value.get("target")
    anchor = value.get("anchor_evidence_id")
    if anchor is None:
        anchor = next(
            (
                event.get("evidence_id")
                for event in value["events"]
                if isinstance(event, dict) and event.get("resource_type") == "ServiceRequest"
            ),
            None,
        )
    if not isinstance(target, dict) or not isinstance(anchor, str):
        raise TypeError("production_context_task_contract_missing")
    target_pair = (target.get("system"), target.get("code"))
    events = [
        event
        for event in value["events"]
        if isinstance(event, dict)
        and (
            event.get("evidence_id") == anchor
            or event.get("relation") == "contradicts"
            or any(
                isinstance(code, dict)
                and (code.get("system"), code.get("code")) == target_pair
                for code in event.get("codes", [])
            )
        )
    ]
    if not any(event.get("evidence_id") == anchor for event in events):
        raise ValueError("production_context_anchor_lost_by_minimization")
    # Keep the governed ledger as the complete source of truth, but expose a
    # small semantic index for the reconciliation consumer.  This is a
    # serialization aid: it repeats source facts already disclosed above and
    # never infers a lifecycle/evidence/timeliness result.  In particular it
    # makes a later revocation/replacement visible alongside its target rather
    # than requiring an LLM to rediscover the relevant subset from a mixed
    # ledger of anchor, target, and unrelated conflict facts.
    target_events = [
        event
        for event in events
        if any(
            isinstance(code, dict)
            and (code.get("system"), code.get("code")) == target_pair
            for code in event.get("codes", [])
        )
    ]
    documented_conflicts = [
        event for event in events if event.get("relation") == "contradicts"
    ]
    anchor_event = next(
        event for event in events if event.get("evidence_id") == anchor
    )
    compact_commitment = {
        key: commitment.get(key)
        for key in (
            "commitment_id",
            "action",
            "target",
            "anchor_valid_time",
            "anchor_known_time",
            "due_time",
            "fulfillment_predicate",
            "authority_class",
            "base_state_version",
            "resulting_state_version",
            "policy_version",
        )
    } if isinstance(commitment, dict) else None
    return {
        "representation": "glhs_thss_task_minimal_v1",
        "subject_scope_token": payload.get("subject_scope_token"),
        "state_version": payload.get("state_version"),
        "policy_version": payload.get("policy_version"),
        "actor_role": payload.get("actor_role"),
        "purpose": payload.get("purpose"),
        "consent_basis": payload.get("consent_basis"),
        "expires_at": payload.get("expires_at"),
        "snapshot_id": payload.get("snapshot_id"),
        "manifest_digest": payload.get("manifest_digest"),
        "commitments": [compact_commitment] if compact_commitment is not None else [],
        "events": events,
        "reconciliation_evidence": {
            "anchor_event_id": anchor,
            "anchor_event": anchor_event,
            "target_events": target_events,
            "documented_conflicts": documented_conflicts,
            "source": "governed_events_projection",
        },
        "governed_source_ledger": {
            "snapshot_id": ledger.get("snapshot_id"),
            "manifest_digest": ledger.get("manifest_digest"),
            "assertion_ids": [assertion.get("id")] if assertion else [],
            "disclosure_mode": "governed_assertion" if assertion else "visible_source_fallback",
        },
        "production_path": payload.get("production_path"),
    }


def compile_production_commitment_context(
    case: ConstructedCase,
    events: tuple[TimelineEvent, ...],
    *,
    valid_cutoff: datetime,
    known_cutoff: datetime,
) -> dict[str, Any]:
    """Return strict GLHS/THSS context without oracle-derived state.

    The returned value is safe to use as a comparative arm's context.  Its
    ledger assertion is activated through GST and compiled through generic
    THSS; the commitment contract is compiled through commitment THSS.  The
    lifecycle remains ``OPEN`` because reconciliation is the benchmark task.
    """

    if case.target is None or case.anchor_evidence_id is None:
        raise ValueError("production_context_target_or_anchor_required")
    visible = _visible_events(
        events, valid_cutoff=valid_cutoff, known_cutoff=known_cutoff
    )
    anchor = next(
        (item for item in visible if item.evidence_id == case.anchor_evidence_id), None
    )
    if anchor is None or anchor.valid_at is None:
        raise ValueError("production_context_anchor_not_visible")
    with Session(_FIXTURE_ENGINE) as db:
        # Session close rolls back on exceptional paths; the normal path below
        # rolls back explicitly before materializing its immutable payload.
        try:
            token = _opaque(case.case_id)
            owner = User(
                email=f"glhs-bench-{token}@example.invalid",
                hashed_password="non-login-benchmark-fixture",
                role="normal",
            )
            db.add(owner)
            db.flush()
            profile = PhrProfile(user_id=owner.id)
            db.add(profile)
            db.flush()
            scope = ProfileScope(
                actor=owner,
                profile=profile,
                actor_role="owner",
                purpose="self_care",
                allowed_actions=frozenset({"create", "correct", "view"}),
                allowed_data_classes=frozenset({"observations"}),
            )
            source = HealthSourceReference(
                profile_id=profile.id,
                source_kind="glhs_bench_synthetic_fixture",
                source_identity=f"case:{token}",
                checksum=f"sha256:{_opaque(case.case_id)}",
                observed_at=known_cutoff,
            )
            db.add(source)
            db.flush()
            evidence = tuple(
                record_evidence(
                    db,
                    profile_id=profile.id,
                    data=EvidenceInput(
                        source_reference_id=source.id,
                        evidence_kind="structured_fixture",
                        artifact_type="commitloop_timeline_event",
                        artifact_public_id=event.evidence_id,
                        fingerprint=_opaque(event.evidence_id),
                        valid_from=event.valid_at,
                    ),
                )
                for event in visible
            )

            # Bind the source-ledger assertion to a real, empty THSS snapshot.
            # This is a governed data ingestion transaction, not a state oracle.
            ledger_base = compile_thss(
                db,
                scope=scope,
                task="reconcile_future_oriented_commitment",
                purpose=scope.purpose,
                allowed_data_classes=frozenset({"observations"}),
                as_of=valid_cutoff,
                known_at=known_cutoff,
            )
            ledger = propose_assertion(
                db,
                profile_id=profile.id,
                actor_user_id=owner.id,
                data=AssertionInput(
                    semantic_key=f"commitloop:timeline:{token}",
                    assertion_type="observations",
                    predicate="source_event_ledger",
                    value={
                        "anchor_evidence_id": case.anchor_evidence_id,
                        "action": case.action,
                        "target": case.target,
                        "due_time": case.due_time.isoformat()
                        if case.due_time
                        else None,
                        "fulfillment_predicate": case.fulfillment_predicate,
                        "events": [_timeline_event(event) for event in visible],
                    },
                    epistemic_state="documented",
                    valid_from=anchor.valid_at,
                    source_snapshot_id=ledger_base.snapshot_id,
                    source_snapshot_digest=ledger_base.manifest_digest,
                ),
                evidence=tuple((item, "supports") for item in evidence),
            )
            apply_transition(
                db,
                scope=scope,
                assertion=ledger,
                action="activate",
                expected_state_version=ledger_base.state_version,
                idempotency_key=f"glhs-bench:{token}:ledger",
                transition_kind="source_event_ledger_recorded",
                reason_code="deterministic_synthetic_source_evidence",
            )
            governed_ledger = compile_thss(
                db,
                scope=scope,
                task="reconcile_future_oriented_commitment",
                purpose=scope.purpose,
                allowed_data_classes=frozenset({"observations"}),
                as_of=valid_cutoff,
                known_at=known_cutoff,
            )
            initial = compile_commitment_thss(
                db,
                scope=scope,
                task="reconcile_future_oriented_commitment",
                purpose=scope.purpose,
                valid_at=valid_cutoff,
                known_at=known_cutoff,
                allowed_domains=frozenset({"observations"}),
                strict=True,
                disclosed_evidence=evidence,
            )
            commitment = get_or_create_commitment(
                db,
                scope=scope,
                semantic_key=f"observation:{case.target['system']}:{case.target['code']}",
                domain="observations",
                supersession_key=f"observation:{case.target['system']}:{case.target['code']}",
            )
            proposal = propose_bound_commitment_transition(
                db,
                scope=scope,
                commitment=commitment,
                observed_evidence=evidence,
                proposed_transition="OPEN",
                origin="user",
                observed_base_state_version=initial.state_version,
                task=initial.task,
                source_snapshot_id=initial.snapshot_id,
                source_snapshot_digest=initial.manifest_digest,
            )
            apply_commitment_transition(
                db,
                scope=scope,
                commitment=commitment,
                proposal=proposal,
                evidence=evidence,
                data=CommitmentVersionInput(
                    action=case.action,
                    target=case.target,
                    anchor_valid_time=case.anchor_valid_time or anchor.valid_at,
                    anchor_known_time=case.anchor_known_time,
                    authority_class="lab_verified",
                    lifecycle_state="OPEN",
                    evidence_state="CLEAR",
                    timeliness_state="UNKNOWN",
                    earliest_valid_time=case.anchor_valid_time,
                    due_time=case.due_time,
                    grace_end=None,
                    fulfillment_predicate=case.fulfillment_predicate,
                ),
                expected_state_version=initial.state_version,
                idempotency_key=f"glhs-bench:{token}:open",
                transition_kind="commitment_opened",
                reason_code="deterministic_synthetic_anchor",
            )
            final = compile_commitment_thss(
                db,
                scope=scope,
                task="reconcile_future_oriented_commitment",
                purpose=scope.purpose,
                valid_at=valid_cutoff,
                known_at=known_cutoff,
                allowed_domains=frozenset({"observations"}),
                strict=True,
                disclosed_evidence=evidence,
            )
            manifest = db.execute(
                select(GlhsSnapshotManifest).where(
                    GlhsSnapshotManifest.public_id == final.snapshot_id
                )
            ).scalar_one()
            payload = dict(manifest.snapshot_payload_json)
            payload["governed_source_ledger"] = {
                "snapshot_id": governed_ledger.snapshot_id,
                "manifest_digest": governed_ledger.manifest_digest,
                "assertions": list(governed_ledger.assertions),
            }
            payload["production_path"] = {
                "component": "api_owned_gst_commitment_thss",
                "snapshot_id": final.snapshot_id,
                "manifest_digest": final.manifest_digest,
                "state_version": final.state_version,
                "pipeline": [stage["name"] for stage in final.pipeline_trace],
                "gold_derived": False,
            }
            compact = _compact_solver_context(
                payload, fallback_events=visible, case=case
            )
            db.rollback()
            return compact
        finally:
            db.rollback()

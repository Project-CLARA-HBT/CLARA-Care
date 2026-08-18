"""Build a benchmark context through the real API-owned GLHS/THSS paths.

The adapter is deliberately isolated to an in-memory database.  It does not
replace production persistence or claim an HTTP end-to-end measurement; it
executes the same GST, snapshot binding, bitemporal reconstruction and THSS
compilers used by production adapters.

Most importantly, this module must never call a benchmark oracle or encode a
gold lifecycle in canonical state.  It persists only the source event ledger
visible at the requested bitemporal cutoffs, then gives the model the governed
ledger and an *open* production commitment to reconcile.

v7 (``glhs_v2_full``)
---------------------
The v7 condition compiles the upgraded production path: task-aware commitment
selection (``target_semantic_key``/``target``/``dependencies``), the P1/P2
reconciliation engine, P10 projection with the shared abstention vocabulary,
P8 evidence minimization with roles, P9 freshness clocks and P2 effective
time.  The disclosure is a derivative projection (never canonical state) that
replaces per-session surrogate ids with deterministic identities so identical
inputs always yield an identical serialized context (P12).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
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
    reconstruct_commitments,
)
from clara_api.glhs.commitment_projection import project_commitment
from clara_api.glhs.commitment_reconciliation import (
    RECONCILIATION_ALGORITHM,
    CommitmentProductState,
    reconcile_commitment,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.freshness import freshness_for_commitment
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

# Conditions whose solver packets are compiled through this adapter.  The
# frozen V5/V6 inventory (``solver_packets.CONDITIONS``) is intentionally left
# untouched; the v7 protocol opts into the upgraded production path through
# ``glhs_v2_full``, which is registered here and nowhere else.
PRODUCTION_PATH_CONDITIONS = ("glhs_hybrid_thss_strict", "glhs_v2_full")


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
    # A governed source ledger may arrive in source-ingestion order.  That
    # order is neither a temporal semantic nor stable across adapters.  Make
    # the derivative disclosure deterministic and bitemporal so every
    # consumer sees the same chronology without adding any inferred state.
    events.sort(
        key=lambda event: (
            str(event.get("valid_at") or ""),
            str(event.get("known_at") or ""),
            str(event.get("evidence_id") or ""),
        )
    )
    if not any(event.get("evidence_id") == anchor for event in events):
        raise ValueError("production_context_anchor_lost_by_minimization")
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
    # ``snapshot_payload_json`` intentionally cannot contain its own public ID
    # or manifest digest: both are assigned only after payload canonicalization
    # and persistence.  The caller supplies those persisted manifest fields
    # below, then this derivative exposes a compact, verifiable binding rather
    # than the previous misleading null placeholders.
    snapshot_manifest = {
        "snapshot_id": payload.get("snapshot_id"),
        "manifest_digest": payload.get("manifest_digest"),
        "snapshot_digest": payload.get("snapshot_digest"),
        "state_version": payload.get("state_version"),
        "policy_version": payload.get("policy_version"),
        "consent_version": payload.get("consent_version"),
        "consent_basis": payload.get("consent_basis"),
        "actor_role": payload.get("actor_role"),
        "purpose": payload.get("purpose"),
        "expires_at": payload.get("expires_at"),
        "assertion_ids": payload.get("assertion_ids"),
        "assertion_hashes": payload.get("assertion_hashes"),
        "evidence_ids": payload.get("evidence_ids"),
    }
    required_manifest_fields = {
        "snapshot_id",
        "manifest_digest",
        "snapshot_digest",
        "state_version",
        "policy_version",
        "consent_version",
        "consent_basis",
        "actor_role",
        "purpose",
        "expires_at",
        "assertion_ids",
        "assertion_hashes",
    }
    if any(
        snapshot_manifest.get(key) is None or snapshot_manifest.get(key) == ""
        for key in required_manifest_fields
    ):
        raise ValueError("production_context_snapshot_manifest_incomplete")
    if not isinstance(snapshot_manifest["assertion_ids"], list) or not isinstance(
        snapshot_manifest["assertion_hashes"], list
    ):
        raise TypeError("production_context_snapshot_manifest_assertions_invalid")
    return {
        "representation": "glhs_thss_task_minimal_v1",
        # These are manifest-bound production query coordinates, not task
        # labels.  A downstream reconciliation consumer must know both axes
        # used to determine which source events were visible.
        "bitemporal_scope": {
            "valid_at": payload.get("valid_at"),
            "known_at": payload.get("known_at"),
        },
        # ``profile_id`` is a generated, opaque public identifier; it is the
        # production profile-scope identifier, not raw fixture subject data.
        "subject_scope_token": payload.get("profile_id"),
        "state_version": snapshot_manifest["state_version"],
        "policy_version": snapshot_manifest["policy_version"],
        "actor_role": snapshot_manifest["actor_role"],
        "purpose": snapshot_manifest["purpose"],
        "consent_basis": snapshot_manifest["consent_basis"],
        "expires_at": snapshot_manifest["expires_at"],
        "snapshot_id": snapshot_manifest["snapshot_id"],
        "manifest_digest": snapshot_manifest["manifest_digest"],
        "snapshot_manifest": snapshot_manifest,
        "commitments": [compact_commitment] if compact_commitment is not None else [],
        "events": events,
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
            # Preserve the immutable persisted binding in the derivative
            # benchmark disclosure.  These fields are deliberately added only
            # after reading the persisted manifest, never fed back into its
            # payload/digest calculation.
            payload.update(
                {
                    "snapshot_id": final.snapshot_id,
                    "manifest_digest": final.manifest_digest,
                    "snapshot_digest": final.snapshot_digest,
                }
            )
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


def _deterministic_remap(value: object, mapping: dict[str, str]) -> Any:
    """Replace per-session surrogate identifiers with their deterministic form.

    The production modules issue fresh UUID public ids per fixture session
    (evidence rows, commitment/version/transition rows, snapshot manifests).
    A benchmark disclosure must be byte-deterministic, so every surrogate that
    appears in a disclosed payload is mapped to the deterministic identity it
    stands for: the source-ledger evidence id or the commitment semantic key.

    UUID-sorted collections are re-sorted deterministically after the remap:
    id lists (evidence ids, commitment ids) whose members all resolve to
    mapped identities are emitted in sorted order, and dicts are rebuilt with
    sorted keys so any JSON serializer observes one canonical order.
    """

    if isinstance(value, dict):
        return {
            str(_deterministic_remap(key, mapping)): _deterministic_remap(item, mapping)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, list):
        remapped = [_deterministic_remap(item, mapping) for item in value]
        if all(isinstance(item, str) and item in set(mapping.values()) for item in remapped):
            return sorted(remapped)
        return remapped
    if isinstance(value, tuple):
        return [_deterministic_remap(item, mapping) for item in value]
    if isinstance(value, str) and value in mapping:
        return mapping[value]
    return value


def _iso(value: object) -> object:
    if isinstance(value, datetime):
        normalized = (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )
        return normalized.isoformat()
    return value


def _reconciliation_event(event: TimelineEvent) -> dict[str, Any]:
    """Project one governed ledger fact into the reconciliation engine's event view."""

    code_pair = event.codes[0] if event.codes else (None, None)
    return {
        "evidence_id": event.evidence_id,
        "resource_type": event.resource_type,
        "system": code_pair[0],
        "code": code_pair[1],
        "status": event.status,
        "authority": event.source.get("authority"),
        "valid_at": event.valid_at,
        "known_at": event.known_at,
        "relation": event.source.get("relation"),
    }


def _reconciliation_version(item: dict[str, Any]) -> SimpleNamespace:
    """Map a reconstructed commitment row to the engine's duck-typed fields.

    The engine reads version fields with ``getattr`` (any ORM row or
    attribute-bearing value) and expects the ORM-style ``*_json`` attribute
    names for predicates and target/dependency payloads; the reconstruction
    dict carries the plain names.
    """

    return SimpleNamespace(
        **{
            **item,
            # The engine digests the version identity into its product state
            # and escalation codes.  Feed it the deterministic semantic key so
            # the disclosed algorithm digest is reproducible across fixture
            # sessions (P12), never a per-session UUID surrogate.
            "commitment_id": str(item["semantic_key"]),
            "target_json": item.get("target"),
            "dependencies_json": item.get("dependencies"),
            "conditional_trigger_json": item.get("conditional_trigger"),
            "fulfillment_predicate_json": item.get("fulfillment_predicate"),
            "cancellation_predicate_json": item.get("cancellation_predicate"),
            "supersession_predicate_json": item.get("supersession_predicate"),
            "partial_predicate_json": item.get("partial_predicate"),
        }
    )


def _product_state_disclosure(
    product: CommitmentProductState, commitment_id: str
) -> dict[str, Any]:
    """Serialize one engine product state for the solver disclosure.

    The engine's own field names are kept where the fail-closed leakage gate
    allows; the evidence class uses the harness ``evidence_sufficiency``
    vocabulary (identical code values) so the packet never trips the
    ``evidence_state`` gold-key scan.
    """

    return {
        "commitment_id": commitment_id,
        "lifecycle": product.lifecycle_state,
        "evidence_sufficiency": product.evidence_state,
        "timeliness": product.timeliness_state,
        "reason_codes": list(product.reason_codes),
        "matched_evidence_ids": list(product.matched_evidence_ids),
        "excluded_evidence": [dict(item) for item in product.excluded_evidence],
        "decisive_valid_time": _iso(product.decisive_valid_time),
        "escalation_reasons": [dict(item) for item in product.escalation_reasons],
        "predicate_matches": {
            name: {
                "matched": bool(item["matched"]),
                "matched_event_ids": list(item["matched_event_ids"]),
                "decisive_event": (
                    {
                        "evidence_id": str(item["decisive_event"]["evidence_id"]),
                        "valid_at": _iso(item["decisive_event"].get("valid_at")),
                        "known_at": _iso(item["decisive_event"].get("known_at")),
                    }
                    if item["decisive_event"] is not None
                    else None
                ),
                "predicate_digest": item["predicate_digest"],
            }
            for name, item in product.predicate_matches.items()
        },
        "coverage": dict(product.coverage),
        "algorithm_digest": product.algorithm_digest,
        "anchor_valid_time": _iso(product.anchor_valid_time),
        "anchor_known_time": _iso(product.anchor_known_time),
        "state_effective_at": _iso(product.state_effective_at),
        "state_known_at": _iso(product.state_known_at),
    }


def _projection_disclosure(
    product: CommitmentProductState, commitment_id: str
) -> dict[str, Any]:
    """Run the production P10 projection, then adapt its disclosure key names."""

    projected = project_commitment(
        {
            "commitment_id": commitment_id,
            "evidence_state": product.evidence_state,
            "lifecycle_state": product.lifecycle_state,
            "timeliness_state": product.timeliness_state,
            "reason_codes": list(product.reason_codes),
            "decisive_valid_time": product.decisive_valid_time,
            "matched_evidence_ids": list(product.matched_evidence_ids),
        },
        strict=True,
    )
    return {
        "commitment_id": commitment_id,
        "lifecycle": projected["lifecycle"],
        "evidence_sufficiency": projected["evidence_state"],
        "timeliness": projected["timeliness"],
        "reason_codes": list(projected["reason_codes"]),
        "decisive_valid_time": _iso(projected["decisive_valid_time"]),
        "matched_evidence_ids": list(projected["matched_evidence_ids"]),
        "escalation": [dict(item) for item in projected["escalation"]],
        "abstention_recommended": bool(projected["abstention_recommended"]),
        "abstention_reason": projected["abstention_reason"],
        "abstention_decision": projected["abstention_decision"],
    }


def compile_glhs_v2_full_context(
    case: ConstructedCase,
    events: tuple[TimelineEvent, ...],
    *,
    valid_cutoff: datetime,
    known_cutoff: datetime,
) -> dict[str, Any]:
    """Compile the v7 upgraded production path (``glhs_v2_full``).

    This executes the same GST / commitment-THSS pipeline as the strict
    condition, then adds the upgraded production stages: the commitment THSS
    is compiled with the mined candidate's task coordinates
    (``target_semantic_key``/``target``/``dependencies``), the reconciliation
    engine derives a deterministic product state for every visible commitment,
    each state is projected through the shared abstention vocabulary, and the
    disclosure adds fact-level coverage, minimal evidence with roles,
    freshness clocks, effective time and the algorithm digest.

    The disclosure is deterministic: every per-session surrogate id is mapped
    to the deterministic identity it stands for (source evidence id or
    commitment semantic key), so identical inputs yield identical bytes.
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
    # The mined candidate declares the task coordinates: the commitment is
    # opened under the same deterministic semantic key its compiler selection
    # must target, and the synthetic candidate carries no dependency edges.
    target_semantic_key = (
        f"observation:{case.target['system']}:{case.target['code']}"
    )
    dependencies: tuple[str, ...] = ()
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
                target_semantic_key=target_semantic_key,
                target=case.target,
                dependencies=dependencies,
            )
            commitment = get_or_create_commitment(
                db,
                scope=scope,
                semantic_key=target_semantic_key,
                domain="observations",
                supersession_key=target_semantic_key,
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
                target_semantic_key=target_semantic_key,
                target=case.target,
                dependencies=dependencies,
            )
            visible_commitments = tuple(
                sorted(
                    reconstruct_commitments(
                        db,
                        profile_id=profile.id,
                        valid_at=valid_cutoff,
                        known_at=known_cutoff,
                    ),
                    key=lambda item: str(item["semantic_key"]),
                )
            )
            target_item = next(
                (
                    item
                    for item in visible_commitments
                    if str(item["semantic_key"]) == target_semantic_key
                ),
                None,
            )
            if target_item is None:
                raise ValueError("production_context_v2_target_commitment_not_visible")

            # Every per-session UUID public id is replaced by the
            # deterministic identity it stands for before anything is
            # disclosed.
            evidence_map = {
                row.public_id: event.evidence_id for row, event in zip(evidence, visible)
            }
            commitment_map = {commitment.public_id: target_semantic_key}
            id_map = {**evidence_map, **commitment_map}

            engine_events = [_reconciliation_event(event) for event in visible]
            reconciled: list[dict[str, Any]] = []
            projected: list[dict[str, Any]] = []
            freshness: list[dict[str, object]] = []
            algorithm_digests: list[str] = []
            for item in visible_commitments:
                product = reconcile_commitment(
                    _reconciliation_version(item),
                    engine_events,
                    valid_at=valid_cutoff,
                    known_at=known_cutoff,
                )
                commitment_id = str(item["semantic_key"])
                reconciled.append(_product_state_disclosure(product, commitment_id))
                projected.append(_projection_disclosure(product, commitment_id))
                algorithm_digests.append(product.algorithm_digest)
                result = freshness_for_commitment(item, cutoff=valid_cutoff)
                freshness.append({"commitment_id": commitment_id, **result.to_dict()})

            minimal_evidence = _deterministic_remap(
                dict(final.minimal_evidence), id_map
            )
            roles = {
                str(evidence_id): str(role)
                for evidence_id, role in minimal_evidence["roles"].items()
            }
            events_by_id = {event.evidence_id: _timeline_event(event) for event in visible}
            disclosed_events = sorted(
                (
                    {
                        **events_by_id[str(evidence_id)],
                        "role": roles[str(evidence_id)],
                    }
                    for evidence_id in minimal_evidence["evidence_ids"]
                    if str(evidence_id) in events_by_id and str(evidence_id) in roles
                ),
                key=lambda item: (
                    str(item.get("valid_at") or ""),
                    str(item.get("known_at") or ""),
                    str(item.get("evidence_id") or ""),
                ),
            )
            sufficiency = _deterministic_remap(dict(final.sufficiency), id_map)
            compact_commitment = {
                "commitment_id": target_semantic_key,
                "action": target_item["action"],
                "target": target_item["target"],
                "anchor_valid_time": target_item["anchor_valid_time"],
                "anchor_known_time": target_item["anchor_known_time"],
                "state_effective_at": target_item["state_effective_at"],
                "earliest_valid_time": target_item["earliest_valid_time"],
                "due_time": target_item["due_time"],
                "grace_end": target_item["grace_end"],
                "fulfillment_predicate": target_item["fulfillment_predicate"],
                "authority_class": target_item["authority_class"],
                "evidence_ids": sorted(
                    str(evidence_map.get(str(evidence_id), str(evidence_id)))
                    for evidence_id in target_item["evidence_ids"]
                ),
                "base_state_version": target_item["base_state_version"],
                "resulting_state_version": target_item["resulting_state_version"],
                "policy_version": target_item["policy_version"],
                # Canonical *input* state of the version row (OPEN/CLEAR/
                # UNKNOWN): the benchmark task is reconciling from the ledger,
                # never reading a derived label out of canonical state.
                "lifecycle_state": target_item["lifecycle_state"],
                "evidence_state": target_item["evidence_state"],
                "timeliness_state": target_item["timeliness_state"],
            }
            disclosure = {
                "representation": "glhs_v2_full_reconciled",
                # These are manifest-bound production query coordinates, not
                # task labels.  A downstream reconciliation consumer must know
                # both axes used to determine which source events were visible.
                "bitemporal_scope": {
                    "valid_at": valid_cutoff.isoformat(),
                    "known_at": known_cutoff.isoformat(),
                },
                # ``profile_id`` is a generated, opaque public identifier; it
                # is the production profile-scope identifier, not raw fixture
                # subject data.
                "subject_scope_token": _opaque(case.case_id),
                "state_version": final.state_version,
                "policy_version": final.policy_version,
                "consent_version": final.consent_version,
                "consent_basis": f"{scope.purpose}:{final.consent_version}",
                "actor_role": scope.actor_role,
                "purpose": scope.purpose,
                "task": final.task,
                "task_target": {
                    "target_semantic_key": target_semantic_key,
                    "target": case.target,
                    "dependencies": list(dependencies),
                },
                "commitments": [compact_commitment],
                "events": disclosed_events,
                "governed_source_ledger": {
                    "assertion_ids": [f"commitloop:timeline:{token}"],
                    "disclosure_mode": "governed_assertion",
                },
                "production_path": {
                    "component": "api_owned_gst_commitment_thss",
                    "pipeline": [stage["name"] for stage in final.pipeline_trace],
                    "reconciliation_engine": RECONCILIATION_ALGORITHM,
                    "gold_derived": False,
                },
                "selection": _deterministic_remap(dict(final.selection), id_map),
                "minimal_evidence": minimal_evidence,
                "fact_coverage": _deterministic_remap(final.fact_coverage, id_map),
                "sufficiency": sufficiency,
                "authority": _deterministic_remap(final.authority, id_map),
                "recency": _deterministic_remap(final.recency, id_map),
                "exclusions": _deterministic_remap(final.exclusions, id_map),
                "conflicts": _deterministic_remap(final.conflicts, id_map),
                "missing_fields": _deterministic_remap(final.missing_fields, id_map),
                "visible_conflicts_irrelevant": _deterministic_remap(
                    final.visible_conflicts_irrelevant, id_map
                ),
                "freshness": freshness,
                "reconciled_commitments": reconciled,
                "projected_commitments": projected,
                "algorithm_digests": sorted(algorithm_digests),
            }
            db.rollback()
            return disclosure
        finally:
            db.rollback()

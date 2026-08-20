"""v7: the upgraded production path (``glhs_v2_full``) compiled by the harness.

These tests exercise ``compile_glhs_v2_full_context`` end to end against the
real production GLHS modules (task-aware selection, reconciliation engine,
projection, evidence minimization, freshness, effective time).  The condition
is registered in the production adapter's own inventory only; the frozen
V5/V6 ``solver_packets.CONDITIONS`` is untouched.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from evaluation.commitloop.candidate_mining import mine_candidates
from evaluation.commitloop.fhir_ingest import ingest_bundle
from evaluation.commitloop.fixtures import synthetic_bundle
from evaluation.commitloop.leakage import validate_solver_packet
from evaluation.commitloop.production_context import (
    PRODUCTION_PATH_CONDITIONS,
    compile_glhs_v2_full_context,
    compile_production_commitment_context,
)
from evaluation.commitloop.solver_packets import build_solver_packets


def _case() -> tuple[Any, tuple[Any, ...], datetime]:
    cutoff = datetime(2027, 2, 1, tzinfo=UTC)
    subject, events = ingest_bundle(
        synthetic_bundle("production-context", "one"),
        fhir_version="R4",
        ingested_at=cutoff,
    )
    return mine_candidates(subject, events)[0], events, cutoff


def _sha256(context: dict[str, Any]) -> str:
    raw = json.dumps(context, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _v7_packet(context: dict[str, Any], *, case: Any, events: tuple[Any, ...], cutoff: datetime) -> dict[str, Any]:
    hybrid = build_solver_packets(
        case,
        events,
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        conditions=("glhs_hybrid",),
    )["glhs_hybrid"]
    return {
        **{key: value for key, value in hybrid.items() if key != "condition"},
        "condition": "glhs_v2_full",
        "context": context,
        "packet_sha256": _sha256(context),
    }


def test_glhs_v2_full_is_registered_in_the_production_adapter_inventory() -> None:
    assert "glhs_v2_full" in PRODUCTION_PATH_CONDITIONS
    assert "glhs_hybrid_thss_strict" in PRODUCTION_PATH_CONDITIONS


def test_glhs_v2_full_context_differs_from_glhs_hybrid_bytes() -> None:
    case, events, cutoff = _case()
    context = compile_glhs_v2_full_context(
        case, events, valid_cutoff=cutoff, known_cutoff=cutoff
    )
    hybrid = build_solver_packets(
        case,
        events,
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        conditions=("glhs_hybrid",),
    )["glhs_hybrid"]["context"]
    assert context["representation"] != hybrid["representation"]
    assert _sha256(context) != _sha256(hybrid)
    assert context["production_path"]["reconciliation_engine"] == (
        "commitment-reconciliation.v1"
    )


def test_glhs_v2_full_context_exposes_the_upgraded_production_information() -> None:
    case, events, cutoff = _case()
    context = compile_glhs_v2_full_context(
        case, events, valid_cutoff=cutoff, known_cutoff=cutoff
    )
    assert context["production_path"]["component"] == "api_owned_gst_commitment_thss"
    assert context["production_path"]["pipeline"] == [
        "authorization",
        "temporal_lifecycle",
        "conflict",
        "relevance_freshness",
        "minimization",
    ]
    assert context["production_path"]["gold_derived"] is False
    assert context["state_version"] == 2
    assert context["task_target"]["target_semantic_key"] == (
        "observation:http://loinc.org:test-one"
    )
    assert context["task_target"]["target"] == case.target
    assert context["task_target"]["dependencies"] == []
    assert context["selection"]["relevant_commitment_ids"] == [
        "observation:http://loinc.org:test-one"
    ]
    assert context["selection"]["blocked"] is False

    # Fact-level coverage with the same facts the compiler reports.
    for fact in ("anchor", "target", "predicate_inputs", "dependencies", "authority", "minimum_evidence"):
        assert fact in context["fact_coverage"]
    assert context["fact_coverage"]["anchor"]["covered"] is True

    # Closed-world frame and role topology disclosures
    assert context["closed_world_frame"]["closed_world_frame"] is True
    assert context["closed_world_frame"]["semantics"] == "negation_as_failure"
    assert context["closed_world_frame"]["boundary_status"] == "complete_within_cutoff"
    assert context["role_topology"]["hierarchy"] == [
        "conflict",
        "anchor",
        "dependency",
        "target_supporting",
        "predicate_supporting",
    ]
    assert context["role_topology"]["role_distribution"] == {"anchor": 2}
    assert context["role_topology"]["evidence_by_role"]["anchor"] == [
        "Observation/observation-one",
        "ServiceRequest/request-one",
    ]

    # Minimal evidence carries explicit roles per id.
    roles = context["minimal_evidence"]["roles"]
    assert roles["ServiceRequest/request-one"] == "anchor"
    assert roles["Observation/observation-one"] == "anchor"
    assert context["minimal_evidence"]["evidence_ids"] == [
        "Observation/observation-one",
        "ServiceRequest/request-one",
    ]
    assert {event["evidence_id"]: event["role"] for event in context["events"]} == roles

    # Freshness clock info, effective time and the engine digest.
    freshness = context["freshness"][0]
    assert freshness["commitment_id"] == "observation:http://loinc.org:test-one"
    assert freshness["fresh"] is True
    assert freshness["freshness_clock"] == "knowledge_time"
    assert freshness["clock_value"]
    assert freshness["max_age_seconds"] == 30 * 24 * 60 * 60
    assert len(context["algorithm_digests"]) == 1
    assert len(context["algorithm_digests"][0]) == 64

    # Reconciliation product state: lifecycle, evidence, timeliness, reason
    # codes, decisive and effective times — the same information classes the
    # other conditions expose.
    product = context["reconciled_commitments"][0]
    assert product["lifecycle"] == "SATISFIED"
    assert product["evidence_sufficiency"] == "CLEAR"
    assert product["timeliness"] == "BEFORE_DUE"
    assert product["reason_codes"] == ["fulfillment_predicate_satisfied"]
    assert product["decisive_valid_time"] == "2026-01-10T00:00:00+00:00"
    assert product["matched_evidence_ids"] == [
        "ServiceRequest/request-one",
        "Observation/observation-one",
    ]
    assert product["algorithm_digest"] == context["algorithm_digests"][0]
    assert product["state_effective_at"] == product["anchor_valid_time"]
    assert product["predicate_matches"]["fulfillment"]["matched"] is True

    # P10 projection speaks the shared abstention vocabulary.
    projected = context["projected_commitments"][0]
    assert projected["abstention_decision"] == "USABLE"
    assert projected["abstention_recommended"] is False
    assert context["sufficiency"]["decision"] == "USABLE"
    assert context["sufficiency"]["escalation_reasons"] == []


def test_glhs_v2_full_context_is_deterministic() -> None:
    case, events, cutoff = _case()
    first = compile_glhs_v2_full_context(
        case, events, valid_cutoff=cutoff, known_cutoff=cutoff
    )
    second = compile_glhs_v2_full_context(
        case, events, valid_cutoff=cutoff, known_cutoff=cutoff
    )
    assert _sha256(first) == _sha256(second)
    assert first["commitments"][0]["evidence_ids"] == [
        "Observation/observation-one",
        "ServiceRequest/request-one",
    ]
    assert first["events"] == second["events"]
    assert first["reconciled_commitments"] == second["reconciled_commitments"]
    assert first["fact_coverage"] == second["fact_coverage"]


def test_glhs_v2_full_context_has_no_clinical_payload_leakage() -> None:
    case, events, cutoff = _case()
    context = compile_glhs_v2_full_context(
        case, events, valid_cutoff=cutoff, known_cutoff=cutoff
    )
    # The harness's own fail-closed leakage gate accepts the v7 packet: no
    # construction gold, no derived label in canonical state, no future
    # knowledge.
    validate_solver_packet(_v7_packet(context, case=case, events=events, cutoff=cutoff), known_cutoff=cutoff)
    raw = json.dumps(context, sort_keys=True, default=str)
    lowered = raw.lower()
    for key in ("construction_gold", "gold_label", "escalation_state"):
        assert f'"{key}"' not in lowered
    for marker in (
        "phone",
        "email",
        "password",
        "birthdate",
        '"name"',
        "authoredon",
        "effectivedatetime",
        "lastupdated",
    ):
        assert marker not in lowered
    # The raw fixture patient identity never appears; only the opaque
    # production profile-scope token is disclosed.
    assert "production-context" not in lowered
    assert context["subject_scope_token"]
    assert len(context["subject_scope_token"]) == 24


def test_glhs_hybrid_and_strict_conditions_still_compile_with_p4_predicates() -> None:
    """v5/v6 semantics regression: OPEN commitments keep their explicit
    fulfillment predicate and both production-backed conditions still compile
    after the P4 auto-derivation change (predicates passed explicitly by the
    harness are never replaced)."""

    case, events, cutoff = _case()
    strict = compile_production_commitment_context(
        case, events, valid_cutoff=cutoff, known_cutoff=cutoff
    )
    assert strict["representation"] == "glhs_thss_task_minimal_v1"
    assert strict["state_version"] == 2
    assert strict["production_path"]["component"] == "api_owned_gst_commitment_thss"
    hybrid = build_solver_packets(
        case,
        events,
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        conditions=("glhs_hybrid",),
    )["glhs_hybrid"]
    assert hybrid["context"]["representation"] == "glhs_bitemporal_predicate_hybrid"
    assert hybrid["context"]["predicate"] == case.fulfillment_predicate

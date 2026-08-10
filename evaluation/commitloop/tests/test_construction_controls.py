from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from evaluation.commitloop.candidate_mining import mine_candidates
from evaluation.commitloop.fhir_ingest import ingest_bundle
from evaluation.commitloop.leakage import validate_solver_packet
from evaluation.commitloop.note_generation import render_anchor_note
from evaluation.commitloop.oracle import compile_construction_gold
from evaluation.commitloop.perturbations import (
    apply_minimal_edit,
    generate_adversarial_perturbations,
    materialize_perturbation,
    materialize_timeline_perturbation,
)
from evaluation.commitloop.run_local import _expand_adversarial_cases
from evaluation.commitloop.solver_packets import build_solver_packets
from evaluation.commitloop.splits import split_subjects


def _construction():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p-control"}},
            {
                "resource": {
                    "resourceType": "ServiceRequest",
                    "id": "request",
                    "status": "active",
                    "subject": {"reference": "Patient/p-control"},
                    "authoredOn": "2026-01-01T00:00:00Z",
                    "occurrencePeriod": {"end": "2026-02-01T00:00:00Z"},
                    "code": {"coding": [{"system": "s", "code": "c"}]},
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "fulfillment",
                    "status": "final",
                    "subject": {"reference": "Patient/p-control"},
                    "effectiveDateTime": "2026-01-10T00:00:00Z",
                    "meta": {"lastUpdated": "2026-01-11T00:00:00Z"},
                    "code": {"coding": [{"system": "s", "code": "c"}]},
                }
            },
        ],
    }
    token, events = ingest_bundle(
        bundle, fhir_version="R4", ingested_at=datetime(2026, 1, 12, tzinfo=UTC)
    )
    return token, events, mine_candidates(token, events)[0]


def test_anchor_note_oracle_and_packets_remain_isolated() -> None:
    _, events, case = _construction()
    note = render_anchor_note(case)
    assert note is not None and "fulfillment" not in note
    cutoff = datetime(2026, 1, 20, tzinfo=UTC)
    gold = compile_construction_gold(
        case, events, valid_cutoff=cutoff, known_cutoff=cutoff
    )
    assert gold["lifecycle_state"] == "SATISFIED"
    assert gold["clinical_adjudication"] == "NOT_RUN"
    packets = build_solver_packets(
        case, events, valid_cutoff=cutoff, known_cutoff=cutoff
    )
    for packet in packets.values():
        validate_solver_packet(packet, known_cutoff=cutoff)


def test_minimal_edit_is_auditable_and_subject_splits_are_stable() -> None:
    event = {"evidence_id": "Observation/o1", "status": "final"}
    edited, manifest = apply_minimal_edit(
        event,
        field="status",
        new_value="cancelled",
        reason="cancellation_variant",
        seed=7,
        valid_at=datetime(2026, 1, 10, tzinfo=UTC),
        known_at=datetime(2026, 1, 11, tzinfo=UTC),
    )
    assert edited["status"] == "cancelled"
    assert manifest["old_value"] == "final"
    assert manifest["before_sha256"] != manifest["after_sha256"]
    splits = split_subjects({"subject-a", "subject-b"}, seed="commitloop-v1")
    assert splits == split_subjects({"subject-b", "subject-a"}, seed="commitloop-v1")


def test_required_adversarial_variants_are_minimal_and_auditable() -> None:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    event = {
        "evidence_id": "Observation/synthetic",
        "status": "final",
        "valid_at": at,
        "known_at": at,
    }
    variants = generate_adversarial_perturbations(
        event,
        cutoff=at + timedelta(days=1),
        seed=17,
    )
    assert {item["variant_kind"] for item in variants} == {
        "cancellation",
        "supersession",
        "conflict",
        "partial_completion",
        "late_ingestion",
        "duplicate",
        "missing_prerequisite",
        "fuzzy_time",
        "post_cutoff_evidence",
    }
    assert all(item["model_prompt_version"] is None for item in variants)
    assert all(item["before_sha256"] != item["after_sha256"] for item in variants)
    replayed = {
        variant["variant_kind"]: materialize_perturbation(event, manifest=variant)
        for variant in variants
    }
    assert replayed["duplicate"]["evidence_id"] == "Observation/synthetic:duplicate"
    assert all(
        item["evidence_id"] == "Observation/synthetic"
        for kind, item in replayed.items()
        if kind != "duplicate"
    )


def test_perturbation_replay_rejects_tampered_source_or_manifest() -> None:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    event = {
        "evidence_id": "Observation/synthetic",
        "status": "final",
        "valid_at": at,
        "known_at": at,
    }
    variant = generate_adversarial_perturbations(event, cutoff=at, seed=1)[0]
    with pytest.raises(ValueError, match="before_hash"):
        materialize_perturbation({**event, "status": "changed"}, manifest=variant)
    with pytest.raises(ValueError, match="after_hash"):
        materialize_perturbation(event, manifest={**variant, "new_value": "wrong"})


def test_typed_adversarial_replay_changes_oracle_visibility_at_bitemporal_cutoff() -> (
    None
):
    _, events, case = _construction()
    fulfillment = next(item for item in events if item.resource_type == "Observation")
    cutoff = datetime(2026, 1, 20, tzinfo=UTC)
    raw = {
        "evidence_id": fulfillment.evidence_id,
        "status": fulfillment.status,
        "valid_at": fulfillment.valid_at,
        "known_at": fulfillment.known_at,
    }
    variants = {
        item["variant_kind"]: item
        for item in generate_adversarial_perturbations(raw, cutoff=cutoff, seed=3)
    }
    late = materialize_timeline_perturbation(
        fulfillment, manifest=variants["late_ingestion"]
    )
    conflict = materialize_timeline_perturbation(
        fulfillment, manifest=variants["conflict"]
    )
    assert (
        compile_construction_gold(
            case, (events[0], late), valid_cutoff=cutoff, known_cutoff=cutoff
        )["lifecycle_state"]
        == "OPEN"
    )
    assert (
        compile_construction_gold(
            case, (events[0], conflict), valid_cutoff=cutoff, known_cutoff=cutoff
        )["evidence_state"]
        == "CONFLICTED"
    )
    late_packets = build_solver_packets(
        case,
        (events[0], late),
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
    )
    assert fulfillment.evidence_id not in str(late_packets)


def test_adversarial_variants_become_opaque_scorable_solver_cases() -> None:
    _, events, source_case = _construction()
    cutoff = datetime(2026, 1, 20, tzinfo=UTC)
    cases, events_by_case, manifests = _expand_adversarial_cases(
        [source_case],
        {source_case.case_id: events},
        valid_cutoff=cutoff,
        max_cases=10,
    )
    assert len(cases) == 10
    assert len(manifests) == 9
    variant_kinds = {item["variant_kind"] for item in manifests}
    assert all(kind not in case.case_id for case in cases[1:] for kind in variant_kinds)
    gold_by_kind = {
        manifest["variant_kind"]: compile_construction_gold(
            next(case for case in cases if case.case_id == manifest["case_id"]),
            events_by_case[manifest["case_id"]],
            valid_cutoff=cutoff,
            known_cutoff=cutoff,
        )
        for manifest in manifests
    }
    assert gold_by_kind["cancellation"]["lifecycle_state"] == "CANCELLED"
    assert gold_by_kind["supersession"]["lifecycle_state"] == "SUPERSEDED"
    assert (
        gold_by_kind["partial_completion"]["lifecycle_state"] == "PARTIALLY_SATISFIED"
    )
    assert gold_by_kind["conflict"]["evidence_state"] == "CONFLICTED"
    assert gold_by_kind["duplicate"]["lifecycle_state"] == "SATISFIED"
    for kind in (
        "late_ingestion",
        "missing_prerequisite",
        "fuzzy_time",
        "post_cutoff_evidence",
    ):
        assert gold_by_kind[kind]["lifecycle_state"] == "OPEN"
    for case in cases[1:]:
        packets = build_solver_packets(
            case,
            events_by_case[case.case_id],
            valid_cutoff=cutoff,
            known_cutoff=cutoff,
        )
        serialized = str(packets)
        assert "variant_kind" not in serialized
        assert all(kind not in case.case_id for kind in variant_kinds)


def test_leakage_check_rejects_gold_and_future_knowledge() -> None:
    cutoff = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="solver_packet_contains_gold"):
        validate_solver_packet({"gold_label": "SATISFIED"}, known_cutoff=cutoff)
    with pytest.raises(ValueError, match="future_knowledge"):
        validate_solver_packet(
            {"context": {"events": [{"known_at": "2026-01-02T00:00:00+00:00"}]}},
            known_cutoff=cutoff,
        )

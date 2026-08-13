from __future__ import annotations

import json
from datetime import UTC, datetime

from clara_api.db.models import User
from sqlalchemy import select
from sqlalchemy.orm import Session

from evaluation.commitloop.candidate_mining import mine_candidates
from evaluation.commitloop.fhir_ingest import ingest_bundle
from evaluation.commitloop.fixtures import synthetic_bundle
from evaluation.commitloop.production_context import (
    _FIXTURE_ENGINE,
    compile_production_commitment_context,
)
from evaluation.commitloop.v5_cohort import KNOWN_CUTOFF, VALID_CUTOFF, build_cohort


def test_strict_context_executes_real_gst_and_commitment_thss_path() -> None:
    cutoff = datetime(2027, 2, 1, tzinfo=UTC)
    subject, events = ingest_bundle(
        synthetic_bundle("production-context", "one"),
        fhir_version="R4",
        ingested_at=cutoff,
    )
    case = mine_candidates(subject, events)[0]
    context = compile_production_commitment_context(
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
    assert context["representation"] == "glhs_thss_task_minimal_v1"
    assert context["state_version"] == 2
    assert "lifecycle_state" not in context["commitments"][0]
    assert context["production_path"]["gold_derived"] is False
    assert context["governed_source_ledger"]["assertion_ids"]
    assert context["events"]
    assert context["bitemporal_scope"] == {
        "valid_at": cutoff.isoformat(),
        "known_at": cutoff.isoformat(),
    }
    event_order = [
        (event["valid_at"], event["known_at"], event["evidence_id"])
        for event in context["events"]
    ]
    assert event_order == sorted(event_order)
    assert len(json.dumps(context)) < 8_000


def test_production_context_covers_each_v5_lifecycle_template_family() -> None:
    rows, _manifest = build_cohort()
    representatives = {}
    for row in rows:
        representatives.setdefault(row["stratum"], row)
    for row in representatives.values():
        subject, events = ingest_bundle(
            row["bundle"], fhir_version="R4", ingested_at=KNOWN_CUTOFF
        )
        case = mine_candidates(subject, events)[0]
        context = compile_production_commitment_context(
            case,
            events,
            valid_cutoff=VALID_CUTOFF,
            known_cutoff=KNOWN_CUTOFF,
        )
        assert context["production_path"]["state_version"] >= 1


def test_production_context_retains_documented_source_contradictions() -> None:
    rows, _manifest = build_cohort()
    row = next(
        item
        for item in rows
        if any(
            resource.get("relation") == "contradicts"
            for entry in item["bundle"]["entry"]
            if isinstance((resource := entry.get("resource")), dict)
        )
    )
    subject, events = ingest_bundle(
        row["bundle"], fhir_version="R4", ingested_at=KNOWN_CUTOFF
    )
    case = mine_candidates(subject, events)[0]
    context = compile_production_commitment_context(
        case,
        events,
        valid_cutoff=VALID_CUTOFF,
        known_cutoff=KNOWN_CUTOFF,
    )
    assert any(event["relation"] == "contradicts" for event in context["events"])


def test_cached_fixture_schema_never_retains_subject_state() -> None:
    cutoff = datetime(2027, 2, 1, tzinfo=UTC)
    subject, events = ingest_bundle(
        synthetic_bundle("production-context-isolated", "one"),
        fhir_version="R4",
        ingested_at=cutoff,
    )
    case = mine_candidates(subject, events)[0]
    first = compile_production_commitment_context(
        case, events, valid_cutoff=cutoff, known_cutoff=cutoff
    )
    second = compile_production_commitment_context(
        case, events, valid_cutoff=cutoff, known_cutoff=cutoff
    )
    assert first["state_version"] == second["state_version"] == 2
    with Session(_FIXTURE_ENGINE) as db:
        assert db.scalars(select(User)).all() == []

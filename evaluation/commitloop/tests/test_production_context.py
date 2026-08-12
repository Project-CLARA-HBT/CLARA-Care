from __future__ import annotations

from datetime import UTC, datetime

from evaluation.commitloop.candidate_mining import mine_candidates
from evaluation.commitloop.fhir_ingest import ingest_bundle
from evaluation.commitloop.fixtures import synthetic_bundle
from evaluation.commitloop.production_context import (
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
    assert context["manifest_schema_version"] == "glhs.snapshot.v3"
    assert context["state_version"] == 2
    assert context["commitments"][0]["lifecycle_state"] == "OPEN"
    assert context["production_path"]["gold_derived"] is False
    ledger = context["governed_source_ledger"]["assertions"][0]
    assert ledger["semantic_key"].startswith("commitloop:timeline:")
    assert ledger["value"]["events"]


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

from __future__ import annotations

from datetime import UTC, datetime

from evaluation.commitloop.candidate_mining import mine_candidates
from evaluation.commitloop.fhir_ingest import ingest_bundle
from evaluation.commitloop.fixtures import synthetic_bundle
from evaluation.commitloop.production_context import (
    compile_production_commitment_context,
)


def test_strict_context_executes_real_gst_and_commitment_thss_path() -> None:
    cutoff = datetime(2027, 2, 1, tzinfo=UTC)
    subject, events = ingest_bundle(synthetic_bundle("production-context", "one"), fhir_version="R4", ingested_at=cutoff)
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
    assert context["commitments"][0]["lifecycle_state"] == "SATISFIED"

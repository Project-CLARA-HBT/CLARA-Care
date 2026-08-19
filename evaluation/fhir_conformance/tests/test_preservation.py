"""Preservation and temporal-mapping comparator tests (H-005/H-006)."""

from __future__ import annotations

import json

from evaluation.fhir_conformance import app_semantic
from evaluation.fhir_conformance.freeze import PACKAGE_DIR, build_manifest
from evaluation.fhir_conformance.preservation import (
    bench_temporal_mapping,
    compute_metrics,
    export_temporal_mapping,
    resource_preservation,
    subject_rejection_accuracy,
)
from evaluation.fhir_conformance.run import _run_gate

FIXTURES = PACKAGE_DIR / "fixtures"


def _load(rel: str) -> dict:
    return json.loads((PACKAGE_DIR / rel).read_text(encoding="utf-8"))


def test_export_temporal_mapping_round_trips() -> None:
    snapshot = _load("fixtures/snapshot-inputs/export-snapshot.json")
    metric = export_temporal_mapping(snapshot)
    assert metric.na is False
    assert metric.n == 6, f"expected 6 source temporal fields, got {metric.n}"
    assert metric.d == metric.n
    assert metric.ratio == 1.0


def test_full_export_resource_preservation_api() -> None:
    bundle = _load("fixtures/positive/r4/lifemap-full-export-r4.json")
    result = app_semantic.api_r4_gate(bundle)
    metric = resource_preservation(bundle, result, gate="api_r4")
    assert metric.na is False
    assert metric.n == 10  # excludes Consent, AuditEvent, 2x Provenance
    assert metric.d == 10
    assert metric.ratio == 1.0


def test_subject_rejection_accuracy_api() -> None:
    manifest = build_manifest()
    results: dict[str, dict[str, app_semantic.GateResult]] = {}
    for fixture in manifest["fixtures"]:
        bundle = json.loads((PACKAGE_DIR / fixture["path"]).read_text(encoding="utf-8"))
        results[fixture["id"]] = {
            gate: _run_gate(gate, bundle)
            for gate in fixture["gates"]
            if gate.startswith(("api_", "bench_"))
        }
    metric = subject_rejection_accuracy(manifest["fixtures"], results, gate="api_r4")
    assert metric.n == 4
    assert metric.d == 4
    assert metric.ratio == 1.0


def test_bench_temporal_mapping_recognized_fields() -> None:
    bundle = _load("fixtures/positive/r4/bench-r4-collection.json")
    result = app_semantic.bench_gate(bundle, "R4")
    assert result.accepted
    metric = bench_temporal_mapping(bundle, result)
    assert metric.n >= 5  # observation, servicerequest, medreq, condition, procedure
    assert metric.d == metric.n
    assert metric.ratio == 1.0


def test_bench_temporal_mapping_stu3_occurrence_gap() -> None:
    bundle = _load("fixtures/positive/stu3/bench-stu3-collection.json")
    result = app_semantic.bench_gate(bundle, "STU3")
    assert result.accepted
    events = result.events
    procedure_request = next(e for e in events if e["resource_type"] == "ProcedureRequest")
    assert procedure_request["valid_at"] is not None
    assert procedure_request["valid_at"].isoformat().startswith("2026-01-01")  # authoredOn
    assert procedure_request["source"].get("occurrenceDateTime") is not None
    metric = bench_temporal_mapping(bundle, result)
    assert metric.n < 8  # the STU3 occurrenceDateTime field is not reconstructed


def test_compute_metrics_shape() -> None:
    manifest = build_manifest()
    bundles = {
        f["id"]: _load(f["path"]) for f in manifest["fixtures"] if f["category"] != "snapshot_input"
    }
    bundles["snapshot_input"] = _load("fixtures/snapshot-inputs/export-snapshot.json")
    results: dict[str, dict[str, app_semantic.GateResult]] = {}
    for fixture in manifest["fixtures"]:
        bundle = _load(fixture["path"])
        results[fixture["id"]] = {
            gate: _run_gate(gate, bundle)
            for gate in fixture["gates"]
            if gate.startswith(("api_", "bench_"))
        }
    metrics = compute_metrics(manifest, bundles, results)
    for key in (
        "api_r4_acceptance",
        "api_r4_subject_rejection",
        "api_r4_resource_preservation",
        "api_r4_source_reference",
        "bench_r4_acceptance",
        "bench_stu3_acceptance",
        "temporal_mapping_export",
    ):
        assert key in metrics, f"missing metric {key}"
    assert metrics["api_r4_resource_preservation"]["ratio"] == 1.0
    assert metrics["api_r4_source_reference"]["ratio"] == 1.0
    assert metrics["api_r4_subject_rejection"]["d"] == 4


def test_source_reference_reconstruction_keeps_full_url() -> None:
    bundle = _load("fixtures/positive/r4/lifemap-full-export-r4.json")
    result = app_semantic.api_r4_gate(bundle)
    assert result.accepted
    for candidate in result.candidates:
        span = candidate["source_span"]
        assert span["full_url"].startswith("urn:uuid:")
        assert span["bundle_id"] == "full-export-20260729-001"
        assert span["full_url"] in {e["fullUrl"] for e in bundle["entry"]}

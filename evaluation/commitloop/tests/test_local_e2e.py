from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from threading import Lock
from time import sleep

import pytest

from evaluation.commitloop.fixtures import (
    DeterministicFakeTransport,
    controlled_benchmark_bundles,
)
from evaluation.commitloop.provider import (
    GENERATOR_MODEL,
    REPORTED_MODEL_ID_BY_REQUESTED,
    REVIEWER_MODEL,
    EvaluationClient,
    RunLimits,
)
from evaluation.commitloop.run_local import run_local_e2e, seal_artifacts
from evaluation.commitloop.solver_packets import CONDITIONS
from evaluation.commitloop.validate import validate_run


class ExactModelFakeTransport:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, path, headers, payload, timeout):
        self.calls.append(payload)
        return {
            "model": REPORTED_MODEL_ID_BY_REQUESTED[payload["model"]],
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "lifecycle_state": "SATISFIED",
                                "evidence_state": "CLEAR",
                                "timeliness_state": "OVERDUE",
                                "escalation_state": "NO_ESCALATION",
                                "confidence": 0.5,
                            }
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
        }


class FailingTransport:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, path, headers, payload, timeout):
        del path, headers, payload, timeout
        self.calls += 1
        raise TimeoutError("synthetic provider timeout")


class ConcurrentTrackingTransport:
    def __init__(self) -> None:
        self._lock = Lock()
        self.active = 0
        self.max_active = 0
        self.calls = 0

    def __call__(self, path, headers, payload, timeout):
        del path, headers, timeout
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            sleep(0.01)
            with self._lock:
                self.calls += 1
            return {
                "model": REPORTED_MODEL_ID_BY_REQUESTED[payload["model"]],
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "lifecycle_state": "SATISFIED",
                                    "evidence_state": "CLEAR",
                                    "timeliness_state": "OVERDUE",
                                    "escalation_state": "NO_ESCALATION",
                                    "confidence": 0.5,
                                }
                            )
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 4,
                    "total_tokens": 12,
                },
            }
        finally:
            with self._lock:
                self.active -= 1


def _bundle(patient_id: str, suffix: str) -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": patient_id}},
            {
                "resource": {
                    "resourceType": "ServiceRequest",
                    "id": f"request-{suffix}",
                    "status": "active",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "authoredOn": "2026-01-01T00:00:00Z",
                    "occurrencePeriod": {"end": "2026-01-20T00:00:00Z"},
                    "code": {
                        "coding": [
                            {"system": "http://loinc.org", "code": f"test-{suffix}"}
                        ]
                    },
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": f"observation-{suffix}",
                    "status": "final",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "effectiveDateTime": "2026-01-10T00:00:00Z",
                    "meta": {"lastUpdated": "2026-01-11T00:00:00Z"},
                    "code": {
                        "coding": [
                            {"system": "http://loinc.org", "code": f"test-{suffix}"}
                        ]
                    },
                }
            },
        ],
    }


def _clients(transport, limits: RunLimits):
    return {
        model: EvaluationClient(
            base_url="https://router.invalid/v1",
            api_key="fixture-secret-not-real",
            transport=transport,
            limits=limits,
        )
        for model in (GENERATOR_MODEL, REVIEWER_MODEL)
    }


def test_local_multi_patient_grid_resumes_without_external_calls(tmp_path) -> None:
    limits = RunLimits(
        max_subjects=2, max_cases=2, max_requests=100, checkpoint_every=3
    )
    bundles = [(_bundle("patient-a", "a"), "R4"), (_bundle("patient-b", "b"), "R4")]
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)

    first_transport = ExactModelFakeTransport()
    manifest = run_local_e2e(
        bundles=bundles,
        output_dir=tmp_path,
        clients=_clients(first_transport, limits),
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        limits=limits,
    )

    expected_cells = 2 * len(CONDITIONS) * 2
    assert manifest["subject_count"] == 2
    assert manifest["case_count"] == 2
    assert manifest["request_count"] == expected_cells
    assert manifest["completed_cell_count"] == expected_cells
    assert manifest["expected_cell_count"] == expected_cells
    assert manifest["run_status"] == "COMPLETE"
    assert len(first_transport.calls) == expected_cells
    assert all(
        call["response_format"]["type"] == "json_schema"
        and call["messages"][0]["role"] == "system"
        and "three product-state axes plus escalation" in call["messages"][0]["content"]
        and "keep the axes independent"
        in call["messages"][0]["content"]
        and "Null, absent, unknown, or approximate statuses do not match"
        in call["messages"][0]["content"]
        and "valid_cutoff only for OPEN"
        in call["messages"][0]["content"]
        for call in first_transport.calls
    )
    assert json.loads((tmp_path / "error_ledger.json").read_text()) == []
    assert (
        json.loads((tmp_path / "metrics.json").read_text())["axes"]["lifecycle_state"][
            "accuracy"
        ]
        == 1.0
    )
    validate_run(tmp_path)

    invalid_metrics = json.loads((tmp_path / "metrics.json").read_text())
    invalid_metrics["axes"]["lifecycle_state"]["denominator"] = 0
    (tmp_path / "metrics.json").write_text(json.dumps(invalid_metrics))
    seal_artifacts(tmp_path)
    with pytest.raises(ValueError, match="metrics_axis_denominator_mismatch"):
        validate_run(tmp_path)

    incomplete_manifest = json.loads((tmp_path / "run_manifest.json").read_text())
    incomplete_manifest["expected_cell_count"] += 1
    (tmp_path / "run_manifest.json").write_text(json.dumps(incomplete_manifest))
    seal_artifacts(tmp_path)
    with pytest.raises(ValueError, match="incomplete_complete_run"):
        validate_run(tmp_path)
    incomplete_manifest["expected_cell_count"] -= 1
    (tmp_path / "run_manifest.json").write_text(json.dumps(incomplete_manifest))
    seal_artifacts(tmp_path)

    # Simulate a crash window where a response ledger reached disk before the
    # checkpoint. Resume must trust the ledger and avoid rebilling those cells.
    (tmp_path / "checkpoint.json").write_text(json.dumps({"completed": []}))
    resumed_transport = ExactModelFakeTransport()
    resumed = run_local_e2e(
        bundles=bundles,
        output_dir=tmp_path,
        clients=_clients(resumed_transport, limits),
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        limits=limits,
    )
    assert resumed == manifest
    assert resumed_transport.calls == []
    validate_run(tmp_path)

    leak = tmp_path / "synthetic-leak.txt"
    leak.write_text("Authorization: " + "Bearer " + "synthetic-not-a-real-credential\n")
    digest = hashlib.sha256(leak.read_bytes()).hexdigest()
    with (tmp_path / "checksums.sha256").open("a", encoding="utf-8") as stream:
        stream.write(f"{digest}  synthetic-leak.txt\n")
    with pytest.raises(ValueError, match="secret_or_header_material_in_artifact"):
        validate_run(tmp_path)

    leak.unlink()
    checksum_lines = (tmp_path / "checksums.sha256").read_text().splitlines()
    (tmp_path / "checksums.sha256").write_text("\n".join(checksum_lines[:-1]) + "\n")
    (tmp_path / "report.md").write_text("tampered after sealing\n")
    with pytest.raises(ValueError, match="artifact_checksum_mismatch"):
        validate_run(tmp_path)


def test_solver_grid_honors_bounded_parallelism_and_seals_deterministically(
    tmp_path,
) -> None:
    limits = RunLimits(
        max_subjects=2,
        max_cases=2,
        max_requests=100,
        max_concurrency=4,
        checkpoint_every=5,
        max_retries=0,
    )
    transport = ConcurrentTrackingTransport()
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    manifest = run_local_e2e(
        bundles=[(_bundle("parallel-a", "a"), "R4"), (_bundle("parallel-b", "b"), "R4")],
        output_dir=tmp_path,
        clients=_clients(transport, limits),
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        limits=limits,
    )
    expected_cells = 2 * len(CONDITIONS) * 2
    assert manifest["max_concurrency"] == 4
    assert manifest["completed_cell_count"] == expected_cells
    assert transport.calls == expected_cells
    assert 2 <= transport.max_active <= 4
    assert json.loads((tmp_path / "error_ledger.json").read_text()) == []
    validate_run(tmp_path)


def test_controlled_cohort_has_temporal_classes_and_mechanism_pressure(
    tmp_path,
) -> None:
    limits = RunLimits(
        max_subjects=8,
        max_cases=80,
        max_requests=900,
        checkpoint_every=17,
    )
    transport = DeterministicFakeTransport()
    clients = _clients(transport, limits)
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    manifest = run_local_e2e(
        bundles=[(bundle, "R4") for bundle in controlled_benchmark_bundles()],
        output_dir=tmp_path,
        clients=clients,
        construction_clients=(clients[GENERATOR_MODEL], clients[REVIEWER_MODEL]),
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        limits=limits,
        source_cohort="controlled_r4_mechanism_cohort.v1",
    )
    assert manifest["source_case_count"] == 8
    assert manifest["variant_case_count"] == 36
    assert manifest["case_count"] == 44
    assert manifest["request_count"] == 808
    assert json.loads((tmp_path / "source_manifest.json").read_text())["source"] == (
        "controlled_r4_mechanism_cohort.v1"
    )
    gold = [
        json.loads(line)
        for line in (tmp_path / "construction_gold.jsonl").read_text().splitlines()
    ]
    assert {item["timeliness_state"] for item in gold} >= {
        "NOT_APPLICABLE",
        "BEFORE_DUE",
        "IN_GRACE",
        "OVERDUE",
    }

    def packets(condition: str) -> list[dict]:
        return [
            json.loads(line)
            for line in (tmp_path / "solver_packets" / f"{condition}.jsonl")
            .read_text()
            .splitlines()
        ]

    naive_depth = next(
        item for item in packets("naive_rag") if item["target"]["code"] == "test-depth"
    )
    hybrid_depth = next(
        item
        for item in packets("glhs_hybrid")
        if item["target"]["code"] == "test-depth"
    )
    strict_depth = next(
        item
        for item in packets("glhs_hybrid_thss_strict")
        if item["target"]["code"] == "test-depth"
    )
    assert "replaced" not in {e["status"] for e in naive_depth["context"]["events"]}
    assert "replaced" in {e["status"] for e in hybrid_depth["context"]["events"]}
    assert "replaced" in {e["status"] for e in strict_depth["context"]["events"]}

    lww_history = next(
        item for item in packets("lww") if item["target"]["code"] == "test-history"
    )
    hybrid_history = next(
        item
        for item in packets("glhs_hybrid")
        if item["target"]["code"] == "test-history"
    )
    assert {e["status"] for e in lww_history["context"]["events"]} == {
        "active",
        "final",
    }
    assert {e["status"] for e in hybrid_history["context"]["events"]} >= {
        "revoked",
        "final",
    }
    validate_run(tmp_path)


def test_request_budget_is_total_and_resume_does_not_duplicate_errors(tmp_path) -> None:
    limits = RunLimits(max_subjects=2, max_cases=2, max_requests=5, checkpoint_every=1)
    bundles = [(_bundle("patient-a", "a"), "R4"), (_bundle("patient-b", "b"), "R4")]
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    first_transport = ExactModelFakeTransport()

    first = run_local_e2e(
        bundles=bundles,
        output_dir=tmp_path,
        clients=_clients(first_transport, limits),
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        limits=limits,
    )
    assert first["run_status"] == "BOUNDED_INCOMPLETE"
    assert first["request_count"] == 5
    assert len(first_transport.calls) == 5

    resumed_transport = ExactModelFakeTransport()
    second = run_local_e2e(
        bundles=bundles,
        output_dir=tmp_path,
        clients=_clients(resumed_transport, limits),
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        limits=limits,
    )
    assert second["request_count"] == 5
    assert second["completed_cell_count"] == 5
    assert resumed_transport.calls == []
    assert json.loads((tmp_path / "error_ledger.json").read_text()) == []
    validate_run(tmp_path)


def test_total_request_budget_includes_generation_and_review(tmp_path) -> None:
    limits = RunLimits(max_subjects=2, max_cases=2, max_requests=10, checkpoint_every=1)
    bundles = [(_bundle("patient-a", "a"), "R4"), (_bundle("patient-b", "b"), "R4")]
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    transport = DeterministicFakeTransport()
    clients = _clients(transport, limits)

    first = run_local_e2e(
        bundles=bundles,
        output_dir=tmp_path,
        clients=clients,
        construction_clients=(clients[GENERATOR_MODEL], clients[REVIEWER_MODEL]),
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        limits=limits,
    )
    assert first["request_count"] == 10
    assert first["generation_request_count"] == 4
    assert first["solver_request_count"] == 6
    assert first["generation_case_count"] == 2
    assert first["run_status"] == "BOUNDED_INCOMPLETE"
    assert transport.call_count == 10
    validate_run(tmp_path)

    resumed_transport = DeterministicFakeTransport()
    resumed_clients = _clients(resumed_transport, limits)
    resumed = run_local_e2e(
        bundles=bundles,
        output_dir=tmp_path,
        clients=resumed_clients,
        construction_clients=(
            resumed_clients[GENERATOR_MODEL],
            resumed_clients[REVIEWER_MODEL],
        ),
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        limits=limits,
    )
    assert resumed == first
    assert resumed_transport.call_count == 0
    validate_run(tmp_path)


def test_provider_failures_remain_in_structured_error_ledger(tmp_path) -> None:
    limits = RunLimits(
        max_subjects=1,
        max_cases=1,
        max_requests=18,
        checkpoint_every=2,
        max_retries=1,
        retry_backoff_seconds=0,
    )
    transport = FailingTransport()
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    manifest = run_local_e2e(
        bundles=[(_bundle("patient-a", "a"), "R4")],
        output_dir=tmp_path,
        clients=_clients(transport, limits),
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        limits=limits,
    )
    errors = json.loads((tmp_path / "error_ledger.json").read_text())
    assert manifest["run_status"] == "COMPLETE"
    assert manifest["solver_request_count"] == 18
    assert len(errors) == 18
    assert transport.calls == 36
    assert all(
        item["error"] == "ProviderError"
        and item["reported_model_id"] is None
        and item["attempts"] == 2
        and item["usage"] == {}
        for item in errors
    )
    validate_run(tmp_path)


def test_single_primary_model_grid_uses_subject_level_analysis(tmp_path) -> None:
    limits = RunLimits(max_subjects=1, max_cases=1, max_requests=2)
    transport = ExactModelFakeTransport()
    client = EvaluationClient(
        base_url="https://router.invalid/v1",
        api_key="fixture-secret-not-real",
        transport=transport,
        limits=limits,
    )
    conditions = ("full_authorized_history", "glhs_hybrid_thss_strict")
    manifest = run_local_e2e(
        bundles=[(_bundle("primary-subject", "primary"), "R4")],
        output_dir=tmp_path,
        clients={REVIEWER_MODEL: client},
        valid_cutoff=datetime(2026, 2, 1, tzinfo=UTC),
        known_cutoff=datetime(2026, 2, 1, tzinfo=UTC),
        limits=limits,
        conditions=conditions,
        primary_model=REVIEWER_MODEL,
    )
    assert manifest["expected_cell_count"] == 2
    assert manifest["conditions"] == list(conditions)
    assert manifest["primary_model"] == REVIEWER_MODEL
    statistics = json.loads(
        (tmp_path / "statistical_results.json").read_text(encoding="utf-8")
    )
    assert statistics["schema_version"] == "commitloop-primary-statistics.v1"
    assert statistics["subject_count"] == 1
    assert statistics["wins"] == 0
    assert statistics["losses"] == 0
    assert statistics["ties"] == 1
    metrics = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["generation"]["mode"] == "deterministic_construction_only"
    rows = (tmp_path / "per_case_metrics.csv").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 3

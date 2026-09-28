"""Comprehensive test suite for Phase 13 (E13: External / Independent Validation).

Validates task packets, protocol specifications, statistical calculations (Cohen's kappa,
Krippendorff's alpha, Wilson CIs), execution pipeline, analysis, sealing, offline reproduction,
and Red Team (E) guardrails.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from evaluation.external_validation.analyze import (
    analyze_e13_results,
    compute_cohen_kappa,
    compute_krippendorff_alpha,
    generate_summary_markdown,
    wilson_ci,
)
from evaluation.external_validation.run_e13_external import run_e13, run_task_evaluation
from evaluation.external_validation.seal import seal_e13
from reproduce_e13 import reproduce_and_verify


def test_wilson_ci_computation() -> None:
    """Test Wilson score 95% confidence interval calculations."""
    # Test boundary k=0, n=100
    p, low, high = wilson_ci(0, 100)
    assert p == 0.0
    assert low == 0.0
    assert 0.0 < high < 0.05

    # Test boundary k=100, n=100
    p, low, high = wilson_ci(100, 100)
    assert p == 1.0
    assert 0.95 < low < 1.0
    assert high == 1.0

    # Test typical k=95, n=100
    p, low, high = wilson_ci(95, 100)
    assert p == 0.95
    assert 0.88 < low < 0.92
    assert 0.97 < high <= 1.0

    # Test n=0 invalid input
    p, low, high = wilson_ci(0, 0)
    assert p == 0.0 and low == 0.0 and high == 0.0


def test_cohen_kappa_computation() -> None:
    """Test Cohen's kappa for inter-rater agreement."""
    # Perfect agreement
    perfect_pairs = [("ACCURATE", "ACCURATE")] * 20
    kappa = compute_cohen_kappa(perfect_pairs)
    assert kappa == 1.0

    # Complete disagreement
    disagree_pairs = [("ACCURATE", "INACCURATE")] * 10 + [("INACCURATE", "ACCURATE")] * 10
    kappa_disagree = compute_cohen_kappa(disagree_pairs)
    assert kappa_disagree is not None and kappa_disagree <= 0.0

    # Partial agreement
    mixed_pairs = [("ACCURATE", "ACCURATE")] * 15 + [("ACCURATE", "INACCURATE")] * 5
    kappa_mixed = compute_cohen_kappa(mixed_pairs)
    assert kappa_mixed is not None

    # Empty pairs
    assert compute_cohen_kappa([]) is None


def test_krippendorff_alpha_computation() -> None:
    """Test Krippendorff's alpha for inter-rater reliability."""
    perfect_pairs = [("ACCURATE", "ACCURATE")] * 20
    alpha = compute_krippendorff_alpha(perfect_pairs)
    assert alpha == 1.0

    empty_pairs: list[tuple[str, str]] = []
    assert compute_krippendorff_alpha(empty_pairs) is None


def test_e13_tasks_v2_schema() -> None:
    """Test schema and corpora coverage in protocols/external_validation/eicu_mimic_tasks_v2.json."""
    tasks_path = Path("protocols/external_validation/eicu_mimic_tasks_v2.json")
    assert tasks_path.is_file()

    data = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert data.get("schema_version") == "glhs-external-validation-tasks-v2"
    
    corpora = set(data.get("corpora_represented", []))
    expected_corpora = {"eicu", "synthea", "mimic_on_fhir", "diabetes_130"}
    assert corpora == expected_corpora

    tasks = data.get("tasks", [])
    assert len(tasks) >= 8

    for t in tasks:
        assert "task_id" in t
        assert "corpus" in t
        assert t["corpus"] in expected_corpora
        assert "expected_ground_truth" in t
        assert "dual_annotator_packets" in t
        packets = t["dual_annotator_packets"]
        assert "annotator_1" in packets
        assert "annotator_2" in packets
        assert "adjudicator" in packets


def test_e13_protocol_json_schema() -> None:
    """Test schema and invariants in protocols/E13_external_validation/protocol.json."""
    proto_path = Path("protocols/E13_external_validation/protocol.json")
    assert proto_path.is_file()

    doc = json.loads(proto_path.read_text(encoding="utf-8"))
    assert doc.get("schema_version") == "glhs-e13-external-validation-protocol-v1"
    assert doc.get("status") == "FROZEN"
    assert "corpora" in doc
    assert set(doc["corpora"].keys()) == {"eicu", "synthea", "mimic_on_fhir", "diabetes_130"}
    assert doc.get("red_team_constraints", {}).get("disallow_model_as_human") is True


def test_run_e13_execution(tmp_path: Path) -> None:
    """Test run_e13_external.py execution pipeline."""
    tasks_path = Path("protocols/external_validation/eicu_mimic_tasks_v2.json")
    protocol_path = Path("protocols/E13_external_validation/protocol.json")
    out_dir = tmp_path / "e13_run"

    meta = run_e13(
        tasks_path=tasks_path,
        protocol_path=protocol_path,
        output_dir=out_dir,
        mode="synthetic",
    )

    assert meta["total_tasks"] >= 8
    assert (out_dir / "raw" / "results.jsonl").is_file()
    assert (out_dir / "raw" / "execution_metadata.json").is_file()

    results_lines = (out_dir / "raw" / "results.jsonl").read_text().splitlines()
    assert len(results_lines) == meta["total_tasks"]


def test_red_team_guardrails(tmp_path: Path) -> None:
    """Test Red Team (E) guardrails preventing model QA from being claimed as human adjudication."""
    tasks_path = Path("protocols/external_validation/eicu_mimic_tasks_v2.json")
    protocol_path = Path("protocols/E13_external_validation/protocol.json")

    # 1. Test Synthetic mode
    synth_dir = tmp_path / "synthetic_run"
    run_e13(tasks_path=tasks_path, protocol_path=protocol_path, output_dir=synth_dir, mode="synthetic")
    synth_summary = analyze_e13_results(synth_dir / "raw" / "results.jsonl", protocol_path)

    assert synth_summary["adjudication_type"] == "SYNTHETIC_MODEL_ADJUDICATION"
    assert synth_summary["human_adjudication_status"] == "NOT_RUN_HUMAN_UNAVAILABLE"
    assert synth_summary["independent_human_claim_eligible"] is False
    assert synth_summary["red_team_guardrails"]["disallow_model_as_human_enforced"] is True

    # 2. Test NOT_RUN mode
    notrun_dir = tmp_path / "notrun_run"
    run_e13(tasks_path=tasks_path, protocol_path=protocol_path, output_dir=notrun_dir, mode="not_run")
    notrun_summary = analyze_e13_results(notrun_dir / "raw" / "results.jsonl", protocol_path)

    assert notrun_summary["adjudication_type"] == "NOT_RUN"
    assert notrun_summary["human_adjudication_status"] == "NOT_RUN_HUMAN_UNAVAILABLE"
    assert notrun_summary["independent_human_claim_eligible"] is False

    # 3. Test Verified Human mode
    human_dir = tmp_path / "human_run"
    run_e13(tasks_path=tasks_path, protocol_path=protocol_path, output_dir=human_dir, mode="human")
    human_summary = analyze_e13_results(human_dir / "raw" / "results.jsonl", protocol_path)

    assert human_summary["adjudication_type"] == "INDEPENDENT_HUMAN_ADJUDICATION"
    assert human_summary["human_adjudication_status"] == "COMPLETED"
    assert human_summary["independent_human_claim_eligible"] is True


def test_seal_e13_workflow(tmp_path: Path) -> None:
    """Test sealing workflow and output artifacts."""
    tasks_path = Path("protocols/external_validation/eicu_mimic_tasks_v2.json")
    protocol_path = Path("protocols/E13_external_validation/protocol.json")
    artifact_dir = tmp_path / "sealed_e13"

    seal_doc = seal_e13(
        artifact_dir=artifact_dir,
        protocol_path=protocol_path,
        tasks_path=tasks_path,
        mode="synthetic",
        force_run=True,
    )

    assert seal_doc["status"] == "SEALED"
    assert seal_doc["schema_version"] == "glhs-e13-external-validation-seal-v1"
    assert (artifact_dir / "checksums.sha256").is_file()
    assert (artifact_dir / "validation.json").is_file()
    assert (artifact_dir / "seal.json").is_file()
    assert (artifact_dir / "derived" / "summary.json").is_file()
    assert (artifact_dir / "derived" / "summary.md").is_file()


def test_reproduce_e13_offline() -> None:
    """Test reproduce_e13.py offline validator on frozen protocol directory."""
    report = reproduce_and_verify(
        artifact_dir=Path("protocols/E13_external_validation"),
        protocol_path=Path("protocols/E13_external_validation/protocol.json"),
    )

    assert report["status"] == "REPRODUCED_AND_VERIFIED"
    assert report["network_disabled"] is True
    assert report["seal_verified"] is True
    assert report["total_tasks"] >= 8


def test_reproduce_e13_r3_evidence_bundle() -> None:
    """Test reproduce_e13.py offline validator on R3 evidence directory."""
    report = reproduce_and_verify(
        artifact_dir=Path("research/glhs_journal/q3_r3/evidence/E13_external_validation"),
        protocol_path=Path("research/glhs_journal/q3_r3/protocols/E13_external_validation/protocol.json"),
    )

    assert report["status"] == "REPRODUCED_AND_VERIFIED"
    assert report["network_disabled"] is True
    assert report["seal_verified"] is True
    assert report["total_tasks"] >= 8

"""Tests for the GLHS malformed-output taxonomy parser.

These tests use tiny synthetic run directories and never touch the sealed
artifacts. They prove the failure-type classification, the paired Strict-vs
-full-history contingency, and the read-only checksum verification.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from research.glhs_journal.malformed_audit_v1.taxonomy_parser import (
    classify_failure_type,
    parse_run,
    render_audit_markdown,
    verify_checksums,
)


def _write(tmp: Path, name: str, content: str) -> None:
    (tmp / name).write_text(content, encoding="utf-8")


def _make_run(tmp: Path, *, errors: list[dict[str, object]]) -> Path:
    run = tmp / "run"
    run.mkdir(parents=True)
    manifest = {
        "schema_version": "commitloop-run.v1",
        "subject_count": 2,
        "case_count": 2,
        "models": ["model-a", "model-b"],
        "conditions": [
            "full_authorized_history",
            "glhs_hybrid_thss_strict",
        ],
        "expected_cell_count": 8,
    }
    _write(run, "run_manifest.json", json.dumps(manifest))
    _write(
        run,
        "metrics.json",
        json.dumps({"output_count": 8 - len(errors), "missing_output_count": 0}),
    )
    _write(run, "error_ledger.json", json.dumps(errors))
    _write(run, "error_ledger.csv", "key,case_id,condition,requested_model_id,reported_model_id,error,error_detail,attempts\n")
    _write(run, "partition_manifest.json", json.dumps({"subject-1": "validation"}))
    _write(run, "perturbation_manifest.jsonl", "")
    _write(run, "per_case_metrics.csv", "case_id,model,condition\n")
    # checksums for every file written (must not be checked against missing files)
    checksum_lines = []
    for file_path in sorted(run.iterdir()):
        if file_path.is_file() and file_path.name != "checksums.sha256":
            digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            checksum_lines.append(f"{digest}  {file_path.name}")
    _write(run, "checksums.sha256", "\n".join(checksum_lines) + "\n")
    return run


def test_classify_failure_type_mappings() -> None:
    assert classify_failure_type("SolverFormatError", "provider_json_decode_error") == "parse"
    assert classify_failure_type("JSONDecodeError") == "parse"
    assert classify_failure_type("SolverFormatError", "prediction_schema_invalid") == "schema"
    assert classify_failure_type("ValueError", "prediction_schema_invalid") == "schema"
    assert classify_failure_type("ProviderError", "malformed_provider_response") == "format"
    assert classify_failure_type("ProviderError", "empty_provider_content") == "format"
    assert classify_failure_type("ProviderError", "model_substitution_detected:foo") == "format"
    assert classify_failure_type("ProviderError", "provider_http_terminal_500") == "other"
    assert classify_failure_type("TimeoutError") == "other"


def test_checksum_verification_detects_mismatch(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    _write(run, "a.json", "{}")
    _write(run, "checksums.sha256", "0" * 64 + "  a.json\n")
    result = verify_checksums(run)
    assert result["verified"] is False
    assert result["files"][0]["status"] == "MISMATCH"


def test_parse_run_with_malformed_outputs(tmp_path: Path) -> None:
    errors = [
        {
            "key": "m:a:full:c1",
            "case_id": "c1",
            "condition": "full_authorized_history",
            "reported_model_id": "model-a",
            "error": "SolverFormatError",
            "error_detail": "provider_json_decode_error",
        },
        {
            "key": "m:a:strict:c1",
            "case_id": "c1",
            "condition": "glhs_hybrid_thss_strict",
            "reported_model_id": "model-a",
            "error": "SolverFormatError",
            "error_detail": "prediction_schema_invalid",
        },
        {
            "key": "m:a:strict:c2",
            "case_id": "c2",
            "condition": "glhs_hybrid_thss_strict",
            "reported_model_id": "model-a",
            "error": "ProviderError",
            "error_detail": "malformed_provider_response",
        },
    ]
    audit = parse_run(_make_run(tmp_path, errors=errors))
    assert audit["total_malformed"] == 3
    assert audit["expected_total_cells"] == 8
    assert audit["failure_type_distribution"] == {
        "parse": 1,
        "schema": 1,
        "format": 1,
        "other": 0,
    }
    assert audit["by_condition"]["full_authorized_history"]["malformed"] == 1
    assert audit["by_condition"]["glhs_hybrid_thss_strict"]["malformed"] == 2
    assert audit["paired_contingency"]["both"] == 1  # c1 malformed in both
    assert audit["paired_contingency"]["strict_only"] == 1  # c2
    assert audit["primary_null_result_unchanged"] is True


def test_parse_run_with_no_malformed_outputs(tmp_path: Path) -> None:
    audit = parse_run(_make_run(tmp_path, errors=[]))
    assert audit["total_malformed"] == 0
    assert audit["paired_contingency"] == {}
    assert audit["failure_type_distribution"] == {
        "parse": 0,
        "schema": 0,
        "format": 0,
        "other": 0,
    }


def test_audit_derives_task_stratum_and_subject_neither_from_immutable_run() -> None:
    audit = parse_run(Path("artifacts/commitloop/local-phase-a-v6"))
    assert audit["checksum_verification"]["verified"] is True
    assert audit["total_malformed"] == 0
    assert audit["expected_total_cells"] == 360
    assert audit["by_task"]["reconcile_future_oriented_commitment"]["denominator"] == 360
    assert audit["by_stratum"]["validation"]["denominator"] == 360
    assert audit["paired_contingency"] == {
        "both": 0,
        "strict_only": 0,
        "full_only": 0,
        "neither": 2,
    }
    assert audit["primary_reference_subject_count"] == 384
    assert audit["primary_null_result_unchanged"] is True


def test_render_audit_markdown_smoke(tmp_path: Path) -> None:
    audit = parse_run(_make_run(tmp_path, errors=[]))
    markdown = render_audit_markdown(audit)
    assert "OFFLINE / DESCRIPTIVE" in markdown
    assert "checksums.sha256" in markdown
    assert "GLHS-M03" in markdown

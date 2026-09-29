"""Comprehensive test suite for Phase 11 (E11) and Phase 12 (E12) CommitLoop v8.

Tests two-model replication cohort execution, prospective 12-class error taxonomy,
sensitivity recovery arms R0..R3, paired Schuirmann TOST equivalence, 95% bootstrap CIs,
freeze/seal validation, and offline reproduction.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
import pytest

from evaluation.commitloop.analyze_v8 import analyze_v8_run
from evaluation.commitloop.malformed_sensitivity import (
    TAXONOMY_12_CLASSES,
    classify_error_12_class,
    evaluate_sensitivity_arms,
    normalize_error_class,
    repair_local_json_r1,
    validate_prediction_schema,
)
from evaluation.commitloop.seal_v8 import seal_v8_protocol
from evaluation.commitloop.v8_runner import (
    audit_provider_run_ledger,
    verify_v8_freeze_contract,
    verify_v8_provider_probe,
)


def test_12_class_error_taxonomy_classification() -> None:
    """Verify classification across all 12 prospective error classes."""
    assert classify_error_12_class("JSONDecodeError", "invalid json body", "{bad: json") == "invalid_json"
    assert classify_error_12_class("SchemaError", "missing_key", '{"lifecycle_state": "OPEN"}') == "schema_mismatch"
    assert classify_error_12_class("TruncationError", "max_tokens reached", '{"lifecycle_state": "OPEN"') == "truncation"
    assert classify_error_12_class("RefusalError", "safety policy block", "I cannot fulfill this request") == "refusal"
    assert classify_error_12_class("EmptyResponse", "empty body", "") == "empty_response"
    assert classify_error_12_class("ProviderError", "HTTP 502 Bad Gateway", "502 error") == "provider_error"
    assert classify_error_12_class("ModelError", "model_substitution_detected", "Wrong model") == "wrong_model"
    assert classify_error_12_class("TimeoutError", "timed out waiting", "Timeout") == "timeout"
    assert classify_error_12_class("FormatError", "markdown fence violation", "Here is JSON:\n```json\n{}```") == "content_format_violation"
    assert classify_error_12_class("SemanticError", "invalid enum state", '{"lifecycle_state": "INVALID", "evidence_state": "CLEAR", "timeliness_state": "BEFORE_DUE"}') == "semantic_failure"
    assert classify_error_12_class("RateLimitError", "HTTP 429 quota_exceeded", "429") == "rate_limit"
    assert classify_error_12_class("UnknownError", "unclassified issue", "random string") == "unclassified"
    assert normalize_error_class("rate_limit_exhaustion") == "rate_limit"
    assert normalize_error_class("unclassified_error") == "unclassified"


def test_r1_local_deterministic_repair() -> None:
    """Verify Arm R1 local deterministic JSON repair without network calls."""
    valid_json = '{"lifecycle_state": "SATISFIED", "evidence_state": "CLEAR", "timeliness_state": "BEFORE_DUE"}'

    # Strip markdown fence
    fenced = f"```json\n{valid_json}\n```"
    repaired = repair_local_json_r1(fenced)
    assert repaired is not None
    assert repaired["lifecycle_state"] == "SATISFIED"

    # Trailing comma removal
    trailing_comma = '{"lifecycle_state": "SATISFIED", "evidence_state": "CLEAR", "timeliness_state": "BEFORE_DUE",}'
    repaired_tc = repair_local_json_r1(trailing_comma)
    assert repaired_tc is not None
    assert repaired_tc["timeliness_state"] == "BEFORE_DUE"

    # Invalid JSON that cannot be repaired locally returns None
    assert repair_local_json_r1("totally hopeless text") is None


def test_sensitivity_recovery_arms_evaluation() -> None:
    """Verify evaluation of recovery arms R0, R1, R2, R3."""
    gold_by_case = {
        "case_001": {
            "case_id": "case_001",
            "lifecycle_state": "SATISFIED",
            "evidence_state": "CLEAR",
            "timeliness_state": "BEFORE_DUE",
        }
    }

    # Cell with markdown fence format violation (repairable by R1)
    fenced_raw = '```json\n{"lifecycle_state": "SATISFIED", "evidence_state": "CLEAR", "timeliness_state": "BEFORE_DUE"}\n```'
    cell_outputs = [
        {
            "case_id": "case_001",
            "model": "claude-sonnet-4.6",
            "condition": "glhs_hybrid_thss_strict",
            "key": "claude-sonnet-4.6:glhs_hybrid_thss_strict:case_001",
            "prediction": None,  # R0 fails
            "raw_content": fenced_raw,
            "initial_error": "content_format_violation",
            "retry_prediction": {"lifecycle_state": "SATISFIED", "evidence_state": "CLEAR", "timeliness_state": "BEFORE_DUE"},
            "r3_prediction": {"lifecycle_state": "SATISFIED", "evidence_state": "CLEAR", "timeliness_state": "BEFORE_DUE"},
        }
    ]

    results = evaluate_sensitivity_arms(cell_outputs, gold_by_case)
    arms = results["arms"]

    # R0 fails closed (0 accuracy)
    assert arms["R0_ITT_Primary"]["correct_cells"] == 0
    # R1 repairs locally (1 accuracy)
    assert arms["R1_Local_Repair"]["correct_cells"] == 1
    # R2 succeeds via retry (1 accuracy)
    assert arms["R2_Identical_Retry"]["correct_cells"] == 1
    # R3 succeeds via repair prompt (1 accuracy)
    assert arms["R3_Constrained_Repair"]["correct_cells"] == 1


def test_v8_statistical_analysis_and_tost(tmp_path: Path) -> None:
    """Verify Phase 11 / Phase 12 analysis calculation including Schuirmann TOST."""
    from reproduce_e11 import generate_synthetic_v8_run

    run_dir = tmp_path / "synthetic_run"
    generate_synthetic_v8_run(run_dir, n_subjects=100)

    analysis = analyze_v8_run(run_dir, delta=0.02, alpha=0.05, bootstrap_samples=100)
    assert "e11_two_model_replication" in analysis
    assert "e12_malformed_sensitivity" in analysis

    e11 = analysis["e11_two_model_replication"]
    assert "claude-sonnet-4.6" in e11
    assert "gemini-3.6-flash-high" in e11

    claude_res = e11["claude-sonnet-4.6"]
    assert "tost" in claude_res
    assert "bootstrap_95_ci" in claude_res
    assert len(claude_res["bootstrap_95_ci"]) == 2


def test_v8_tost_zero_variance_and_power_handling() -> None:
    """Verify Schuirmann TOST handling of zero variance and sample size power."""
    from evaluation.commitloop.tost_equivalence import compute_tost_paired

    # Pilot cohort: N=8, zero-variance (all identical differences 0.0)
    strict_pilot = [1.0] * 8
    full_pilot = [1.0] * 8
    res_pilot = compute_tost_paired(strict_pilot, full_pilot, delta=0.02, alpha=0.05)
    assert res_pilot.p_tost is None
    assert res_pilot.is_equivalent is False
    assert res_pilot.se == 0.0
    assert res_pilot.note is not None
    assert "Observed exact agreement on the eight tested cases; population-level +/-2pp equivalence was not established (underpowered sample size)." in res_pilot.note

    # Powered cohort: N=384, zero-variance (all identical differences 0.0)
    strict_powered = [1.0] * 384
    full_powered = [1.0] * 384
    res_powered = compute_tost_paired(strict_powered, full_powered, delta=0.02, alpha=0.05)
    assert res_powered.p_tost == 0.0001
    assert res_powered.is_equivalent is True
    assert res_powered.ci_90 == (0.0, 0.0)
    assert res_powered.ci_95_contained is True


def test_v8_seal_creation_and_checksums(tmp_path: Path) -> None:
    """Verify seal creation and checksum generation."""
    protocol_dir = tmp_path / "protocol"
    protocol_dir.mkdir()
    (protocol_dir / "statistical_analysis_plan.json").write_text("{}")
    (protocol_dir / "power_analysis.json").write_text("{}")

    output_dir = tmp_path / "output"
    repo_root = tmp_path

    # Mock git rev-parse HEAD by initializing git repo or mocking
    import subprocess

    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True)
    (repo_root / "dummy.txt").write_text("dummy")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_root, check=True)

    payload = seal_v8_protocol(protocol_dir, output_dir, repo_root)
    assert (output_dir / "freeze.json").is_file()
    assert (output_dir / "checksums.sha256").is_file()
    assert payload["fallbacks_permitted"] is False


def test_v8_freeze_and_probe_verification(tmp_path: Path) -> None:
    """Verify freeze and probe verification logic."""
    freeze_file = tmp_path / "freeze.json"
    freeze_data = {
        "schema_version": "commitloop-v8-freeze.v1",
        "git_sha": "a" * 40,
    }
    freeze_file.write_text(json.dumps(freeze_data))

    assert verify_v8_freeze_contract(freeze_file, tmp_path)["git_sha"] == "a" * 40

    probe_file = tmp_path / "provider_probe.json"
    probe_data = {
        "fallback": False,
        "requested_models": ["claude-sonnet-4.6", "gemini-3.6-flash-high"],
        "reported_model_mapping": {
            "claude-sonnet-4.6": "claude-sonnet-4-6",
            "gemini-3.6-flash-high": "gemini-3.6-flash-high",
        },
    }
    probe_file.write_text(json.dumps(probe_data))

    verified_probe = verify_v8_provider_probe(probe_file, freeze_data)
    assert verified_probe["fallback"] is False


def test_offline_reproduction_e11_and_e12() -> None:
    """Run offline reproduction scripts reproduce_e11.py and reproduce_e12.py."""
    import reproduce_e11
    import reproduce_e12

    assert reproduce_e11.main() == 0
    assert reproduce_e12.main() == 0


def test_provider_ledger_record_by_record_audit() -> None:
    """Verify record-by-record auditing on prospective provider run ledger."""
    ledger_path = Path("protocols/commitloop/v8-glhs-q2-r2/provider_run_ledger.json")
    assert ledger_path.is_file()

    audit = audit_provider_run_ledger(ledger_path)
    assert audit["total_records"] == 48
    assert audit["audit_passed"] is True
    assert set(audit["models_tested"]) == {"claude-sonnet-4.6", "gemini-3.6-flash-high", "gemini-3.8-flash-tiered"}

    # Must accurately report 9 fallbacks (unallowed model substitutions), NOT 0
    assert audit["fallbacks_observed"] == 9
    assert audit["fallbacks_observed"] != 0

    # Model drift / unallowed fallback breakdown
    breakdown = audit["model_drift_breakdown"]
    assert breakdown["gemini-3.8-flash-tiered -> gemini-3.7-flash-tiered"] == 4
    assert breakdown["gemini-3.8-flash-tiered -> gemini-3.6-flash-tiered"] == 5

    # Documented alias normalizations (not silent zero, tracked separately)
    alias_norm = audit["alias_normalization"]
    assert alias_norm["claude-sonnet-4.6 -> claude-sonnet-4-6"] == 16
    assert alias_norm["gemini-3.8-flash-tiered -> antigravity/gemini-3.8-flash-tiered"] == 7

    # Error taxonomy breakdown
    assert audit["error_counts"] == {"invalid_json": 2}

    # Token usage positive integers
    assert audit["token_usage"]["prompt_tokens"] > 0
    assert audit["token_usage"]["completion_tokens"] > 0
    assert audit["token_usage"]["total_tokens"] > 0


def test_provider_ledger_audit_detects_malformed_records() -> None:
    """Verify provider ledger auditing rejects empty raw output, bad tokens, or bad taxonomy."""
    valid_record = {
        "requested_model_id": "gemini-3.6-flash-high",
        "reported_model_id": "gemini-3.6-flash-high",
        "raw_output": '{"lifecycle_state": "OPEN"}',
        "parsed_output": {"lifecycle_state": "OPEN"},
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
        "error_classification": None,
    }

    # 1. Empty raw output
    bad_raw = dict(valid_record, raw_output="")
    with pytest.raises(ValueError, match="empty_or_missing_raw_output"):
        audit_provider_run_ledger({"ledger": [bad_raw]})

    # 2. Negative token count
    bad_tokens = dict(valid_record, prompt_tokens=-1)
    with pytest.raises(ValueError, match="invalid_token_count"):
        audit_provider_run_ledger({"ledger": [bad_tokens]})

    # 3. Non-integer token count
    bad_tokens_type = dict(valid_record, total_tokens="many")
    with pytest.raises(ValueError, match="invalid_token_count"):
        audit_provider_run_ledger({"ledger": [bad_tokens_type]})

    # 4. Unknown error classification
    bad_err = dict(valid_record, error_classification="arbitrary_unregistered_error")
    with pytest.raises(ValueError, match="unknown_error_classification"):
        audit_provider_run_ledger({"ledger": [bad_err]})

    # 5. Null parsed output without error classification
    null_parsed = dict(valid_record, parsed_output=None, error_classification=None)
    with pytest.raises(ValueError, match="missing_error_classification_for_null_parsed_output"):
        audit_provider_run_ledger({"ledger": [null_parsed]})


def test_provider_ledger_audit_model_mismatch_increments_fallback() -> None:
    """Verify mismatched model IDs increment fallbacks_observed and never report 0."""
    records = [
        {
            "requested_model_id": "gemini-3.8-flash-tiered",
            "reported_model_id": "gemini-3.7-flash-tiered",
            "raw_output": '{"lifecycle_state": "OPEN"}',
            "parsed_output": {"lifecycle_state": "OPEN"},
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "error_classification": None,
        },
        {
            "requested_model_id": "gemini-3.8-flash-tiered",
            "reported_model_id": "gemini-3.6-flash-tiered",
            "raw_output": '{"lifecycle_state": "OPEN"}',
            "parsed_output": {"lifecycle_state": "OPEN"},
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "error_classification": None,
        },
        {
            "requested_model_id": "gemini-3.6-flash-high",
            "reported_model_id": "gemini-3.6-flash-high",
            "raw_output": '{"lifecycle_state": "OPEN"}',
            "parsed_output": {"lifecycle_state": "OPEN"},
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "error_classification": None,
        },
    ]

    audit = audit_provider_run_ledger({"ledger": records})
    assert audit["fallbacks_observed"] == 2
    assert audit["total_records"] == 3
    assert audit["model_drift_breakdown"] == {
        "gemini-3.8-flash-tiered -> gemini-3.7-flash-tiered": 1,
        "gemini-3.8-flash-tiered -> gemini-3.6-flash-tiered": 1,
    }

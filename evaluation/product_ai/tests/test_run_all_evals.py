"""Unit and integration tests for Product AI Evaluation Runner hardening (EVAL-CLI-01, EVAL-CLI-02, EVAL-LIVE-01, EVAL-ATOMIC-01)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ML_SRC = _REPO_ROOT / "services" / "ml" / "src"
_API_SRC = _REPO_ROOT / "services" / "api" / "src"
for p in (str(_REPO_ROOT), str(_ML_SRC), str(_API_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from evaluation.product_ai.common import (
    CaseEvaluationResult,
    EvaluationTarget,
    MockEvaluationAdapter,
    TaskReport,
    ThresholdCheck,
    save_report_atomic,
    write_json_atomic,
)
from evaluation.product_ai.run_all_evals import (
    BENCHMARK_SUITES,
    EVALUATION_TARGETS,
    run_all_benchmarks,
    validate_cli_identifiers,
)

# ==============================================================================
# EVAL-CLI-01 Tests: Fail-closed CLI identifier validation
# ==============================================================================


def test_validate_cli_identifiers_rejects_unknown_model(capsys: pytest.CaptureFixture[str]) -> None:
    """Unknown model must print exact invalid identifier and exit code 2."""
    with pytest.raises(SystemExit) as exc_info:
        validate_cli_identifiers(models=["definitely-not-a-model"])
    assert exc_info.value.code == 2

    stderr = capsys.readouterr().err
    assert "definitely-not-a-model" in stderr
    assert "CLI validation error: unknown model identifiers" in stderr


def test_validate_cli_identifiers_rejects_unknown_suite(capsys: pytest.CaptureFixture[str]) -> None:
    """Unknown suite must print exact invalid identifier and exit code 2."""
    with pytest.raises(SystemExit) as exc_info:
        validate_cli_identifiers(suites=["not_a_valid_suite"])
    assert exc_info.value.code == 2

    stderr = capsys.readouterr().err
    assert "not_a_valid_suite" in stderr
    assert "CLI validation error: unknown suite identifiers" in stderr


def test_validate_cli_identifiers_rejects_explicitly_empty_models(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Explicitly empty model selection (models=[]) must fail closed with exit code 2, not default to all."""
    with pytest.raises(SystemExit) as exc_info:
        validate_cli_identifiers(models=[])
    assert exc_info.value.code == 2

    stderr = capsys.readouterr().err
    assert "explicit --models selection is empty" in stderr


def test_validate_cli_identifiers_rejects_explicitly_empty_suites(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Explicitly empty suites selection (suites=[]) must fail closed with exit code 2, not default to all."""
    with pytest.raises(SystemExit) as exc_info:
        validate_cli_identifiers(suites=[])
    assert exc_info.value.code == 2

    stderr = capsys.readouterr().err
    assert "explicit --suites selection is empty" in stderr


def test_validate_cli_identifiers_accepts_valid_selection() -> None:
    """Valid models and suites should resolve to expected targets and suite names."""
    targets, suites = validate_cli_identifiers(
        models=["gemini-3.7-flash-tiered", "deepseek-v4-pro"],
        suites=["grounded_answer", "medication_safety"],
    )
    assert len(targets) == 2
    assert [t.model for t in targets] == ["gemini-3.7-flash-tiered", "deepseek-v4-pro"]
    assert suites == ["grounded_answer", "medication_safety"]


def test_validate_cli_identifiers_defaults_when_none() -> None:
    """When models=None and suites=None, resolve to all registered targets and suites."""
    targets, suites = validate_cli_identifiers(models=None, suites=None)
    assert len(targets) == len(EVALUATION_TARGETS)
    assert set(suites) == set(BENCHMARK_SUITES.keys())


# ==============================================================================
# EVAL-CLI-02 Tests: EvaluationTarget schema and manifest alignment
# ==============================================================================


def test_evaluation_target_schema_and_properties() -> None:
    target = EvaluationTarget(
        provider="unofficial_gemini_gateway",
        model="gemini-3.7-flash-tiered",
        role="candidate_quality_multimodal",
        target_type="candidate",
        execution_mode="mock",
        endpoint_class="unofficial_gemini_gateway",
        revision="v2",
    )
    assert target.provider == "unofficial_gemini_gateway"
    assert target.model == "gemini-3.7-flash-tiered"
    assert target.role == "candidate_quality_multimodal"
    assert target.target_type == "candidate"
    assert target.execution_mode == "mock"
    assert target.endpoint_class == "unofficial_gemini_gateway"
    assert target.revision == "v2"

    # Test backward-compatible dict access
    assert target["model"] == "gemini-3.7-flash-tiered"
    assert target["provider"] == "unofficial_gemini_gateway"

    d = target.to_dict()
    assert d["model"] == "gemini-3.7-flash-tiered"
    assert d["target_type"] == "candidate"


def test_evaluation_targets_include_deepseek_baseline_and_candidates() -> None:
    """Verify that default EVALUATION_TARGETS includes baseline and candidate models."""
    model_names = [t.model for t in EVALUATION_TARGETS]
    assert "deepseek-v4-pro" in model_names
    assert "gemini-3.7-flash-tiered" in model_names
    assert "gemini-3.6-flash-high" in model_names
    assert "claude-sonnet-4-6" in model_names

    baseline_targets = [t for t in EVALUATION_TARGETS if t.target_type == "baseline"]
    candidate_targets = [t for t in EVALUATION_TARGETS if t.target_type == "candidate"]

    assert len(baseline_targets) == 1
    assert baseline_targets[0].model == "deepseek-v4-pro"
    assert baseline_targets[0].role == "baseline_reasoning"
    assert len(candidate_targets) == 3


def test_evaluation_targets_snapshot_equality() -> None:
    """Snapshot test for EVALUATION_TARGETS structure and identities."""
    expected_snapshot = [
        {
            "provider": "unofficial_gemini_gateway",
            "model": "gemini-3.7-flash-tiered",
            "role": "candidate_quality_multimodal",
            "target_type": "candidate",
            "execution_mode": "mock",
            "endpoint_class": "unofficial_gemini_gateway",
            "revision": "v1",
        },
        {
            "provider": "unofficial_gemini_gateway",
            "model": "gemini-3.6-flash-high",
            "role": "candidate_fast_multimodal",
            "target_type": "candidate",
            "execution_mode": "mock",
            "endpoint_class": "unofficial_gemini_gateway",
            "revision": "v1",
        },
        {
            "provider": "unofficial_gemini_gateway",
            "model": "claude-sonnet-4-6",
            "role": "candidate_quality_reasoning",
            "target_type": "candidate",
            "execution_mode": "mock",
            "endpoint_class": "unofficial_gemini_gateway",
            "revision": "v1",
        },
        {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "role": "baseline_reasoning",
            "target_type": "baseline",
            "execution_mode": "mock",
            "endpoint_class": "deepseek",
            "revision": "v1",
        },
    ]
    actual = [t.to_dict() for t in EVALUATION_TARGETS]
    assert actual == expected_snapshot


# ==============================================================================
# EVAL-LIVE-01 Tests: Refuse live=True without credentials & mode provenance
# ==============================================================================


def test_run_all_benchmarks_refuses_live_without_deepseek_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Refuse live=True when deepseek target has no DEEPSEEK_API_KEY."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("ROUTER_API_KEY", "router-test-key")

    deepseek_target = [t for t in EVALUATION_TARGETS if t.provider == "deepseek"]

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY is not set or empty"):
        run_all_benchmarks(
            output_dir=tmp_path,
            targets=deepseek_target,
            live=True,
        )


def test_run_all_benchmarks_refuses_live_without_router_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Refuse live=True when gemini gateway target has no router API key."""
    monkeypatch.delenv("ROUTER_API_KEY", raising=False)
    monkeypatch.delenv("CLARA_UNOFFICIAL_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")

    gemini_target = [t for t in EVALUATION_TARGETS if t.provider == "unofficial_gemini_gateway"][:1]

    with pytest.raises(RuntimeError, match="ROUTER_API_KEY / CLARA_UNOFFICIAL_GEMINI_API_KEY"):
        run_all_benchmarks(
            output_dir=tmp_path,
            targets=gemini_target,
            live=True,
            router_api_key="",
        )


def test_mock_adapter_records_mock_execution_mode() -> None:
    """A mock adapter can only produce execution_mode='mock'."""
    adapter = MockEvaluationAdapter(provider_alias="deepseek", model_name="deepseek-v4-pro")
    assert adapter.execution_mode == "mock"
    assert adapter.endpoint_class == "offline_mock"


def test_case_result_and_task_report_provenance_fields() -> None:
    """Every record must carry execution_mode, endpoint_class, and response_provenance."""
    case_res = CaseEvaluationResult(
        case_id="test_case_1",
        passed=True,
        score=1.0,
        metrics={"groundedness": 1.0},
        output="safe response",
        expected={"key_claims": ["safe"]},
        execution_mode="mock",
        endpoint_class="offline_mock",
        response_provenance={"provider": "deepseek", "digest": "sha256:abc"},
    )
    d = case_res.to_dict()
    assert d["execution_mode"] == "mock"
    assert d["endpoint_class"] == "offline_mock"
    assert d["response_provenance"] == {"provider": "deepseek", "digest": "sha256:abc"}

    check = ThresholdCheck(
        metric_name="groundedness",
        threshold_value=0.95,
        actual_value=1.0,
        operator=">=",
        passed=True,
    )
    report = TaskReport(
        task_id="grounded_answer",
        task_name="Grounded Answer",
        version="1.0.0",
        provider="deepseek",
        model="deepseek-v4-pro",
        route_class="quality_multimodal",
        total_cases=1,
        passed_cases=1,
        failed_cases=0,
        pass_rate=1.0,
        metrics={"groundedness": 1.0},
        threshold_checks=(check,),
        overall_passed=True,
        latency_p50_ms=10.0,
        latency_p95_ms=10.0,
        case_results=(case_res,),
        execution_mode="mock",
        endpoint_class="offline_mock",
        response_provenance={"provider": "deepseek"},
    )
    rd = report.to_dict()
    assert rd["execution_mode"] == "mock"
    assert rd["endpoint_class"] == "offline_mock"
    assert rd["response_provenance"] == {"provider": "deepseek"}


# ==============================================================================
# EVAL-ATOMIC-01 Tests: Atomic writing of evaluation reports
# ==============================================================================


def test_write_json_atomic_creates_valid_file(tmp_path: Path) -> None:
    target_file = tmp_path / "subdir" / "test_report.json"
    data = {"task_id": "test", "passed": True, "score": 1.0}

    write_json_atomic(data, target_file)

    assert target_file.exists()
    assert json.loads(target_file.read_text(encoding="utf-8")) == data


def test_save_report_atomic_saves_report_atomically(tmp_path: Path) -> None:
    target_file = tmp_path / "summary.json"
    data = {"all_passed": True, "timestamp": "2026-08-23T00:00:00Z"}

    save_report_atomic(data, target_file)

    assert target_file.exists()
    loaded = json.loads(target_file.read_text(encoding="utf-8"))
    assert loaded["all_passed"] is True

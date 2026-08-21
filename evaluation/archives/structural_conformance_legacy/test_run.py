"""Contracts for the frozen, non-clinical GLHS Q2 evaluator."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import tarfile
from xml.etree import ElementTree

import pytest
from evaluation.glhs_q2.integrate_model_arm import integrate
from evaluation.glhs_q2.prepare_synthea_archive import prepare as prepare_synthea
from evaluation.glhs_q2.run import SYSTEMS, THSS_PROFILES, _case, run, write
from evaluation.glhs_q2.run_external_stream import run_stream
from evaluation.glhs_q2.run_model_arm import PROMPT_VERSION, SEEDS
from evaluation.glhs_q2.validate_artifact import validate
from scripts.evaluation.render_glhs_q2_full_synthea_report import (
    render as render_full_synthea_report,
)


def test_exact_q2_cohort_shape_and_holdout_partition() -> None:
    result = run(20260808, 400)

    cases = result["cases"]
    assert result["schema_version"] == "glhs-q2-structural-v1"
    assert result["protocol"]["subjects"] == 200
    assert len(cases) == 400
    assert len({row["subject_id"] for row in cases}) == 200
    assert sum(row["experiment"] == "direct_conformance" for row in cases) == 100
    assert sum(row["experiment"] == "compositional_stress" for row in cases) == 240
    assert sum(row["experiment"] == "ambiguity_escalation" for row in cases) == 60
    assert sum(row["partition"] == "sealed_holdout" for row in cases) == 60
    assert tuple(result["metrics"]) == SYSTEMS
    assert result["score_release"]["final_score_released"] is False


def test_q2_model_ledger_is_exact_120_cases_three_predeclared_seeds() -> None:
    result = run(20260808, 400)

    rows = result["per_run"]
    assert [row["seed"] for row in rows] == [20260808, 20260809, 20260810]
    assert all(row["cases"] == 120 for row in rows)
    assert all(row["status"] == "not_run_no_frozen_model_provider_config" for row in rows)
    assert len({row["case_ids_sha256"] for row in rows}) == 1


def test_writer_emits_pre_execution_contracts_and_all_required_tables(tmp_path) -> None:
    cases = [
        {
            "case_id": _case(index).case_id,
            "subject_id": _case(index).subject_id,
            "episode_count": _case(index).episode_count,
            "scenario": _case(index).scenario,
            "expected_state": _case(index).expected_state,
            "expected_error": _case(index).expected_error,
            "critical_fact_count": _case(index).critical_fact_count,
            "nonessential_authorized_fact_count": _case(index).nonessential_authorized_fact_count,
            "authorized": _case(index).authorized,
            "experiment": _case(index).experiment,
            "partition": _case(index).partition,
        }
        for index in range(1, 401)
    ]
    from evaluation.glhs_q2.run import _write_frozen_inputs

    frozen = _write_frozen_inputs(tmp_path, cases)
    result = run(20260808, 400, frozen_input_sha256=frozen)
    write(result, tmp_path, frozen_input_sha256=frozen)

    expected = {
        "summary.json",
        "environment.json",
        "cases.csv",
        "outcomes.csv",
        "external_cases.csv",
        "external_outcomes.csv",
        "external_stratified_metrics.csv",
        "external_baseline_comparison.csv",
        "operational_metrics.csv",
        "cost_of_success.csv",
        "per_run.csv",
        "conformance.csv",
        "baseline_comparison.csv",
        "ablation.csv",
        "thss_ablation.csv",
        "error_analysis.csv",
        "stratified_metrics.csv",
        "scalability.csv",
        "policy.json",
        "task_relevance_manifest.json",
        "oracle_manifest.json",
        "holdout_manifest.json",
        "mechanism_evidence.json",
        "report.md",
        "evidence-manifest.json",
    }
    assert expected <= {path.name for path in tmp_path.iterdir()}
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "evidence-manifest.json").read_text(encoding="utf-8"))
    assert summary["protocol"]["frozen_input_sha256"] == frozen
    assert (
        manifest["summary_sha256"]
        == hashlib.sha256((tmp_path / "summary.json").read_bytes()).hexdigest()
    )
    with (tmp_path / "conformance.csv").open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 100 * len(SYSTEMS)
    with (tmp_path / "per_run.csv").open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 3
    assert json.loads((tmp_path / "holdout_manifest.json").read_text(encoding="utf-8"))[
        "case_ids"
    ] == [f"Q2-{index:04d}" for index in range(281, 341)]
    for name in (
        "baseline-comparison.svg",
        "thss-privacy-utility.svg",
        "conflict-automation.svg",
        "error-breakdown.svg",
        "latency.svg",
        "scalability.svg",
    ):
        assert ElementTree.fromstring((tmp_path / name).read_text(encoding="utf-8")).tag.endswith(
            "svg"
        )


def test_comparisons_use_one_predeclared_subject_summary_and_required_strata() -> None:
    result = run(20260808, 400)
    for value in result["comparisons"].values():
        assert "state_correct_mcnemar_exact_subject_summary" in value
        assert value["state_correct_mcnemar_exact_subject_summary"]["discordant"] <= 200
    assert {row["stratum"] for row in result["stratified_metrics"]} == {
        "late_evidence",
        "conflict",
        "authorization_revocation",
        "stale_transition",
    }


def test_invalid_case_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="exactly 400"):
        run(20260808, 399)


def test_thss_ablation_keeps_authorization_fixed() -> None:
    rows = {row["profile"]: row for row in run(20260808, 400)["thss_ablation"]}
    assert tuple(rows) == THSS_PROFILES
    assert all(row["authorization_fixed"] is True for row in rows.values())
    assert all(row["unauthorized_disclosure_numerator"] == 0 for row in rows.values())


def test_cost_of_success_reports_only_declared_measurement_scopes() -> None:
    rows = {row["comparison"]: row for row in run(20260808, 400)["cost_of_success"]}
    assert tuple(rows) == (
        "glhs_full_vs_glhs_no_gst",
        "glhs_full_vs_glhs_no_thss",
        "glhs_full_vs_temporal_provenance_resolver",
    )
    assert rows["glhs_full_vs_glhs_no_gst"]["failure_reduction_numerator"] == 267
    assert rows["glhs_full_vs_glhs_no_thss"]["failure_reduction_numerator"] == 0
    assert rows["glhs_full_vs_temporal_provenance_resolver"]["failure_reduction_numerator"] == 66
    assert rows["glhs_full_vs_glhs_no_gst"]["context_tokens_proxy_delta"] == 0
    assert rows["glhs_full_vs_glhs_no_thss"]["context_tokens_proxy_delta"] == -60
    assert rows["glhs_full_vs_temporal_provenance_resolver"]["context_tokens_proxy_delta"] is None
    assert (
        rows["glhs_full_vs_temporal_provenance_resolver"]["context_scope"]
        == "not_measured_tpr_has_no_thss_compiler_in_protocol"
    )


def test_external_stream_writes_full_raw_csv_without_loading_raw_source_fields(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    perturbations = source / "perturbations.jsonl"
    with perturbations.open("w", encoding="utf-8") as handle:
        for index in range(1, 101):
            case = _case(index)
            handle.write(
                json.dumps(
                    {
                        "case_id": f"stream-{index:03d}",
                        "subject_token": f"token-{index:03d}",
                        "scenario": case.scenario,
                        "expected_state": case.expected_state,
                        "expected_error": case.expected_error,
                        "critical_fact_count": case.critical_fact_count,
                        "nonessential_authorized_fact_count": case.nonessential_authorized_fact_count,
                        "authorized": case.authorized,
                        "episode_count": case.episode_count,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    manifest = source / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "glhs-q2-external-structural-v2",
                "cohort": "synthea_fhir_stu3",
                "partition": "development",
                "perturbations_file": perturbations.name,
                "perturbations_sha256": hashlib.sha256(perturbations.read_bytes()).hexdigest(),
                "source_scan": {"fhir_patient_bundles": 100, "selected_cases": 100},
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"
    result = run_stream(manifest_path=manifest, output=output)
    assert result["cases"] == result["subjects"] == 100
    assert result["metrics"]["glhs_full"]["state_correct"]["numerator"] == 100
    assert validate(output)["valid"] is True
    report = tmp_path / "report.md"
    report.write_text("# Evidence report\n", encoding="utf-8")
    render_full_synthea_report(artifact=output, report=report)
    assert "FULL_SYNTHEA_MACHINE_RESULTS:START" in report.read_text(encoding="utf-8")
    assert not (output / ".external-stream-unique.sqlite3").exists()
    with (output / "external_outcomes.csv").open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 100 * len(SYSTEMS)


def test_synthea_preparer_resumes_from_durable_token_only_checkpoint(tmp_path) -> None:
    """A restarted full scan accepts a prior local token checkpoint.

    The fixture has no clinical values beyond the minimum FHIR structural
    fields.  Its purpose is to prevent regressions where an interrupted
    million-patient run is rejected or leaks source identifiers into the
    checkpoint/output.
    """
    nested = tmp_path / "nested.tar.gz"
    with tarfile.open(nested, "w:gz") as archive:
        for index in range(100):
            payload = json.dumps(
                {
                    "entry": [
                        {"resource": {"resourceType": "Patient", "id": f"raw-patient-{index}"}},
                        {"resource": {"resourceType": "Encounter"}},
                    ]
                }
            ).encode()
            member = tarfile.TarInfo(f"output/fhir/patient-{index}.json")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
    outer = tmp_path / "synthea.tar.gz"
    with tarfile.open(outer, "w:gz") as archive:
        archive.add(nested, arcname="synthea/nested.tar.gz")
    salt = tmp_path / "salt.bin"
    salt.write_bytes(b"s" * 32)
    output = tmp_path / "output"
    output.mkdir()
    checkpoint = output / ".synthea-selection.sqlite3"
    connection = sqlite3.connect(checkpoint)
    connection.execute(
        "CREATE TABLE selected (token TEXT PRIMARY KEY NOT NULL, episodes INTEGER NOT NULL)"
    )
    connection.execute(
        "INSERT INTO selected (token, episodes) VALUES (?, ?)", ("checkpoint-only-token", 1)
    )
    connection.commit()
    connection.close()

    manifest = prepare_synthea(
        archive_path=outer,
        token_salt_file=salt,
        output_dir=output,
        lawful_access_attestation="Synthetic structural data is lawful for testing.",
        selection_modulus=1,
        progress_every_bundles=10,
        resume=True,
    )

    emitted = (output / "perturbations.jsonl").read_text(encoding="utf-8")
    assert manifest["source_scan"]["selected_cases"] == 101
    assert not checkpoint.exists()
    assert "raw-patient" not in emitted


def test_model_arm_integrator_requires_full_frozen_grid(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "model_arm_contract.json").write_text(
        json.dumps(
            {
                "version": PROMPT_VERSION,
                "code_revision": "abcdef1",
                "runner_sha256": "b" * 64,
                "seeds": list(SEEDS),
                "case_count": 1,
                "no_fallback": True,
                "synthetic_only": True,
                "transport": "direct",
                "runtime_selection": {
                    "task": "medical_safety_router",
                    "provider": "deepseek",
                    "configured_model": "frozen-model",
                    "model_version": "v1",
                    "model_profile": "pro",
                    "prompt_version": "p1",
                    "task_contract_schema_version": "c1",
                    "risk_level": "high",
                    "fallback_model": "",
                    "rollback_applied": False,
                    "generation_temperature": 0.0,
                    "generation_max_tokens": 100,
                    "configured_base_url_sha256": "a" * 64,
                },
            }
        ),
        encoding="utf-8",
    )
    fields = [
        "case_id",
        "seed",
        "expected_state",
        "scenario",
        "experiment",
        "status",
        "latency_ms",
        "model_used",
        "policy_action",
        "guard_reason",
        "degraded",
        "json_valid",
        "state",
        "state_correct",
        "answer_sha256",
        "error_class",
    ]
    with (source / "model_per_run.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for seed in SEEDS:
            writer.writerow(
                {
                    "case_id": "Q2-0001",
                    "seed": seed,
                    "expected_state": "state_current",
                    "scenario": "ordinary_latest",
                    "experiment": "direct_conformance",
                    "status": "completed",
                    "latency_ms": "10",
                    "model_used": "frozen-model",
                    "policy_action": "direct_model_arm",
                    "guard_reason": "",
                    "degraded": "False",
                    "json_valid": "True",
                    "state": "state_current",
                    "state_correct": "True",
                    "answer_sha256": "a",
                    "error_class": "",
                }
            )
    summary = integrate(source, tmp_path / "out")
    assert summary["aggregate"]["completed"] == 3
    assert summary["aggregate"]["state_correct"] == 3
    assert (tmp_path / "out" / "model_arm_by_experiment.csv").is_file()

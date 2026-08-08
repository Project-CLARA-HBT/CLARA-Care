"""Contracts for the non-clinical GLHS Q3 structural evaluator."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import tarfile
from xml.etree import ElementTree

from evaluation.glhs_q3.prepare_external_cohort import prepare
from evaluation.glhs_q3.prepare_synthea_archive import prepare as prepare_synthea
from evaluation.glhs_q3.run import SYSTEMS, THSS_PROFILES, run, write


def test_q3_protocol_has_all_predeclared_comparators_and_minimum_scale() -> None:
    result = run(20260808, 300)

    assert result["protocol"]["subjects"] == 150
    assert result["protocol"]["cases"] == 300
    assert tuple(result["metrics"]) == SYSTEMS
    assert result["protocol"]["clinical_validation"] is False
    assert result["reproducibility"]["clinical_data"] is False
    assert result["metrics"]["glhs_full"]["state_correct"]["denominator"] == 300
    assert result["metrics"]["glhs_full"]["unauthorized_disclosure"]["numerator"] == 0
    assert result["metrics"]["glhs_full"]["gst_bypass"]["numerator"] == 0


def test_no_thss_ablation_keeps_authorization_fixed_and_only_exposes_authorized_excess() -> None:
    result = run(20260808, 300)
    rows = {row["profile"]: row for row in result["thss_ablation"]}

    assert tuple(rows) == THSS_PROFILES
    assert all(row["authorization_fixed"] is True for row in rows.values())
    assert all(row["unauthorized_disclosure_numerator"] == 0 for row in rows.values())
    assert rows["strict"]["nonessential_disclosure_numerator"] == 0
    assert rows["full_authorized"]["critical_fact_recall"] == 1.0


def test_writer_emits_frozen_machine_readable_artifacts(tmp_path) -> None:
    write(run(20260808, 300), tmp_path)

    expected = {
        "summary.json",
        "environment.json",
        "cases.csv",
        "outcomes.csv",
        "per_run.csv",
        "baseline_comparison.csv",
        "thss_ablation.csv",
        "error_analysis.csv",
        "scalability.csv",
        "baseline-comparison.svg",
        "thss-privacy-utility.svg",
        "conflict-automation.svg",
        "error-breakdown.svg",
        "latency.svg",
        "scalability.svg",
        "report.md",
        "evidence-manifest.json",
    }
    assert expected <= {path.name for path in tmp_path.iterdir()}
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "evidence-manifest.json").read_text(encoding="utf-8"))
    assert summary["schema_version"] == "glhs-q3-structural-v3"
    assert summary["score_release"]["final_score_released"] is False
    assert manifest["summary_sha256"] == hashlib.sha256(
        (tmp_path / "summary.json").read_bytes()
    ).hexdigest()
    with (tmp_path / "baseline_comparison.csv").open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 5
    for name in (
        "baseline-comparison.svg",
        "thss-privacy-utility.svg",
        "conflict-automation.svg",
        "error-breakdown.svg",
        "latency.svg",
        "scalability.svg",
    ):
        assert ElementTree.fromstring((tmp_path / name).read_text(encoding="utf-8")).tag.endswith("svg")


def test_explicit_mimic_demo_structural_manifest_never_loads_raw_clinical_data(tmp_path) -> None:
    perturbations = tmp_path / "perturbations.jsonl"
    rows = []
    for index in range(100):
        rows.append(
            {
                "case_id": f"mimic-demo-{index:03d}",
                "subject_token": f"deidentified-token-{index:03d}",
                "scenario": "late_evidence" if index % 2 else "conflict",
                "expected_state": "retain_current" if index % 2 else "conflict",
                "expected_error": "temporal_ambiguity"
                if index % 2
                else "comparable_authority_conflict",
                "critical_fact_count": 1,
                "nonessential_authorized_fact_count": 2,
                "authorized": True,
                "episode_count": 10,
            }
        )
    perturbations.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    manifest = tmp_path / "mimic-demo.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "glhs-q3-mimic-demo-v1",
                "cohort": "mimic_iv_demo_fhir",
                "lawful_access_attestation": "Local lawful demo derivative; no raw resource passed.",
                "perturbations_file": perturbations.name,
                "perturbations_sha256": hashlib.sha256(perturbations.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    result = run(20260808, 300, manifest)

    demo = result["mimic_demo"]
    assert demo["status"] == "evaluated_deidentified_structural_perturbations"
    assert demo["cases"] == 100
    assert demo["subjects"] == 100
    assert demo["clinical_data_loaded"] is False
    assert demo["eligible_for_final_score"] is False


def test_sealed_external_holdout_requires_freeze_metadata_and_releases_only_that_score(tmp_path) -> None:
    perturbations = tmp_path / "sealed.jsonl"
    rows = [
        {
            "case_id": f"sealed-{index:03d}",
            "subject_token": f"synthea-token-{index:03d}",
            "scenario": "late_evidence" if index % 2 else "conflict",
            "expected_state": "1000mg" if index % 2 else "conflict",
            "expected_error": "stale_state_version" if index % 2 else "comparable_authority_conflict",
            "critical_fact_count": 3,
            "nonessential_authorized_fact_count": 7,
            "authorized": True,
            "episode_count": 12,
        }
        for index in range(100)
    ]
    perturbations.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    manifest = tmp_path / "sealed.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "glhs-q3-external-structural-v2",
                "cohort": "synthea_fhir_r4",
                "partition": "sealed_holdout",
                "lawful_access_attestation": "Synthetic FHIR R4 records are lawful and de-identified.",
                "perturbations_file": perturbations.name,
                "perturbations_sha256": hashlib.sha256(perturbations.read_bytes()).hexdigest(),
                "freeze": {
                    "freeze_id": "synthea-q3-holdout-20260808",
                    "frozen_at": "2026-08-08T00:00:00Z",
                    "curator": "independent-evaluator",
                    "independence_attestation": "Curator did not implement or tune the compared policies.",
                    "oracle_freeze_sha256": "a" * 64,
                    "development_set_sha256": "b" * 64,
                },
            }
        ),
        encoding="utf-8",
    )

    result = run(20260808, 300, manifest)

    external = result["cohorts"]["external"]
    assert external["cohort"] == "synthea_fhir_r4"
    assert external["partition"] == "sealed_holdout"
    assert external["eligible_for_final_score"] is True
    assert result["score_release"]["final_score_released"] is True


def test_temporal_provenance_baseline_is_stronger_than_lww_but_has_no_policy_gate() -> None:
    result = run(20260808, 300)
    stronger = result["metrics"]["temporal_provenance_resolver"]
    lww = result["metrics"]["lww"]

    assert stronger["state_correct"]["numerator"] > lww["state_correct"]["numerator"]
    assert stronger["unauthorized_disclosure"]["numerator"] > 0
    assert stronger["gst_bypass"]["numerator"] > 0


def test_preparer_consumes_all_declared_source_tables_without_emitting_raw_identifiers(tmp_path) -> None:
    root = tmp_path / "source"
    hosp = root / "hosp"
    hosp.mkdir(parents=True)
    for name, rows in {
        "admissions.csv.gz": [
            {"subject_id": str(index), "admit": "raw-date"} for index in range(100)
        ],
        "prescriptions.csv.gz": [
            {"subject_id": str(index), "drug": "raw-drug-name"} for index in range(100)
        ]
        + [{"subject_id": "0", "drug": "raw-drug-name"}],
    }.items():
        with gzip.open(hosp / name, "wt", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    salt = tmp_path / "salt.bin"
    salt.write_bytes(b"x" * 32)
    output = tmp_path / "output"

    manifest = prepare(
        cohort="mimic_iv_demo",
        source_root=root,
        token_salt_file=salt,
        output_dir=output,
        partition="development",
        lawful_access_attestation="Local lawful demo derivative.",
        freeze=None,
    )

    emitted = (output / "perturbations.jsonl").read_text(encoding="utf-8")
    assert manifest["source_table_rows"] == {
        "hosp/admissions.csv.gz": 100,
        "hosp/prescriptions.csv.gz": 101,
    }
    assert "raw-drug-name" not in emitted
    assert "raw-date" not in emitted
    assert '"subject_id"' not in emitted
    assert len(emitted.splitlines()) == 100


def test_synthea_stream_preparer_never_emits_bundle_fields(tmp_path) -> None:
    nested = tmp_path / "nested.tar.gz"
    with tarfile.open(nested, "w:gz") as archive:
        for index in range(100):
            payload = json.dumps(
                {
                    "type": "collection",
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Patient",
                                "id": f"raw-patient-{index}",
                                "name": [{"text": "raw-name"}],
                            }
                        },
                        {"resource": {"resourceType": "Encounter", "period": "raw-date"}},
                        {"resource": {"resourceType": "MedicationOrder", "text": "raw-medication"}},
                    ],
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

    manifest = prepare_synthea(
        archive_path=outer,
        token_salt_file=salt,
        output_dir=output,
        lawful_access_attestation="Synthetic data is lawful for structural testing.",
        selection_modulus=1,
    )

    emitted = (output / "perturbations.jsonl").read_text(encoding="utf-8")
    assert manifest["cohort"] == "synthea_fhir_stu3"
    assert manifest["source_scan"]["fhir_patient_bundles"] == 100
    assert not (output / ".synthea-selection.sqlite3").exists()
    assert "raw-name" not in emitted
    assert "raw-medication" not in emitted
    assert "raw-patient" not in emitted

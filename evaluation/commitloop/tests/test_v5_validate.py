from __future__ import annotations

import json

from evaluation.commitloop.fixtures import DeterministicFakeTransport
from evaluation.commitloop.provider import (
    CONFIRMATORY_MODELS,
    REVIEWER_MODEL,
    EvaluationClient,
    RunLimits,
)
from evaluation.commitloop.run_local import run_local_e2e
from evaluation.commitloop.solver_packets import CONDITIONS
from evaluation.commitloop.v5_cohort import (
    COHORT_NAME,
    KNOWN_CUTOFF,
    STRATA,
    VALID_CUTOFF,
    build_cohort,
)
from evaluation.commitloop.v5_validate import validate_v5_run


def test_v5_validator_checks_complete_grid_cohort_and_reproduction(tmp_path) -> None:
    cohort_rows, cohort_manifest = build_cohort()
    cohort = cohort_rows[:1]
    cohort_manifest = {
        **cohort_manifest,
        "subject_count": 1,
        "subject_token_count": 1,
        "bundle_hash_count": 1,
        "template_families": list(STRATA),
    }
    cohort_path = tmp_path / "cohort.jsonl"
    cohort_manifest_path = tmp_path / "cohort_manifest.json"
    cohort_path.write_text(
        json.dumps(cohort[0], sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    cohort_manifest_path.write_text(json.dumps(cohort_manifest, sort_keys=True), encoding="utf-8")

    limits = RunLimits(
        max_subjects=1,
        max_cases=1,
        max_requests=len(CONDITIONS) * len(CONFIRMATORY_MODELS),
    )
    transport = DeterministicFakeTransport()
    clients = {
        model: EvaluationClient(
            base_url="https://router.invalid/v1",
            api_key="fixture-secret-not-real",
            transport=transport,
            limits=limits,
        )
        for model in CONFIRMATORY_MODELS
    }
    run_dir = tmp_path / "run"
    run_local_e2e(
        bundles=[(cohort[0]["bundle"], "R4")],
        output_dir=run_dir,
        clients=clients,
        valid_cutoff=VALID_CUTOFF,
        known_cutoff=KNOWN_CUTOFF,
        limits=limits,
        conditions=CONDITIONS,
        primary_model=REVIEWER_MODEL,
        source_cohort=COHORT_NAME,
    )
    report = validate_v5_run(
        run_dir,
        cohort_path=cohort_path,
        cohort_manifest_path=cohort_manifest_path,
        expected_subject_count=1,
    )
    assert report["status"] == "VALID"
    assert report["subjects"] == 1
    assert report["solver_cells"] == len(CONDITIONS) * len(CONFIRMATORY_MODELS)
    assert report["reproduction_status"] == "PASS"

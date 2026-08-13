from pathlib import Path

import pytest

from evaluation.commitloop.fixtures import DeterministicFakeTransport
from evaluation.commitloop.provider import (
    CONFIRMATORY_MODELS,
    EvaluationClient,
    RunLimits,
)
from evaluation.commitloop.v6_cohort import build_cohort
from evaluation.commitloop.v6_runner import (
    run_v6_development_partition,
    sanitize_artifact_cohort,
)


def test_artifact_cohort_redaction_removes_fhir_subject_references() -> None:
    source = {
        "reference": "Patient/synthetic-42",
        "nested": [{"reference": "patient/synthetic-43"}],
        "unrelated": "Patient/not-a-reference",
    }

    sanitized, count = sanitize_artifact_cohort(source)

    assert count == 2
    assert sanitized == {
        "reference": "urn:glhs-bench:redacted-subject",
        "nested": [{"reference": "urn:glhs-bench:redacted-subject"}],
        "unrelated": "Patient/not-a-reference",
    }


def _clients(limits: RunLimits) -> dict[str, EvaluationClient]:
    transport = DeterministicFakeTransport()
    return {
        model: EvaluationClient(
            base_url="https://offline.invalid/v1",
            api_key="offline-fixture-token",
            transport=transport,
            limits=limits,
        )
        for model in CONFIRMATORY_MODELS
    }


def test_v6_runner_refuses_sealed_final_and_wrong_partition_limits(
    tmp_path: Path,
) -> None:
    rows, _ = build_cohort()
    limits = RunLimits(max_subjects=1, max_cases=1, max_requests=27, max_concurrency=5)
    with pytest.raises(ValueError, match="v6_nonfinal_split_required"):
        run_v6_development_partition(
            rows=rows,
            split="sealed_test",
            output_dir=tmp_path,
            clients=_clients(limits),
            freeze_path=tmp_path / "freeze.json",
            provider_probe_path=tmp_path / "probe.json",
            repository_root=tmp_path,
            limits=limits,
        )
    with pytest.raises(ValueError, match="v6_partition_limits_must_match_split"):
        run_v6_development_partition(
            rows=rows,
            split="development",
            output_dir=tmp_path,
            clients=_clients(limits),
            freeze_path=tmp_path / "freeze.json",
            provider_probe_path=tmp_path / "probe.json",
            repository_root=tmp_path,
            limits=limits,
        )


def test_v6_runner_rejects_rows_that_do_not_match_the_frozen_cohort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows, _ = build_cohort()
    limits = RunLimits(max_subjects=96, max_cases=96, max_requests=9_504, max_concurrency=5)
    monkeypatch.setattr(
        "evaluation.commitloop.v6_runner.verify_v6_freeze",
        lambda **_kwargs: {
            "cohort_sha256": "0" * 64,
            "cohort_manifest_sha256": "0" * 64,
        },
    )
    with pytest.raises(ValueError, match="v6_frozen_cohort_artifact_integrity_invalid"):
        run_v6_development_partition(
            rows=rows,
            split="development",
            output_dir=tmp_path / "output",
            clients=_clients(limits),
            freeze_path=tmp_path / "freeze.json",
            provider_probe_path=tmp_path / "probe.json",
            repository_root=tmp_path,
            limits=limits,
        )

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance.final_analyze import analyze_final_run
from evaluation.property_assurance.final_seal import seal_result_root
from evaluation.property_assurance.suite_matrix import METHOD_IDS

SEEDS = (17, 23)
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_catalog(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "govmut-anchor-catalog-v1",
                "status": "partial_anchor_catalog_development_executions_not_final",
                "candidates": [
                    {
                        "id": "M01-A",
                        "family_seed": "M01",
                        "source_path": "services/api/src/clara_api/glhs/gateway.py",
                        "anchor": "if revalidate_state and base_version != expected_state_version:",
                        "replacement": "if False:",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_run(path: Path, *, complete: bool = True, mutant_ids: list[str] | None = None) -> None:
    mutant_ids = mutant_ids or ["M01-A"]
    executions = []
    for mutant_id in mutant_ids:
        for method in METHOD_IDS:
            slot_seeds: list[int | None] = [None] if method == "M0_regression" else list(SEEDS)
            for seed in slot_seeds:
                executions.append(
                    {
                        "method": method,
                        "hypothesis_seed": seed,
                        "result": {
                            "mutant_id": mutant_id,
                            "classification": "KILLED_TEST_ASSERTION",
                            "runtime_ms": 100.0,
                        },
                    }
                )
    if not complete:
        executions = executions[:-1]
    path.write_text(
        json.dumps(
            {
                "schema_version": "govmut-final-run.v1",
                "status": "COMPLETED_NOT_ANALYZED",
                "freeze_id": "test-freeze-001",
                "manifest_path": "final_freeze.json",
                "manifest_sha256": "0" * 64,
                "hypothesis_version": "6.163.0",
                "limits": {
                    "pytest_timeout_seconds": 600,
                    "hypothesis_max_examples": 1000,
                    "hypothesis_stateful_step_count": 100,
                },
                "included_mutant_ids": mutant_ids,
                "executions": executions,
            }
        ),
        encoding="utf-8",
    )


def _result_root(tmp_path: Path) -> Path:
    root = tmp_path / "result"
    root.mkdir()
    _write_catalog(tmp_path / "mutation_site_candidates.json")
    _write_run(root / "final_run.json")
    analyze_final_run(
        run_path=root / "final_run.json",
        catalog_path=tmp_path / "mutation_site_candidates.json",
        output_path=root / "final_analysis.json",
    )
    return root


def _expected_source_sha() -> str:
    completed = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_seal_writes_four_artifacts(tmp_path: Path) -> None:
    root = _result_root(tmp_path)
    artifacts = seal_result_root(result_root=root, repository_root=_REPO_ROOT)

    for name in ("artifact-sha256.json", "environment.json", "README.md", "claim_to_evidence.csv"):
        assert name in artifacts
        assert artifacts[name].is_file()
    assert set(artifacts) == {
        "artifact-sha256.json",
        "environment.json",
        "README.md",
        "claim_to_evidence.csv",
    }


def test_seal_inventory_covers_run_and_analysis_but_not_seal_outputs(
    tmp_path: Path,
) -> None:
    root = _result_root(tmp_path)
    seal_result_root(result_root=root, repository_root=_REPO_ROOT)

    inventory = json.loads((root / "artifact-sha256.json").read_text(encoding="utf-8"))
    assert set(inventory["files"]) == {"final_run.json", "final_analysis.json"}
    assert inventory["freeze_id"] == "test-freeze-001"
    assert inventory["total_files"] == 2


def test_seal_environment_records_source_hypothesis_limits_python(
    tmp_path: Path,
) -> None:
    root = _result_root(tmp_path)
    seal_result_root(result_root=root, repository_root=_REPO_ROOT)

    environment = json.loads((root / "environment.json").read_text(encoding="utf-8"))
    assert environment["source_sha"] == _expected_source_sha()
    assert environment["hypothesis_version"] == "6.163.0"
    assert environment["limits"]["pytest_timeout_seconds"] == 600
    assert environment["python"]["version"]


def test_seal_claim_to_evidence_rows_have_matching_hashes(tmp_path: Path) -> None:
    root = _result_root(tmp_path)
    seal_result_root(result_root=root, repository_root=_REPO_ROOT)

    with (root / "claim_to_evidence.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows, "expected at least one claim row"
    assert any(row["claim_id"] == "CLAIM-MUTSCORE-M1_stateless_property" for row in rows)
    for row in rows:
        evidence = row["evidence_artifact"]
        assert (root / evidence).is_file()
        assert row["evidence_sha256"] == _hash_file(root / evidence)


def test_seal_readme_mentions_freeze_and_plan(tmp_path: Path) -> None:
    root = _result_root(tmp_path)
    seal_result_root(result_root=root, repository_root=_REPO_ROOT)

    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "test-freeze-001" in readme
    assert "ANALYSIS_PLAN.md" in readme
    assert "not external clinical validation" in readme


def test_seal_refuses_invalid_run(tmp_path: Path) -> None:
    root = tmp_path / "result"
    root.mkdir()
    _write_run(root / "final_run.json", complete=False, mutant_ids=["M01-A", "M02-A"])
    with pytest.raises(FreezeError, match="govmut_final_validate_missing_slots"):
        seal_result_root(result_root=root, repository_root=_REPO_ROOT)


def test_seal_refuses_missing_run_and_missing_root(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    with pytest.raises(FreezeError, match="govmut_final_seal_run_missing"):
        seal_result_root(result_root=root, repository_root=_REPO_ROOT)
    with pytest.raises(FreezeError, match="govmut_final_seal_result_root_missing"):
        seal_result_root(result_root=tmp_path / "nope", repository_root=_REPO_ROOT)


def test_seal_refuses_unavailable_repository_revision(tmp_path: Path) -> None:
    root = _result_root(tmp_path)
    with pytest.raises(FreezeError, match="govmut_final_seal_repository_revision_unavailable"):
        seal_result_root(result_root=root, repository_root=tmp_path / "not-a-repo")


def _hash_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()

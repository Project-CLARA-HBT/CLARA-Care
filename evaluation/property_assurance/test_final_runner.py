from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance import final_runner


def _manifest() -> dict[str, object]:
    return {
        "freeze_id": "soict-final-001",
        "methods": {
            method: {"targets": [f"tests/{method}.py"]}
            for method in ("M0_regression", "M1_stateless_property", "M2_state_machine", "M3_combined")
        },
        "hypothesis": {"version": "6.99.0", "ordered_seeds": [11, 29]},
        "limits": {"pytest_timeout_seconds": 37},
        "non_equivalence_review": {"artifact": "review.json"},
    }


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    manifest = tmp_path / "freeze.json"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"candidates": [
        {"id": "M01-A", "source_path": "a.py", "anchor": "a", "replacement": "b"},
        {"id": "M02-A", "source_path": "a.py", "anchor": "c", "replacement": "d"},
    ]}), encoding="utf-8")
    (tmp_path / "review.json").write_text(json.dumps({"dispositions": [
        {"mutant_id": "M01-A", "disposition": "included"},
        {"mutant_id": "M02-A", "disposition": "excluded_equivalent"},
    ]}), encoding="utf-8")
    statistics = tmp_path / "statistics.json"
    statistics.write_text("{}", encoding="utf-8")
    return manifest, catalog, statistics, tmp_path / "run.json"


def test_final_runner_executes_only_included_catalog_entries_across_locked_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, catalog, statistics, output = _write_inputs(tmp_path)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(final_runner, "validate_final_freeze", lambda **_kwargs: _manifest())
    monkeypatch.setattr(final_runner, "_hypothesis_version", lambda: "6.99.0")
    monkeypatch.setattr(final_runner, "execute_mutant", lambda **kwargs: calls.append(kwargs) or {"classification": "SURVIVED"})

    result = final_runner.execute_final_run(
        manifest_path=manifest, repository_root=tmp_path, catalog_path=catalog,
        statistics_plan_path=statistics, output_path=output,
    )

    assert result["included_mutant_ids"] == ["M01-A"]
    assert [(call["pytest_targets"], call["hypothesis_seed"]) for call in calls] == [
        (["tests/M0_regression.py"], None),
        (["tests/M1_stateless_property.py"], 11),
        (["tests/M1_stateless_property.py"], 29),
        (["tests/M2_state_machine.py"], 11),
        (["tests/M2_state_machine.py"], 29),
        (["tests/M3_combined.py"], 11),
        (["tests/M3_combined.py"], 29),
    ]
    assert all(call["pytest_timeout_seconds"] == 37 for call in calls)
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["status"] == "COMPLETED_NOT_ANALYZED"
    assert persisted["manifest_sha256"] == sha256(manifest.read_bytes()).hexdigest()
    assert persisted["hypothesis_version"] == "6.99.0"
    assert persisted["limits"] == _manifest()["limits"]


def test_final_runner_refuses_hypothesis_version_drift_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, catalog, statistics, output = _write_inputs(tmp_path)
    monkeypatch.setattr(final_runner, "validate_final_freeze", lambda **_kwargs: _manifest())
    monkeypatch.setattr(final_runner, "_hypothesis_version", lambda: "different")

    with pytest.raises(FreezeError, match="govmut_final_runner_hypothesis_version_mismatch"):
        final_runner.execute_final_run(
            manifest_path=manifest, repository_root=tmp_path, catalog_path=catalog,
            statistics_plan_path=statistics, output_path=output,
        )
    assert not output.exists()

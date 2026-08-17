from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance import soict_final_runner
from evaluation.property_assurance.soict_final_inputs import generate_soict_final_inputs


def test_soict_final_inputs_cover_catalog_and_bind_complete_matrix(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    outputs = generate_soict_final_inputs(repository_root=root, output_dir=tmp_path)

    review = json.loads(outputs["review_manifest"].read_text(encoding="utf-8"))
    freeze = json.loads(outputs["corpus_freeze_input"].read_text(encoding="utf-8"))
    catalog = json.loads(
        (root / "research/assurance_soict/mutation_site_candidates.json").read_text(encoding="utf-8")
    )

    assert review["status"] == "frozen"
    assert [case["case_id"] for case in review["cases"]] == [item["id"] for item in catalog["candidates"]]
    assert freeze["status"] == "awaiting_dual_model_review_and_hypothesis_environment"
    assert set(freeze["methods"]) == {"M0_regression", "M1_stateless_property", "M2_state_machine", "M3_combined"}
    assert freeze["methods"]["M3_combined"]["targets"] == [
        *freeze["methods"]["M0_regression"]["targets"],
        *freeze["methods"]["M1_stateless_property"]["targets"],
        *freeze["methods"]["M2_state_machine"]["targets"],
    ]


def test_soict_final_runner_uses_only_soict_fixed_paths(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "repository"
    calls: dict[str, Path] = {}

    def fake_execute_final_run(**kwargs):
        calls.update(kwargs)
        return {"status": "COMPLETED_NOT_ANALYZED"}

    monkeypatch.setattr(soict_final_runner, "execute_final_run", fake_execute_final_run)
    output = tmp_path / "output.json"
    assert soict_final_runner.run_soict_final(repository_root=root, output_path=output)["status"] == "COMPLETED_NOT_ANALYZED"
    assert calls == {
        "manifest_path": root / "research/assurance_soict/final_freeze.json",
        "repository_root": root,
        "catalog_path": root / "research/assurance_soict/mutation_site_candidates.json",
        "statistics_plan_path": root / "research/assurance_soict/statistics_plan.json",
        "output_path": output,
    }


def test_soict_final_runner_refuses_unpromoted_freeze(tmp_path: Path) -> None:
    with pytest.raises(FreezeError, match="govmut_soict_final_freeze_not_promoted"):
        soict_final_runner.run_soict_final(
            repository_root=tmp_path, output_path=tmp_path / "output.json"
        )

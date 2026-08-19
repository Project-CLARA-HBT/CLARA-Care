"""W9 corpus-freeze inputs and w9 final-runner tests (no mutants executed, no models called)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.model_adjudication.run_v2 import _load_manifest
from evaluation.property_assurance import w9_final_runner

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "research" / "assurance_soict"

W9_MANIFEST = RESEARCH / "w9_review_manifest.json"
W9_FREEZE_INPUT = RESEARCH / "w9_freeze_input.json"
W9_CATALOG = RESEARCH / "w9_catalog.json"
W9_CATALOG_FULL = RESEARCH / "W9_MUTATION_CATALOG.json"
W9_PROPOSAL = RESEARCH / "W9_FOLLOWUP_CORPUS_PROPOSAL.json"
SEALED_FREEZE = RESEARCH / "final_freeze.json"

SEALED_ARTIFACTS = (
    "final_freeze.json",
    "final_run.json",
    "results/final-analysis.json",
    "mutation_site_candidates.json",
    "corpus_freeze_input.json",
    "dual_model_review_manifest.json",
    "statistics_plan.json",
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _catalog_ids(catalog: dict[str, object]) -> list[str]:
    candidates = catalog["candidates"]
    assert isinstance(candidates, list)
    ids = [item["id"] for item in candidates if isinstance(item, dict)]
    return [item for item in ids if isinstance(item, str)]


def test_w9_catalogs_have_eleven_entries_matching_proposal() -> None:
    proposal = _load(W9_PROPOSAL)
    full = _load(W9_CATALOG_FULL)
    machine = _load(W9_CATALOG)

    expected = _catalog_ids(proposal)
    assert len(expected) == 11
    assert expected == ["W9-C01", "W9-C02", "W9-C03", "W9-C04", "W9-C05", "W9-G01", "W9-G02", "W9-G03", "W9-P01", "W9-P02", "W9-P03"]

    assert _catalog_ids(full) == expected
    assert _catalog_ids(machine) == expected
    verification = _load(RESEARCH / "w9_anchor_verification.json")
    verification_revision = verification["verified_revision"]
    assert full["anchor_verification"]["revision_verified"] == verification_revision
    assert machine["anchor_verification"]["revision_verified"] == verification_revision
    for candidate in full["candidates"]:
        assert isinstance(candidate, dict), "full catalog candidate not an object"
        assert candidate["status"] in {"anchor_verified_not_executed", "anchor_reanchored_not_executed"}
        assert candidate["anchor_status"] in {"VERIFIED", "REANCHORED", "INVALIDATED"}
        assert candidate["anchor_verified_revision"] == verification_revision
        assert candidate["layer"] in {"commitment gateway", "governance-cache", "persistence-reconstruction"}
        assert candidate["id"].startswith("W9-")
    for candidate in machine["candidates"]:
        assert isinstance(candidate, dict), "machine catalog candidate not an object"
        assert set(candidate) == {
            "id",
            "source_path",
            "anchor",
            "replacement",
            "family_seed",
            "status",
            "anchor_status",
            "anchor_verified_revision",
        }
        assert candidate["status"] in {"anchor_verified_not_executed", "anchor_reanchored_not_executed"}
        assert candidate["anchor_status"] in {"VERIFIED", "REANCHORED", "INVALIDATED"}
        assert candidate["anchor_verified_revision"] == verification_revision


def _head_blob(relative_path: str, revision: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{revision}:{relative_path}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_w9_anchors_unique_in_verified_head_blob() -> None:
    revision = _load(RESEARCH / "w9_anchor_verification.json")["verified_revision"]
    for catalog_path in (W9_CATALOG_FULL, W9_CATALOG):
        catalog = _load(catalog_path)
        for candidate in catalog["candidates"]:
            assert isinstance(candidate, dict), "catalog candidate not an object"
            source_path = candidate["source_path"]
            assert isinstance(source_path, str)
            source = _head_blob(source_path, revision)
            anchor = candidate["anchor"]
            assert isinstance(anchor, str) and anchor
            count = source.count(anchor)
            assert count == 1, f"{candidate['id']}: anchor count {count} in {source_path}"


def test_w9_review_manifest_passes_strict_v2_loader_and_covers_catalog() -> None:
    manifest = _load_manifest(W9_MANIFEST)
    machine = _load(W9_CATALOG)
    assert manifest["status"] == "frozen"
    assert manifest["schema_version"] == "clara-model-review-manifest.v2"
    assert manifest["study_id"] == "assurance-soict-2026-w9"
    cases = manifest["cases"]
    assert [case["case_id"] for case in cases] == _catalog_ids(machine)
    full = _load(W9_CATALOG_FULL)
    for case, candidate in zip(cases, full["candidates"], strict=True):
        assert set(case["evidence"]) == {"E1", "E2", "E3", "E4"}
        assert "Fault family:" in case["evidence"]["E1"]
        assert case["evidence"]["E1"].startswith(f"Fault family: {candidate['fault_family']}. Layer: {candidate['layer']}")
        assert candidate["anchor"] in case["evidence"]["E2"]
        assert candidate["replacement"] in case["evidence"]["E2"]
        assert candidate["source_path"] in case["evidence"]["E2"]
        assert candidate["invariant"] in case["evidence"]["E3"]
        assert case["evidence"]["E4"].startswith("Relevant test semantics:")


def test_w9_freeze_input_matches_sealed_methods_hypothesis_and_limits() -> None:
    w9 = _load(W9_FREEZE_INPUT)
    sealed = _load(SEALED_FREEZE)
    verification = _load(RESEARCH / "w9_anchor_verification.json")
    assert w9["schema_version"] == "govmut-final-freeze-input.v1"
    assert w9["status"] == "awaiting_manual_human_review"
    assert w9["methods"] == sealed["methods"]
    assert w9["hypothesis"] == sealed["hypothesis"]
    assert w9["limits"] == sealed["limits"]
    assert w9["code_revision"] == verification["verified_revision"]
    assert w9["catalog"] == "w9_catalog.json"
    assert w9["statistics_plan"] == "statistics_plan.json"
    assert w9["catalog_sha256"] == hashlib.sha256(W9_CATALOG.read_bytes()).hexdigest()
    assert w9["statistics_plan_sha256"] == hashlib.sha256((RESEARCH / "statistics_plan.json").read_bytes()).hexdigest()
    assert w9["non_equivalence_review"]["manifest"] == "w9_review_manifest.json"
    assert w9["non_equivalence_review"]["result_artifact"] == "model_review_run_w9/dual_model_review.json"
    assert w9["non_equivalence_review"]["results_sha256"] is None
    assert "NON_EQUIVALENT" in w9["promotion_rule"] and "UNRESOLVED" in w9["promotion_rule"]


def test_w9_final_runner_uses_only_w9_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repository"
    (root / "research/assurance_soict").mkdir(parents=True)
    (root / "research/assurance_soict/w9_final_freeze.json").write_text("{}", encoding="utf-8")
    calls: dict[str, Path] = {}

    def fake_execute_final_run(**kwargs):
        calls.update(kwargs)
        return {"status": "COMPLETED_NOT_ANALYZED"}

    monkeypatch.setattr(w9_final_runner, "execute_final_run", fake_execute_final_run)
    monkeypatch.setattr(w9_final_runner, "validate_human_review_gate", lambda **_kwargs: {})
    output = tmp_path / "output.json"
    assert w9_final_runner.run_w9_final(repository_root=root, output_path=output)["status"] == "COMPLETED_NOT_ANALYZED"
    assert calls == {
        "manifest_path": root / "research/assurance_soict/w9_final_freeze.json",
        "repository_root": root,
        "catalog_path": root / "research/assurance_soict/w9_catalog.json",
        "statistics_plan_path": root / "research/assurance_soict/statistics_plan.json",
        "output_path": output,
    }
    assert calls["manifest_path"].name == "w9_final_freeze.json"
    assert calls["manifest_path"].name != "final_freeze.json"
    assert calls["catalog_path"].name == "w9_catalog.json"


def test_w9_final_runner_refuses_unpromoted_freeze(tmp_path: Path) -> None:
    with pytest.raises(FreezeError, match="govmut_w9_final_freeze_not_promoted"):
        w9_final_runner.run_w9_final(repository_root=tmp_path, output_path=tmp_path / "output.json")


def test_w9_final_runner_refuses_promoted_freeze_without_manual_review(
    tmp_path: Path,
) -> None:
    research = tmp_path / "research/assurance_soict"
    research.mkdir(parents=True)
    (research / "w9_final_freeze.json").write_text("{}", encoding="utf-8")
    (research / "w9_catalog.json").write_text(
        json.dumps({"candidates": [{"id": "W9-C01"}]}), encoding="utf-8"
    )
    with pytest.raises(FreezeError, match="govmut_w9_human_review_gate_open"):
        w9_final_runner.run_w9_final(
            repository_root=tmp_path, output_path=tmp_path / "output.json"
        )


def test_w8_sealed_artifacts_remain_immutable() -> None:
    revision = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    for relative in SEALED_ARTIFACTS:
        git_path = f"research/assurance_soict/{relative}"
        head_bytes = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{revision}:{git_path}"],
            check=True,
            capture_output=True,
        ).stdout
        local = (ROOT / git_path).read_bytes()
        assert head_bytes == local, f"sealed artifact changed: {relative}"

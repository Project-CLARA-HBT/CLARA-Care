from __future__ import annotations

import hashlib
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from evaluation.contract_clause_ablation.engine import VARIANTS, ContractCase, evaluate
from evaluation.contract_clause_ablation.run import cases, run
from evaluation.contract_clause_ablation.validate import (
    validate,
    validate_frozen_contract,
)


def test_valid_write_survives_every_clause_and_gains_reconstruction() -> None:
    outcomes = {variant: evaluate(variant, ContractCase(case_id="valid")) for variant in VARIANTS}
    assert all(outcome.accepted for outcome in outcomes.values())
    assert outcomes["provenance_audit"].audit_link_present is True
    assert outcomes["snapshot_id_binding"].exact_seen_context_reconstructable is False
    assert outcomes["snapshot_context_binding"].exact_seen_context_reconstructable is True


def test_each_attack_is_localized_to_its_first_incremental_clause() -> None:
    valid = ContractCase(case_id="valid")
    matrix = (
        (replace(valid, profile_matches=False), "base_version_write", "profile_mismatch"),
        (replace(valid, base_version_matches=False), "base_version_write", "base_version"),
        (
            replace(valid, authorized_at_disclosure=False),
            "authorization_at_disclosure",
            "authorization_at_disclosure_denied",
        ),
        (replace(valid, provenance_present=False), "provenance_audit", "provenance_required"),
        (replace(valid, snapshot_id_matches=False), "snapshot_id_binding", "snapshot_id"),
        (replace(valid, actor_matches=False), "snapshot_context_binding", "actor_mismatch"),
        (replace(valid, actor_role_matches=False), "snapshot_context_binding", "actor_role"),
        (replace(valid, purpose_matches=False), "snapshot_context_binding", "purpose_mismatch"),
        (replace(valid, task_matches=False), "snapshot_context_binding", "task_mismatch"),
        (replace(valid, digest_matches=False), "snapshot_context_binding", "snapshot_digest"),
        (
            replace(valid, evidence_within_snapshot=False),
            "snapshot_context_binding",
            "evidence_not_disclosed",
        ),
        (replace(valid, snapshot_unexpired=False), "complete_glhs_contract", "snapshot_expired"),
        (
            replace(valid, authorized_at_write=False),
            "complete_glhs_contract",
            "current_reauthorization_denied",
        ),
        (replace(valid, policy_matches=False), "complete_glhs_contract", "policy_version"),
        (replace(valid, consent_matches=False), "complete_glhs_contract", "consent_version"),
    )
    for case, first_variant, reason in matrix:
        index = VARIANTS.index(first_variant)
        assert all(evaluate(variant, case).accepted for variant in VARIANTS[:index])
        assert reason in evaluate(first_variant, case).reason_code


def test_runner_writes_complete_deterministic_grid_and_checksum(tmp_path) -> None:
    output = tmp_path / "ablation"
    result = run(output)
    rows = result["rows"]
    assert isinstance(rows, list)
    assert len(rows) == len(cases()) * len(VARIANTS)
    expected = (output / "checksums.sha256").read_text().split()[0]
    assert hashlib.sha256((output / "results.json").read_bytes()).hexdigest() == expected
    assert result["external_calls"] == 0
    assert validate(output)["aggregate"] == result["aggregate"]


def test_validator_rejects_tampered_artifact(tmp_path) -> None:
    output = tmp_path / "ablation"
    run(output)
    (output / "results.json").write_text("{}\n", encoding="utf-8")
    try:
        validate(output)
    except ValueError as exc:
        assert str(exc) == "ablation_checksum_mismatch"
    else:
        raise AssertionError("tampered artifact unexpectedly validated")


def test_frozen_contract_validates_and_detects_code_tampering(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parent
    frozen = validate_frozen_contract(source)
    assert frozen["case_count"] == len(cases())

    copied = tmp_path / "contract"
    copied.mkdir()
    for filename in ("engine.py", "run.py", "experiment_manifest.json"):
        shutil.copy2(source / filename, copied / filename)
    (copied / "run.py").write_text("# tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ablation_contract_digest_mismatch:run.py"):
        validate_frozen_contract(copied)

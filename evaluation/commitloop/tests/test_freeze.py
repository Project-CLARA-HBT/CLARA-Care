from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from evaluation.commitloop import freeze
from evaluation.commitloop.cli import _local_fixture
from evaluation.commitloop.freeze import FreezeError, create_implementation_freeze
from evaluation.commitloop.validate import validate_run


def _evidence(
    *,
    result: str = "passed",
    complete: bool = True,
    validated_git_sha: str = "phase-a-test-sha",
) -> dict[str, object]:
    gates = freeze.REQUIRED_VALIDATION_GATES if complete else {"targeted_tests"}
    return {
        "schema_version": "commitloop-phase-a-validation.v1",
        "validated_git_sha": validated_git_sha,
        "router_calls_before_freeze": 0,
        "commands": [
            {
                "gate": gate,
                "command": f"offline-{gate}",
                "result": result,
                "exit_code": 0,
                "result_summary": "synthetic fixture passed",
                "completed_at_utc": datetime(2026, 8, 11, tzinfo=UTC).isoformat(),
            }
            for gate in sorted(gates)
        ],
    }


def test_freeze_requires_a_clean_worktree_before_reading_run_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(freeze, "_git", lambda *_: " M user-owned-file")
    with pytest.raises(
        FreezeError, match="implementation_freeze_requires_clean_worktree"
    ):
        create_implementation_freeze(
            run_dir=tmp_path / "absent-run",
            repository_root=tmp_path,
            validation_evidence=_evidence(),
        )


def test_freeze_requires_explicit_passing_local_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        freeze,
        "_git",
        lambda _, *args: "" if args[0] == "status" else "phase-a-test-sha",
    )
    with pytest.raises(FreezeError, match="local_validation_not_complete"):
        create_implementation_freeze(
            run_dir=tmp_path / "absent-run",
            repository_root=tmp_path,
            validation_evidence=_evidence(result="not-run"),
        )


def test_freeze_requires_every_predeclared_phase_a_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        freeze,
        "_git",
        lambda _, *args: "" if args[0] == "status" else "phase-a-test-sha",
    )
    with pytest.raises(FreezeError, match="local_validation_gates_missing"):
        create_implementation_freeze(
            run_dir=tmp_path / "absent-run",
            repository_root=tmp_path,
            validation_evidence=_evidence(complete=False),
        )


def test_freeze_seals_complete_local_evidence_when_git_boundary_is_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    _local_fixture(run_dir, max_requests=500)

    def fake_git(_: Path, *args: str) -> str:
        return "" if args == ("status", "--porcelain") else "phase-a-test-sha"

    monkeypatch.setattr(freeze, "_git", fake_git)
    monkeypatch.setattr(freeze, "scan_paths", lambda _: [])
    output = create_implementation_freeze(
        run_dir=run_dir,
        repository_root=Path.cwd(),
        validation_evidence=_evidence(),
    )
    payload = json.loads(output.read_text())
    assert payload["phase_a_status"] == "COMPLETE"
    assert payload["router_calls_before_freeze"] == 0
    assert payload["git_sha"] == "phase-a-test-sha"
    validate_run(run_dir)


def test_freeze_fails_on_any_tracked_repository_secret_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    _local_fixture(run_dir, max_requests=500)
    monkeypatch.setattr(
        freeze,
        "_git",
        lambda _, *args: (
            "" if args == ("status", "--porcelain") else "phase-a-test-sha"
        ),
    )
    sentinel = Path("tracked-unsafe-history.md")
    monkeypatch.setattr(freeze, "tracked_paths", lambda _: [sentinel])
    seen: list[Path] = []

    def findings(paths: list[Path]) -> list[str]:
        seen.extend(paths)
        return [str(sentinel)]

    monkeypatch.setattr(freeze, "scan_paths", findings)
    with pytest.raises(FreezeError, match="tracked_repository_secret_scan_failed"):
        create_implementation_freeze(
            run_dir=run_dir,
            repository_root=Path.cwd(),
            validation_evidence=_evidence(),
        )
    assert seen == [sentinel]


def test_freeze_rejects_a_bounded_incomplete_local_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    manifest = _local_fixture(run_dir, max_requests=20)
    assert manifest["run_status"] == "BOUNDED_INCOMPLETE"
    monkeypatch.setattr(
        freeze,
        "_git",
        lambda _, *args: (
            "" if args == ("status", "--porcelain") else "phase-a-test-sha"
        ),
    )
    monkeypatch.setattr(freeze, "scan_paths", lambda _: [])
    with pytest.raises(
        FreezeError, match="implementation_freeze_requires_complete_local_run"
    ):
        create_implementation_freeze(
            run_dir=run_dir,
            repository_root=Path.cwd(),
            validation_evidence=_evidence(),
        )


def test_freeze_rejects_evidence_from_a_different_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        freeze,
        "_git",
        lambda _, *args: "" if args[0] == "status" else "phase-a-test-sha",
    )
    with pytest.raises(FreezeError, match="local_validation_git_sha_mismatch"):
        create_implementation_freeze(
            run_dir=tmp_path / "absent-run",
            repository_root=tmp_path,
            validation_evidence=_evidence(validated_git_sha="older-sha"),
        )


def test_freeze_rejects_secret_bearing_evidence_before_writing_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = _evidence()
    commands = evidence["commands"]
    assert isinstance(commands, list)
    commands[0]["command"] = "Authorization: " + "Bearer " + ("x" * 24)
    monkeypatch.setattr(
        freeze,
        "_git",
        lambda _, *args: (
            "" if args == ("status", "--porcelain") else "phase-a-test-sha"
        ),
    )
    run_dir = tmp_path / "run"
    with pytest.raises(FreezeError, match="local_validation_evidence_contains_secret"):
        create_implementation_freeze(
            run_dir=run_dir,
            repository_root=tmp_path,
            validation_evidence=evidence,
        )
    assert not (run_dir / "implementation_freeze.json").exists()


def test_live_repository_verifier_rejects_dirty_or_changed_frozen_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frozen_input = tmp_path / "frozen-input.txt"
    frozen_input.write_text("sealed", encoding="utf-8")
    monkeypatch.setattr(freeze, "FREEZE_INPUTS", ("frozen-input.txt",))
    payload = {
        "git_sha": "phase-a-test-sha",
        "input_sha256": {"frozen-input.txt": freeze._sha256(frozen_input)},
    }

    monkeypatch.setattr(freeze, "_git", lambda *_: " M frozen-input.txt")
    with pytest.raises(FreezeError, match="phase_b_requires_clean_frozen_worktree"):
        freeze.verify_live_repository_matches_freeze(payload, tmp_path)

    def clean_git(_: Path, *args: str) -> str:
        return "" if args == ("status", "--porcelain") else "phase-a-test-sha"

    monkeypatch.setattr(freeze, "_git", clean_git)
    frozen_input.write_text("changed", encoding="utf-8")
    with pytest.raises(FreezeError, match="phase_b_freeze_input_hash_mismatch"):
        freeze.verify_live_repository_matches_freeze(payload, tmp_path)

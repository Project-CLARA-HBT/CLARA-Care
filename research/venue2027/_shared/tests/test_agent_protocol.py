"""Tests for SH-agent_protocol (research/venue2027/_shared/tools/agent_protocol.py).

Positive controls:
- A well-formed PASS report with real green commands and hashed artifacts validates.
- build_report hashes real artifacts and round-trips through validate_report.

Adversarial controls (each must be REFUSED, never silently treated as safe):
- PASS with no commands.
- PASS with a non-zero exit code.
- PASS whose declared artifact hash does not match the file.
- PASS whose source_sha_after is not a commit in the repo.
- Report for a different task id.
- PASS while a dependency is not completed.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

import pytest

TOOLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import agent_protocol as ap  # noqa: E402


def _git(repo: pathlib.Path, *argv: str) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), *argv], check=True, capture_output=True, text=True
    )
    return res.stdout.strip()


@pytest.fixture()
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "T")
    (r / "artifact.txt").write_text("evidence\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "init")
    return r


def _sha(repo: pathlib.Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


def _good_report(repo: pathlib.Path, **overrides: object) -> dict[str, object]:
    artifact = repo / "artifact.txt"
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    log = repo / "artifact.log"
    log.write_text("pytest -q\ncollected 1 item\n1 passed\n", encoding="utf-8")
    base: dict[str, object] = {
        "task_id": "SH-repo_fingerprint",
        "status": "PASS",
        "source_sha_before": _sha(repo),
        "source_sha_after": _sha(repo),
        "changed_paths": ["artifact.txt"],
        "commands": [{"argv": "pytest -q", "exit_code": 0, "log_path": "artifact.log"}],
        "artifacts_sha256": {"artifact.txt": digest},
        "oracle_disagreement_count": 0,
        "baseline_parity": "NOT_APPLICABLE",
        "unresolved": [],
    }
    base.update(overrides)
    return base


def test_valid_pass_report(repo: pathlib.Path) -> None:
    result = ap.validate_report(_good_report(repo), repo=repo)
    assert result.ok is True, result.errors
    assert result.reason_code == "OK"


def test_pass_without_commands_refused(repo: pathlib.Path) -> None:
    result = ap.validate_report(_good_report(repo, commands=[]), repo=repo)
    assert result.ok is False
    assert result.reason_code == "NO_COMMANDS"


def test_nonzero_exit_refused(repo: pathlib.Path) -> None:
    report = _good_report(repo, commands=[{"argv": "pytest -q", "exit_code": 1}])
    result = ap.validate_report(report, repo=repo)
    assert result.ok is False
    assert result.reason_code == "NONZERO_EXIT"


def test_artifact_hash_mismatch_refused(repo: pathlib.Path) -> None:
    report = _good_report(repo, artifacts_sha256={"artifact.txt": "0" * 64})
    result = ap.validate_report(report, repo=repo)
    assert result.ok is False
    assert result.reason_code == "ARTIFACT_HASH_MISMATCH"


def test_artifact_missing_refused(repo: pathlib.Path) -> None:
    report = _good_report(repo, artifacts_sha256={"nope.txt": "0" * 64})
    result = ap.validate_report(report, repo=repo)
    assert result.ok is False
    assert result.reason_code == "ARTIFACT_MISSING"


def test_unknown_source_sha_refused(repo: pathlib.Path) -> None:
    report = _good_report(repo, source_sha_after="deadbeef" * 5)
    result = ap.validate_report(report, repo=repo)
    assert result.ok is False
    assert result.reason_code == "SHA_NOT_IN_REPO"


def test_task_mismatch_refused(repo: pathlib.Path) -> None:
    result = ap.validate_report(
        _good_report(repo), repo=repo, expected_task_id="SH-agent_protocol"
    )
    assert result.ok is False
    assert result.reason_code == "TASK_MISMATCH"


def test_dependency_not_completed_refused(repo: pathlib.Path) -> None:
    result = ap.validate_report(
        _good_report(repo),
        repo=repo,
        task_dependencies=["SH-other"],
        completed_tasks=[],
    )
    assert result.ok is False
    assert result.reason_code == "DEPENDENCIES_UNSATISFIED"


def test_blocked_report_needs_no_commands(repo: pathlib.Path) -> None:
    report = _good_report(repo, status="BLOCKED", commands=[])
    result = ap.validate_report(report, repo=repo)
    assert result.ok is True


def test_build_report_hashes_artifacts(repo: pathlib.Path) -> None:
    (repo / "artifact.log").write_text("1 passed\n", encoding="utf-8")
    report = ap.build_report(
        task_id="SH-repo_fingerprint",
        status="PASS",
        source_sha_before=_sha(repo),
        source_sha_after=_sha(repo),
        changed_paths=["artifact.txt"],
        commands=[{"argv": "pytest -q", "exit_code": 0, "log_path": "artifact.log"}],
        artifact_paths=["artifact.txt"],
        repo=repo,
    )
    expected = hashlib.sha256((repo / "artifact.txt").read_bytes()).hexdigest()
    assert report["artifacts_sha256"]["artifact.txt"] == expected
    assert ap.validate_report(report, repo=repo).ok is True


def test_mark_task_records_state(repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    manifest = tmp_path / "tasks.json"
    manifest.write_text(
        json.dumps(
            [
                {"id": "T1", "depends": []},
                {"id": "T2", "depends": ["T1"]},
            ]
        ),
        encoding="utf-8",
    )
    state = tmp_path / "state.json"
    report = _good_report(repo, task_id="T1")
    report_path = tmp_path / "T1.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    result = ap.mark_task(
        task_id="T1",
        status="PASS",
        report_path=report_path,
        repo=repo,
        manifest_path=manifest,
        state_path=state,
    )
    assert result.ok is True, result.errors
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert "T1" in saved["completed"]

    # T2 must remain blocked until T1 is complete; then become eligible.
    report2 = _good_report(repo, task_id="T2")
    report2_path = tmp_path / "T2.json"
    report2_path.write_text(json.dumps(report2), encoding="utf-8")
    result2 = ap.mark_task(
        task_id="T2",
        status="PASS",
        report_path=report2_path,
        repo=repo,
        manifest_path=manifest,
        state_path=state,
    )
    assert result2.ok is True, result2.errors

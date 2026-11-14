"""Tests for SH-repo_fingerprint (research/venue2027/_shared/tools/repo_fingerprint.py).

Covers positive and adversarial controls required by the task contract:
- Positive: fingerprint of a real clean git repo reports OK and a stable digest.
- Positive: digest is deterministic across two calls.
- Adversarial: a dirty worktree is refused with DIRTY_WORKTREE (never silent OK).
- Adversarial: a non-git directory is refused with NOT_A_GIT_REPO.
- Adversarial: a repo missing a required contract anchor is refused.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

TOOLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import repo_fingerprint as rf  # noqa: E402


def _git(repo: pathlib.Path, *argv: str) -> None:
    subprocess.run(["git", "-C", str(repo), *argv], check=True, capture_output=True)


@pytest.fixture()
def clean_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    for rel in rf.REQUIRED_ANCHOR_FILES:
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {rel}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def test_clean_repo_reports_ok(clean_repo: pathlib.Path) -> None:
    fp = rf.snapshot(clean_repo)
    assert fp.ok is True, fp.detail
    assert fp.reason_code == "OK"
    assert fp.worktree_clean is True
    assert len(fp.head_sha) == 40
    assert fp.tracked_file_count == len(rf.REQUIRED_ANCHOR_FILES)
    assert fp.content_sha256
    assert fp.missing_required_files == ()


def test_digest_is_deterministic(clean_repo: pathlib.Path) -> None:
    a = rf.snapshot(clean_repo)
    b = rf.snapshot(clean_repo)
    assert a.content_sha256 == b.content_sha256
    assert a.head_sha == b.head_sha


def test_dirty_worktree_is_refused(clean_repo: pathlib.Path) -> None:
    (clean_repo / "services/api/src/clara_api/glhs/admission.py").write_text(
        "modified\n", encoding="utf-8"
    )
    fp = rf.snapshot(clean_repo)
    assert fp.ok is False
    assert fp.reason_code == "DIRTY_WORKTREE"
    assert "uncommitted" in fp.detail


def test_dirty_worktree_can_be_allowed_explicitly(clean_repo: pathlib.Path) -> None:
    (clean_repo / "scratch.txt").write_text("x\n", encoding="utf-8")
    fp = rf.snapshot(clean_repo, require_clean=False)
    assert fp.ok is True
    assert fp.worktree_clean is False


def test_non_git_directory_is_refused(tmp_path: pathlib.Path) -> None:
    fp = rf.snapshot(tmp_path)
    assert fp.ok is False
    assert fp.reason_code == "NOT_A_GIT_REPO"


def test_missing_required_anchor_is_refused(clean_repo: pathlib.Path) -> None:
    missing = clean_repo / rf.REQUIRED_ANCHOR_FILES[0]
    _git(clean_repo, "rm", "-q", str(missing.relative_to(clean_repo)))
    _git(clean_repo, "commit", "-q", "-m", "remove anchor")
    fp = rf.snapshot(clean_repo)
    assert fp.ok is False
    assert fp.reason_code == "MISSING_REQUIRED_FILE"
    assert rf.REQUIRED_ANCHOR_FILES[0] in fp.missing_required_files


def test_write_fingerprint_roundtrip(clean_repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    import json

    fp = rf.snapshot(clean_repo)
    dest = tmp_path / "out" / "fp.json"
    rf.write_fingerprint(fp, dest)
    payload = json.loads(dest.read_text(encoding="utf-8"))
    assert payload["schema_version"] == rf.REPO_FINGERPRINT_SCHEMA_VERSION
    assert payload["head_sha"] == fp.head_sha
    assert payload["content_sha256"] == fp.content_sha256

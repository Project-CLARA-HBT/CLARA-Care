#!/usr/bin/env python3
"""Comprehensive unit and functional test suite for scripts/ops/worktree_manager.py.

Spec: PH02 / A02 (Data model + migration)
Validates:
  1. Branch naming and worktree path derivation.
  2. Commit SHA verification and error handling.
  3. Worktree enumeration and parsing logic.
  4. Isolation, creation, artifact scaffolding, and zero data cross-talk across workers.
  5. Dirty worktree protection during cleanup.
  6. Force cleanup with branch pruning.
  7. CLI options (--list, --status, --create, --cleanup) and JSON output format.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure scripts/ops is importable
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from worktree_manager import (  # noqa: E402
    WorktreeDirtyError,
    WorktreeValidationError,
    branch_exists,
    cleanup_worktrees,
    create_worktrees,
    get_branch_name,
    get_repo_root,
    get_worktree_path,
    get_worktree_status,
    list_worktrees,
    main,
    parse_phase_and_agent_from_branch,
    parse_phase_and_agent_from_path,
    run_git,
    verify_commit_sha,
)


def test_branch_and_path_naming() -> None:
    """Validate canonical branch naming and worktree path generation."""
    branch = get_branch_name("PH02", "A02")
    assert branch == "phase/ph02-a02"

    root = Path("/dev/shm/clara_worktrees")
    path = get_worktree_path(root, "PH02", "A02")
    assert path == Path("/dev/shm/clara_worktrees/PH02_A02")


def test_parse_phase_and_agent() -> None:
    """Validate extraction of phase and agent identifiers."""
    phase, agent = parse_phase_and_agent_from_branch("phase/ph02-a03")
    assert phase == "PH02"
    assert agent == "A03"

    p_none, a_none = parse_phase_and_agent_from_branch("feature/my-branch")
    assert p_none is None
    assert a_none is None

    phase_p, agent_p = parse_phase_and_agent_from_path("/dev/shm/clara_worktrees/PH40_A07")
    assert phase_p == "PH40"
    assert agent_p == "A07"


def test_verify_commit_sha() -> None:
    """Validate commit SHA checking against the live repository."""
    repo_root = get_repo_root()
    proc = run_git(["rev-parse", "HEAD"], cwd=repo_root)
    head_sha = proc.stdout.strip()

    verified = verify_commit_sha(head_sha, repo_root=repo_root)
    assert verified == head_sha

    # Short SHA resolution
    short_sha = head_sha[:8]
    verified_short = verify_commit_sha(short_sha, repo_root=repo_root)
    assert verified_short == head_sha

    # Non-existent commit
    with pytest.raises(WorktreeValidationError):
        verify_commit_sha("0000000000000000000000000000000000000000", repo_root=repo_root)

    # Empty commit
    with pytest.raises(WorktreeValidationError):
        verify_commit_sha("", repo_root=repo_root)


def test_list_worktrees() -> None:
    """Validate listing active git worktrees."""
    wts = list_worktrees()
    assert len(wts) >= 1
    # First worktree is the primary repository root
    main_wt = [wt for wt in wts if wt.is_main]
    assert len(main_wt) == 1
    assert Path(main_wt[0].path).resolve() == get_repo_root().resolve()


def test_create_isolation_scaffolding_and_cleanup(tmp_path: Path) -> None:
    """End-to-end test of worktree lifecycle, isolation, and safety checks."""
    repo_root = get_repo_root()
    proc = run_git(["rev-parse", "HEAD"], cwd=repo_root)
    base_sha = proc.stdout.strip()

    test_phase = "PHTEST99"
    test_agents = ["T01", "T02"]
    branch_t01 = get_branch_name(test_phase, "T01")
    branch_t02 = get_branch_name(test_phase, "T02")

    # Clean up any leftover test state beforehand
    cleanup_worktrees(
        test_phase,
        repo_root=repo_root,
        worktree_root=tmp_path,
        agents=test_agents,
        force=True,
        delete_branches=True,
    )

    try:
        # Step 1: Create worktrees for two test agents
        created = create_worktrees(
            phase_id=test_phase,
            base_sha=base_sha,
            repo_root=repo_root,
            worktree_root=tmp_path,
            agents=test_agents,
            create_artifact_dirs=True,
        )

        assert len(created) == 2
        wt_t01 = get_worktree_path(tmp_path, test_phase, "T01")
        wt_t02 = get_worktree_path(tmp_path, test_phase, "T02")

        assert wt_t01.exists()
        assert wt_t02.exists()
        assert (wt_t01 / "artifacts" / test_phase / "T01").exists()
        assert (wt_t02 / "artifacts" / test_phase / "T02").exists()

        assert branch_exists(branch_t01, repo_root=repo_root)
        assert branch_exists(branch_t02, repo_root=repo_root)

        # Step 2: Verify zero data cross-talk
        file_in_t01 = wt_t01 / "isolated_note_agent1.txt"
        file_in_t01.write_text("Secret content in Agent 1")

        assert file_in_t01.exists()
        assert not (wt_t02 / "isolated_note_agent1.txt").exists()
        assert not (repo_root / "isolated_note_agent1.txt").exists()

        # Step 3: Check status reports dirty worktree and deliverable status
        status = get_worktree_status(
            test_phase,
            repo_root=repo_root,
            worktree_root=tmp_path,
            agents=test_agents,
        )
        assert status["all_worktrees_exist"] is True
        assert status["all_worktrees_clean"] is False  # T01 has an untracked file
        assert status["all_artifacts_complete"] is False

        # Step 4: Cleanup without force MUST raise WorktreeDirtyError due to uncommitted file
        with pytest.raises(WorktreeDirtyError):
            cleanup_worktrees(
                test_phase,
                repo_root=repo_root,
                worktree_root=tmp_path,
                agents=test_agents,
                force=False,
            )

        # Step 5: Deliverables completion check
        for req in ["change_manifest.json", "test_report.md", "risk_register.md", "rollback.md"]:
            (wt_t02 / "artifacts" / test_phase / "T02" / req).write_text("Dummy content")

        status_after_deliv = get_worktree_status(
            test_phase,
            repo_root=repo_root,
            worktree_root=tmp_path,
            agents=test_agents,
        )
        t02_status = [a for a in status_after_deliv["agents"] if a["agent_id"] == "T02"][0]
        assert t02_status["deliverables_complete"] is True

        # Step 6: Force cleanup removes worktrees and branches
        clean_res = cleanup_worktrees(
            test_phase,
            repo_root=repo_root,
            worktree_root=tmp_path,
            agents=test_agents,
            force=True,
            delete_branches=True,
        )
        assert len(clean_res) == 2
        assert not wt_t01.exists()
        assert not wt_t02.exists()
        assert not branch_exists(branch_t01, repo_root=repo_root)
        assert not branch_exists(branch_t02, repo_root=repo_root)

    finally:
        # Guarantee cleanup even on failure
        cleanup_worktrees(
            test_phase,
            repo_root=repo_root,
            worktree_root=tmp_path,
            agents=test_agents,
            force=True,
            delete_branches=True,
        )


def test_cli_flags_and_json(capsys: pytest.CaptureFixture[str]) -> None:
    """Validate CLI execution with --list, --status, and JSON output."""
    # CLI --list --json
    code = main(["--list", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    listed = json.loads(captured.out)
    assert isinstance(listed, list)
    assert any(item.get("is_main") for item in listed)

    # CLI --status --phase PH02 --json
    code = main(["--status", "--phase", "PH02", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    status_data = json.loads(captured.out)
    assert status_data["phase_id"] == "PH02"
    assert status_data["total_agents"] == 10

    # Missing arguments validation
    code = main(["--create", "--phase", "PH99"])
    assert code == 2  # Missing --base-sha

    code = main(["--status"])
    assert code == 2  # Missing --phase


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))

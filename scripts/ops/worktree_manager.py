#!/usr/bin/env python3
"""Git worktree manager for isolated parallel subagent execution.

Spec: PH02 / A02 (Data model + migration)
Provides isolated git worktrees for 10 concurrent subagents per phase with:
  1. Isolated filesystem paths in /dev/shm (or fallback local directory).
  2. Isolated branch namespace: phase/<phase_id>-<agent_id>.
  3. Pre-scaffolded artifact paths: artifacts/<phase_id>/<agent_id>/.
  4. Non-destructive safety checks preventing data loss on uncommitted changes.
  5. Status reporting and deliverable completeness verification.
  6. Zero data cross-talk between concurrently running subagents.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_AGENTS: list[str] = [
    "A01",
    "A02",
    "A03",
    "A04",
    "A05",
    "A06",
    "A07",
    "A08",
    "A09",
    "A10",
]

DEFAULT_SHM_ROOT = Path("/dev/shm/clara_worktrees")
DEFAULT_LOCAL_ROOT = Path(".worktrees")
REQUIRED_DELIVERABLES = [
    "change_manifest.json",
    "test_report.md",
    "risk_register.md",
    "rollback.md",
]


class WorktreeError(Exception):
    """Base exception for worktree operations."""


class WorktreeValidationError(WorktreeError):
    """Raised when validation of arguments or base SHA fails."""


class WorktreeDirtyError(WorktreeError):
    """Raised when an operation would overwrite or discard uncommitted changes."""


class WorktreeGitError(WorktreeError):
    """Raised when a Git command fails."""


@dataclass
class WorktreeInfo:
    """Metadata describing a Git worktree."""

    path: str
    branch: str
    head_sha: str
    phase_id: str | None = None
    agent_id: str | None = None
    is_clean: bool = True
    exists: bool = True
    is_main: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_default_worktree_root(repo_root: Path | None = None) -> Path:
    """Determine the optimal root path for worktrees.

    Prefers /dev/shm if present and writable (for ramdisk speed and isolation),
    otherwise falls back to .worktrees under repo_root.
    """
    shm_path = Path("/dev/shm")
    if shm_path.exists() and os.access(shm_path, os.W_OK):
        return DEFAULT_SHM_ROOT
    root = repo_root or get_repo_root()
    return root / DEFAULT_LOCAL_ROOT


def run_git(
    args: list[str],
    cwd: Path | str | None = None,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Execute a git command with structured error handling."""
    cmd = ["git"] + args
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            check=check,
            capture_output=capture_output,
            text=True,
        )
        return proc
    except subprocess.CalledProcessError as exc:
        stderr_msg = exc.stderr.strip() if exc.stderr else exc.stdout.strip()
        raise WorktreeGitError(
            f"Git command failed: {' '.join(cmd)} (exit code {exc.returncode}): {stderr_msg}"
        ) from exc


def get_repo_root(cwd: Path | str | None = None) -> Path:
    """Locate the top-level directory of the Git repository."""
    proc = run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    return Path(proc.stdout.strip()).resolve()


def verify_commit_sha(base_sha: str, repo_root: Path | None = None) -> str:
    """Verify that a commit SHA exists and return its full 40-character hash."""
    if not base_sha or not base_sha.strip():
        raise WorktreeValidationError("base_sha cannot be empty")
    cleaned_sha = base_sha.strip()
    try:
        proc = run_git(
            ["rev-parse", "--verify", f"{cleaned_sha}^{{commit}}"],
            cwd=repo_root,
        )
        return proc.stdout.strip()
    except WorktreeGitError as exc:
        raise WorktreeValidationError(
            f"base_sha '{cleaned_sha}' is not a valid commit in the repository: {exc}"
        ) from exc


def get_branch_name(phase_id: str, agent_id: str) -> str:
    """Generate canonical branch name: phase/<phase_id>-<agent_id>."""
    return f"phase/{phase_id.lower()}-{agent_id.lower()}"


def get_worktree_path(worktree_root: Path, phase_id: str, agent_id: str) -> Path:
    """Generate canonical worktree path: <root>/<phase_id>_<agent_id>."""
    return worktree_root / f"{phase_id.upper()}_{agent_id.upper()}"


def check_worktree_clean(worktree_path: Path) -> bool:
    """Check if the given worktree working directory has uncommitted modifications."""
    if not worktree_path.exists() or not (worktree_path / ".git").exists():
        return True
    proc = run_git(["status", "--porcelain"], cwd=worktree_path, check=False)
    return len(proc.stdout.strip()) == 0


def branch_exists(branch: str, repo_root: Path | None = None) -> bool:
    """Check whether a local branch exists."""
    proc = run_git(
        ["rev-parse", "--verify", f"refs/heads/{branch}"],
        cwd=repo_root,
        check=False,
    )
    return proc.returncode == 0


def get_branch_head_sha(branch: str, repo_root: Path | None = None) -> str | None:
    """Get the HEAD commit SHA of a branch, or None if it does not exist."""
    proc = run_git(
        ["rev-parse", "--verify", f"refs/heads/{branch}"],
        cwd=repo_root,
        check=False,
    )
    if proc.returncode == 0:
        return proc.stdout.strip()
    return None


def parse_phase_and_agent_from_branch(branch: str) -> tuple[str | None, str | None]:
    """Parse phase_id and agent_id from a branch name like phase/ph02-a02."""
    match = re.match(r"^phase/([a-zA-Z0-9]+)-([a-zA-Z0-9]+)$", branch)
    if match:
        return match.group(1).upper(), match.group(2).upper()
    return None, None


def parse_phase_and_agent_from_path(path_str: str) -> tuple[str | None, str | None]:
    """Parse phase_id and agent_id from a path like .../PH02_A02."""
    dir_name = Path(path_str).name
    match = re.match(r"^([a-zA-Z0-9]+)_([a-zA-Z0-9]+)$", dir_name)
    if match:
        return match.group(1).upper(), match.group(2).upper()
    return None, None


def list_worktrees(
    *,
    repo_root: Path | str | None = None,
    phase_id: str | None = None,
) -> list[WorktreeInfo]:
    """List all registered Git worktrees with status and metadata."""
    root = Path(repo_root).resolve() if repo_root else get_repo_root()
    proc = run_git(["worktree", "list", "--porcelain"], cwd=root)

    worktrees: list[WorktreeInfo] = []
    current_entry: dict[str, str] = {}
    is_first = True

    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            if current_entry:
                worktrees.append(_build_worktree_info(current_entry, is_main=is_first))
                is_first = False
                current_entry = {}
            continue

        parts = line.split(" ", 1)
        key = parts[0]
        val = parts[1] if len(parts) > 1 else ""
        current_entry[key] = val

    if current_entry:
        worktrees.append(_build_worktree_info(current_entry, is_main=is_first))

    if phase_id:
        target_phase = phase_id.upper()
        worktrees = [wt for wt in worktrees if wt.phase_id and wt.phase_id.upper() == target_phase]

    return worktrees


def _build_worktree_info(raw: dict[str, str], is_main: bool = False) -> WorktreeInfo:
    path_str = raw.get("worktree", "")
    head_sha = raw.get("HEAD", "")
    branch_ref = raw.get("branch", "")
    branch = branch_ref.replace("refs/heads/", "") if branch_ref else ""

    p_branch, a_branch = parse_phase_and_agent_from_branch(branch)
    p_path, a_path = parse_phase_and_agent_from_path(path_str)

    phase = p_branch or p_path
    agent = a_branch or a_path

    wt_path = Path(path_str)
    exists = wt_path.exists()
    is_clean = check_worktree_clean(wt_path) if exists else False

    return WorktreeInfo(
        path=path_str,
        branch=branch,
        head_sha=head_sha,
        phase_id=phase,
        agent_id=agent,
        is_clean=is_clean,
        exists=exists,
        is_main=is_main,
        details={
            "locked": "locked" in raw,
            "prunable": "prunable" in raw,
            "bare": "bare" in raw,
            "detached": "detached" in raw,
        },
    )


def create_worktrees(
    phase_id: str,
    base_sha: str,
    *,
    repo_root: Path | str | None = None,
    worktree_root: Path | str | None = None,
    agents: list[str] | None = None,
    force: bool = False,
    create_artifact_dirs: bool = True,
) -> list[WorktreeInfo]:
    """Create isolated worktrees for each agent in a phase.

    Parameters:
      phase_id: e.g. 'PH02'
      base_sha: Git commit SHA to branch from
      repo_root: Git repo root directory (default auto-detected)
      worktree_root: Base dir for worktrees (default /dev/shm/clara_worktrees or .worktrees)
      agents: list of agent identifiers (default A01..A10)
      force: if True, re-create worktrees/branches even if existing
      create_artifact_dirs: if True, pre-create artifacts/<phase_id>/<agent_id>

    Returns:
      List of WorktreeInfo for all created/verified worktrees.
    """
    if not phase_id or not phase_id.strip():
        raise WorktreeValidationError("phase_id cannot be empty")
    phase_id = phase_id.strip().upper()

    root = Path(repo_root).resolve() if repo_root else get_repo_root()
    verified_sha = verify_commit_sha(base_sha, repo_root=root)

    wt_root = Path(worktree_root).resolve() if worktree_root else get_default_worktree_root(root)
    wt_root.mkdir(parents=True, exist_ok=True)

    agent_list = [a.strip().upper() for a in (agents or DEFAULT_AGENTS)]
    if not agent_list:
        raise WorktreeValidationError("agents list cannot be empty")

    results: list[WorktreeInfo] = []

    for agent_id in agent_list:
        branch = get_branch_name(phase_id, agent_id)
        wt_path = get_worktree_path(wt_root, phase_id, agent_id)

        # Check existing worktree registration
        existing_wts = {wt.path: wt for wt in list_worktrees(repo_root=root)}

        if str(wt_path) in existing_wts:
            existing = existing_wts[str(wt_path)]
            if not force:
                if existing.branch == branch and existing.head_sha == verified_sha:
                    # Idempotent match: already created at target base_sha
                    if create_artifact_dirs:
                        _scaffold_artifacts(wt_path, phase_id, agent_id)
                    results.append(existing)
                    continue
                raise WorktreeError(
                    f"Worktree already exists at {wt_path} (branch={existing.branch}, HEAD={existing.head_sha}). "
                    f"Use force=True to reset."
                )

            # Force cleanup of existing worktree
            run_git(["worktree", "remove", "--force", str(wt_path)], cwd=root, check=False)
            if wt_path.exists():
                shutil.rmtree(wt_path, ignore_errors=True)

        elif wt_path.exists():
            # Directory exists on disk but not in git worktrees
            if not force:
                raise WorktreeError(
                    f"Directory already exists at {wt_path} but is not a registered worktree. "
                    f"Use force=True to overwrite."
                )
            shutil.rmtree(wt_path, ignore_errors=True)

        # Handle branch existence
        b_exists = branch_exists(branch, repo_root=root)
        if b_exists:
            current_head = get_branch_head_sha(branch, repo_root=root)
            if current_head != verified_sha:
                if not force:
                    raise WorktreeError(
                        f"Branch {branch} already exists at {current_head} != {verified_sha}. "
                        f"Use force=True to reset."
                    )
                # Reset existing branch to verified_sha
                run_git(["branch", "-f", branch, verified_sha], cwd=root)
            cmd = ["worktree", "add", str(wt_path), branch]
        else:
            # Create branch from verified base_sha
            cmd = ["worktree", "add", "-b", branch, str(wt_path), verified_sha]

        run_git(cmd, cwd=root)

        # Pre-create artifact scaffold inside worktree
        if create_artifact_dirs:
            _scaffold_artifacts(wt_path, phase_id, agent_id)

        results.append(
            WorktreeInfo(
                path=str(wt_path),
                branch=branch,
                head_sha=verified_sha,
                phase_id=phase_id,
                agent_id=agent_id,
                is_clean=True,
                exists=True,
                is_main=False,
            )
        )

    return results


def _scaffold_artifacts(wt_path: Path, phase_id: str, agent_id: str) -> Path:
    """Create artifacts/<phase_id>/<agent_id> directory in the worktree."""
    artifact_dir = wt_path / "artifacts" / phase_id.upper() / agent_id.upper()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def cleanup_worktrees(
    phase_id: str,
    *,
    repo_root: Path | str | None = None,
    worktree_root: Path | str | None = None,
    agents: list[str] | None = None,
    force: bool = False,
    delete_branches: bool = False,
) -> list[dict[str, Any]]:
    """Remove worktrees for a phase with protection against data loss.

    Parameters:
      phase_id: e.g. 'PH02'
      repo_root: Git repo root directory
      worktree_root: Base dir for worktrees
      agents: list of agent identifiers to clean up (default A01..A10)
      force: if True, delete even if uncommitted changes exist
      delete_branches: if True, also delete corresponding phase branches

    Returns:
      List of dict summaries for each cleanup action.
    """
    if not phase_id or not phase_id.strip():
        raise WorktreeValidationError("phase_id cannot be empty")
    phase_id = phase_id.strip().upper()

    root = Path(repo_root).resolve() if repo_root else get_repo_root()
    agent_list = [a.strip().upper() for a in (agents or DEFAULT_AGENTS)]
    wt_root = Path(worktree_root).resolve() if worktree_root else get_default_worktree_root(root)

    registered = {wt.path: wt for wt in list_worktrees(repo_root=root)}
    results: list[dict[str, Any]] = []

    # First pass: check for dirty worktrees to avoid partial cleanups if force is False
    dirty_trees: list[str] = []
    for agent_id in agent_list:
        wt_path = get_worktree_path(wt_root, phase_id, agent_id)
        if wt_path.exists() and not check_worktree_clean(wt_path):
            dirty_trees.append(str(wt_path))

    if dirty_trees and not force:
        raise WorktreeDirtyError(
            f"Cannot cleanup phase {phase_id}: uncommitted changes found in: {', '.join(dirty_trees)}. "
            f"Use force=True to discard changes."
        )

    for agent_id in agent_list:
        branch = get_branch_name(phase_id, agent_id)
        wt_path = get_worktree_path(wt_root, phase_id, agent_id)
        path_str = str(wt_path)

        removed_worktree = False
        removed_dir = False
        removed_branch = False

        if path_str in registered:
            cmd = ["worktree", "remove"]
            if force:
                cmd.append("--force")
            cmd.append(path_str)
            run_git(cmd, cwd=root, check=False)
            removed_worktree = True

        if wt_path.exists():
            shutil.rmtree(wt_path, ignore_errors=True)
            removed_dir = True

        if delete_branches and branch_exists(branch, repo_root=root):
            run_git(["branch", "-D", branch], cwd=root, check=False)
            removed_branch = True

        results.append(
            {
                "agent_id": agent_id,
                "worktree_path": path_str,
                "branch": branch,
                "removed_worktree": removed_worktree,
                "removed_directory": removed_dir,
                "removed_branch": removed_branch,
            }
        )

    run_git(["worktree", "prune"], cwd=root, check=False)
    return results


def get_worktree_status(
    phase_id: str,
    *,
    repo_root: Path | str | None = None,
    worktree_root: Path | str | None = None,
    agents: list[str] | None = None,
) -> dict[str, Any]:
    """Retrieve detailed status of worktrees and deliverables for a phase."""
    if not phase_id or not phase_id.strip():
        raise WorktreeValidationError("phase_id cannot be empty")
    phase_id = phase_id.strip().upper()

    root = Path(repo_root).resolve() if repo_root else get_repo_root()
    agent_list = [a.strip().upper() for a in (agents or DEFAULT_AGENTS)]
    wt_root = Path(worktree_root).resolve() if worktree_root else get_default_worktree_root(root)

    all_wts = {wt.path: wt for wt in list_worktrees(repo_root=root)}

    agent_statuses: list[dict[str, Any]] = []
    all_exist = True
    all_clean = True
    all_artifacts_complete = True

    for agent_id in agent_list:
        branch = get_branch_name(phase_id, agent_id)
        wt_path = get_worktree_path(wt_root, phase_id, agent_id)
        path_str = str(wt_path)

        wt_info = all_wts.get(path_str)
        exists_on_disk = wt_path.exists()
        is_clean = check_worktree_clean(wt_path) if exists_on_disk else False
        head_sha = (
            wt_info.head_sha if wt_info else (get_branch_head_sha(branch, repo_root=root) or "")
        )

        if not exists_on_disk or not wt_info:
            all_exist = False
        if not is_clean:
            all_clean = False

        # Check deliverable status
        artifact_dir = wt_path / "artifacts" / phase_id / agent_id
        deliverables_found: dict[str, bool] = {}
        for req in REQUIRED_DELIVERABLES:
            found = (artifact_dir / req).exists()
            deliverables_found[req] = found
            if not found:
                all_artifacts_complete = False

        agent_statuses.append(
            {
                "agent_id": agent_id,
                "worktree_path": path_str,
                "branch": branch,
                "registered_in_git": wt_info is not None,
                "exists_on_disk": exists_on_disk,
                "head_sha": head_sha,
                "is_clean": is_clean,
                "artifact_dir": str(artifact_dir),
                "deliverables": deliverables_found,
                "deliverables_complete": all(deliverables_found.values()),
            }
        )

    return {
        "phase_id": phase_id,
        "total_agents": len(agent_list),
        "all_worktrees_exist": all_exist,
        "all_worktrees_clean": all_clean,
        "all_artifacts_complete": all_artifacts_complete,
        "worktree_root": str(wt_root),
        "agents": agent_statuses,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CLARA Parallel Subagent Git Worktree Manager")
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--create",
        action="store_true",
        help="Create isolated worktrees for agents in a phase",
    )
    action_group.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up worktrees for a phase",
    )
    action_group.add_argument(
        "--list",
        action="store_true",
        help="List Git worktrees",
    )
    action_group.add_argument(
        "--status",
        action="store_true",
        help="Show detailed status of worktrees and artifacts for a phase",
    )

    parser.add_argument(
        "--phase",
        type=str,
        default="",
        help="Phase identifier (e.g., PH02, PH40)",
    )
    parser.add_argument(
        "--base-sha",
        type=str,
        default="",
        help="Base commit SHA to anchor worktrees",
    )
    parser.add_argument(
        "--root-dir",
        type=str,
        default="",
        help="Custom root directory for worktrees (defaults to /dev/shm/clara_worktrees or .worktrees)",
    )
    parser.add_argument(
        "--agents",
        type=str,
        default="",
        help="Comma-separated agent list (e.g. A01,A02,A03). Defaults to A01..A10",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-creation or cleanup (discards dirty changes if force cleanup)",
    )
    parser.add_argument(
        "--delete-branches",
        action="store_true",
        help="Delete git branches during cleanup",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON",
    )
    parser.add_argument(
        "--no-artifacts-scaffold",
        action="store_true",
        help="Do not pre-create artifacts/<phase>/<agent> folders during create",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    agents = [a.strip() for a in args.agents.split(",") if a.strip()] if args.agents else None
    root_dir = Path(args.root_dir).resolve() if args.root_dir else None

    try:
        if args.create:
            if not args.phase:
                print("Error: --phase is required for --create", file=sys.stderr)
                return 2
            if not args.base_sha:
                print("Error: --base-sha is required for --create", file=sys.stderr)
                return 2

            results = create_worktrees(
                phase_id=args.phase,
                base_sha=args.base_sha,
                worktree_root=root_dir,
                agents=agents,
                force=args.force,
                create_artifact_dirs=not args.no_artifacts_scaffold,
            )
            if args.json:
                print(json.dumps([wt.to_dict() for wt in results], indent=2))
            else:
                print(
                    f"[worktree_manager] Successfully created {len(results)} worktrees for {args.phase}:"
                )
                for wt in results:
                    print(f"  - {wt.agent_id}: {wt.path} [{wt.branch} @ {wt.head_sha[:8]}]")
            return 0

        if args.cleanup:
            if not args.phase:
                print("Error: --phase is required for --cleanup", file=sys.stderr)
                return 2

            results_clean = cleanup_worktrees(
                phase_id=args.phase,
                worktree_root=root_dir,
                agents=agents,
                force=args.force,
                delete_branches=args.delete_branches,
            )
            if args.json:
                print(json.dumps(results_clean, indent=2))
            else:
                print(f"[worktree_manager] Cleaned up worktrees for {args.phase}:")
                for r in results_clean:
                    print(
                        f"  - {r['agent_id']}: removed_wt={r['removed_worktree']}, "
                        f"removed_dir={r['removed_directory']}, removed_branch={r['removed_branch']}"
                    )
            return 0

        if args.list:
            wts = list_worktrees(phase_id=args.phase if args.phase else None)
            if args.json:
                print(json.dumps([wt.to_dict() for wt in wts], indent=2))
            else:
                print(f"[worktree_manager] Active Git worktrees ({len(wts)} total):")
                for wt in wts:
                    main_tag = " (main)" if wt.is_main else ""
                    clean_tag = "clean" if wt.is_clean else "DIRTY"
                    p_tag = f" [{wt.phase_id}/{wt.agent_id}]" if wt.phase_id else ""
                    print(
                        f"  - {wt.path}{main_tag}: {wt.branch} @ {wt.head_sha[:8]} [{clean_tag}]{p_tag}"
                    )
            return 0

        if args.status:
            if not args.phase:
                print("Error: --phase is required for --status", file=sys.stderr)
                return 2

            status = get_worktree_status(
                phase_id=args.phase,
                worktree_root=root_dir,
                agents=agents,
            )
            if args.json:
                print(json.dumps(status, indent=2))
            else:
                print(f"[worktree_manager] Status for Phase {status['phase_id']}:")
                print(f"  All worktrees exist:    {status['all_worktrees_exist']}")
                print(f"  All worktrees clean:    {status['all_worktrees_clean']}")
                print(f"  Deliverables complete:  {status['all_artifacts_complete']}")
                print("  Agents:")
                for ag in status["agents"]:
                    wt_clean = "clean" if ag["is_clean"] else "DIRTY"
                    deliv_ok = "COMPLETE" if ag["deliverables_complete"] else "INCOMPLETE"
                    print(
                        f"    - {ag['agent_id']}: branch={ag['branch']} ({wt_clean}) deliverables={deliv_ok}"
                    )
            return 0

    except (WorktreeError, WorktreeValidationError, WorktreeDirtyError) as err:
        print(f"[worktree_manager] Error: {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

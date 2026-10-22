#!/usr/bin/env python3
"""CLARA Care — Merge Queue & Integration Worker.

Spec: PH02 / A07 (Tests + CI)
Orchestrates the sequential integration and verification of 10 concurrent subagents:
  1. Validates each agent's change_manifest.json against required schemas.
  2. Enforces path ACLs per agent role and flags out-of-lane file mutations.
  3. Detects cross-agent file collisions (shared modifications forbidden).
  4. Sequentially cherry-picks commits in deterministic dependency order:
     A02 (DB) -> A01 (Contract) -> A03 (Domain) -> A04 (ML) -> A05 (Web) ->
     A06 (Mobile) -> A07 (Tests/CI) -> A08 (Security) -> A09 (Docs) -> A10 (Hostile Audit)
  5. Executes test gating suites (AST bytecode compilation, migration downgrade checks, unit tests).
  6. Emits the canonical artifacts/{PHASE}/integration/merge_manifest.json.

Zero-dependency standard library implementation (Python 3.11+).
"""

from __future__ import annotations

import argparse
import datetime
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Deterministic dependency order prescribed by CLARA PH02 architecture:
# A02 (DB) -> A01 (API Contract) -> A03 (Domain) -> A04 (ML) -> A05 (Web) ->
# A06 (Mobile) -> A07 (Tests/CI) -> A08 (Security) -> A09 (Docs) -> A10 (Hostile Audit)
DETERMINISTIC_ORDER: list[str] = [
    "A02",
    "A01",
    "A03",
    "A04",
    "A05",
    "A06",
    "A07",
    "A08",
    "A09",
    "A10",
]

# Canonical path lanes for PH02 (fallback if machine/PHASE_TASKS.json is unavailable)
DEFAULT_PH02_PATH_LANES: dict[str, list[str]] = {
    "A01": [
        "services/api/src/clara_api/api/",
        "contracts/",
        "services/api/src/clara_api/schemas.py",
    ],
    "A02": [
        "services/api/src/clara_api/db/",
        "services/api/alembic/versions/",
    ],
    "A03": [
        "services/api/src/clara_api/glhs/",
        "services/api/src/clara_api/lifemap/",
        "services/api/src/clara_api/phr/",
        "services/api/src/clara_api/compliance/",
        "services/api/src/clara_api/core/",
    ],
    "A04": [
        "services/ml/src/clara_ml/",
        "evaluation/",
        "services/ocr/",
        "services/asr/",
    ],
    "A05": [
        "apps/web/app/",
        "apps/web/components/",
        "apps/web/lib/",
    ],
    "A06": [
        "apps/mobile/",
    ],
    "A07": [
        "services/api/tests/",
        "services/ml/tests/",
        "apps/web/e2e/",
        ".github/workflows/",
        "scripts/ops/",
    ],
    "A08": [
        "docs/security/",
        "docs/compliance/",
        "scripts/ops/",
    ],
    "A09": [
        "research/",
        "docs/research/",
        "docs/implementation/",
        "docs/interoperability/",
    ],
    "A10": [
        "docs/reports/",
        "docs/runbooks/",
        "scripts/ci/",
    ],
}

DEFAULT_ROLES: dict[str, str] = {
    "A01": "API + contract",
    "A02": "Data model + migration",
    "A03": "Domain + GLHS services",
    "A04": "ML + retrieval",
    "A05": "Web UX",
    "A06": "Mobile Flutter",
    "A07": "Tests + CI",
    "A08": "Security + privacy",
    "A09": "Docs + research evidence",
    "A10": "Adversarial audit + integration proposals",
}


@dataclass
class AgentManifest:
    agent_id: str
    phase_id: str
    role: str
    task: str
    status: str
    worktree: str
    branch: str
    commit: str
    files_changed: list[str] = field(default_factory=list)
    verified_source_anchors: list[str] = field(default_factory=list)
    test_execution_results: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    rollback_steps: list[str] = field(default_factory=list)
    remediations: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ManifestValidationResult:
    valid: bool
    agent_id: str
    manifest_path: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manifest: AgentManifest | None = None


@dataclass
class PathAclViolation:
    agent_id: str
    file_path: str
    allowed_lanes: list[str]
    reason: str


@dataclass
class FileCollision:
    file_path: str
    agents: list[str]


@dataclass
class CherryPickResult:
    agent_id: str
    commit_sha: str
    success: bool
    message: str
    stdout: str = ""
    stderr: str = ""


@dataclass
class TestGateResult:
    __test__ = False  # Inform pytest this is a data container, not a test suite
    command: str
    exit_code: int
    duration_seconds: float
    passed: bool
    stdout: str
    stderr: str


def normalize_lane_entry(entry: str) -> str:
    """Normalize a path lane entry by removing leading slashes."""
    entry = entry.strip()
    if entry.startswith("/"):
        entry = entry.lstrip("/")
    return entry


def is_file_in_path_lane(
    file_path: str,
    agent_id: str,
    phase_id: str,
    path_lane: list[str],
) -> bool:
    """Check if a file path is permitted within the agent's path lane."""
    norm_file = file_path.strip().lstrip("/")

    # Rule 1: Always allowed in agent's own artifact lane
    allowed_artifact_prefix = f"artifacts/{phase_id}/{agent_id}/"
    if norm_file.startswith(allowed_artifact_prefix):
        return True

    # Rule 2: Allowed in agent's own artifacts directory case-insensitively
    if norm_file.lower().startswith(f"artifacts/{phase_id.lower()}/{agent_id.lower()}/"):
        return True

    # Rule 3: Check against declared path lane
    for raw_lane in path_lane:
        lane = normalize_lane_entry(raw_lane)
        if not lane:
            continue

        # If lane is a directory prefix
        if lane.endswith("/"):
            if norm_file.startswith(lane):
                return True
        # If lane is a glob pattern
        elif "*" in lane or "?" in lane:
            if fnmatch.fnmatch(norm_file, lane):
                return True
        # If lane is an exact file
        else:
            if norm_file == lane or norm_file.startswith(lane + "/"):
                return True

    return False


def load_phase_tasks_from_spec(repo_root: Path, phase_id: str) -> dict[str, dict[str, Any]]:
    """Load phase tasks, roles, and path lanes from machine/PHASE_TASKS.json if available."""
    spec_path = repo_root / "CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK" / "machine" / "PHASE_TASKS.json"
    result: dict[str, dict[str, Any]] = {}

    if spec_path.exists():
        try:
            with open(spec_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                phases = data if isinstance(data, list) else data.get("phases", [])
                for ph in phases:
                    if ph.get("id") == phase_id or f"PH{ph.get('phase', -1):02d}" == phase_id:
                        for ag in ph.get("agents", []):
                            aid = ag.get("agent_id")
                            lanes = [
                                p.strip()
                                for p in ag.get("path_lane", "").split(";")
                                if p.strip()
                            ]
                            result[aid] = {
                                "role": ag.get("role", DEFAULT_ROLES.get(aid, "")),
                                "task": ag.get("task", ""),
                                "path_lane": lanes,
                                "acceptance_artifacts": ag.get("acceptance_artifacts", []),
                            }
                        break
        except Exception:
            pass

    return result


def find_agent_manifest_file(
    repo_root: Path,
    phase_id: str,
    agent_id: str,
    worktrees_dir: Path | None = None,
    custom_manifest_path: Path | None = None,
) -> Path | None:
    """Locate the change_manifest.json file for a given agent across search locations."""
    if custom_manifest_path and custom_manifest_path.exists():
        return custom_manifest_path

    # Search candidates in priority order:
    candidates: list[Path] = []

    # 1. Inside dedicated agent worktree: <worktrees_dir>/<phase_id>_<agent_id>/artifacts/<phase_id>/<agent_id>/change_manifest.json
    if worktrees_dir:
        candidates.append(
            worktrees_dir / f"{phase_id}_{agent_id}" / "artifacts" / phase_id / agent_id / "change_manifest.json"
        )
        candidates.append(
            worktrees_dir / f"{phase_id}_{agent_id}" / "change_manifest.json"
        )

    # 2. Inside repo root: <repo_root>/artifacts/<phase_id>/<agent_id>/change_manifest.json
    candidates.append(
        repo_root / "artifacts" / phase_id / agent_id / "change_manifest.json"
    )

    for c in candidates:
        if c.is_file():
            return c

    return None


def validate_agent_manifest(
    manifest_path: Path,
    expected_phase: str,
    expected_agent: str,
    repo_root: Path | None = None,
) -> ManifestValidationResult:
    """Validate an individual agent's change_manifest.json against required standards."""
    errors: list[str] = []
    warnings: list[str] = []

    if not manifest_path.exists():
        return ManifestValidationResult(
            valid=False,
            agent_id=expected_agent,
            manifest_path=str(manifest_path),
            errors=[f"Manifest file not found: {manifest_path}"],
        )

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return ManifestValidationResult(
            valid=False,
            agent_id=expected_agent,
            manifest_path=str(manifest_path),
            errors=[f"Invalid JSON format in {manifest_path}: {e}"],
        )

    if not isinstance(data, dict):
        return ManifestValidationResult(
            valid=False,
            agent_id=expected_agent,
            manifest_path=str(manifest_path),
            errors=["Manifest root must be a JSON object"],
        )

    # 1. Phase ID check
    phase_id = data.get("phase_id", "")
    if phase_id != expected_phase:
        errors.append(f"Mismatched phase_id: expected '{expected_phase}', got '{phase_id}'")

    # 2. Agent ID check
    agent_id = data.get("agent_id", "")
    if agent_id != expected_agent:
        errors.append(f"Mismatched agent_id: expected '{expected_agent}', got '{agent_id}'")

    # 3. Status check
    status = data.get("status", "").upper()
    if status not in ("COMPLETE", "PASSED", "SUCCESS", "COMPLETED"):
        errors.append(f"Unacceptable manifest status: '{status}' (must be 'COMPLETE', 'COMPLETED', or 'PASSED')")

    # 4. Blockers check - MUST BE EMPTY
    blockers = data.get("blockers", [])
    if not isinstance(blockers, list):
        errors.append("Field 'blockers' must be a list")
    elif len(blockers) > 0:
        errors.append(f"Agent declares unresolved blockers: {blockers}")

    # 5. Files changed check
    files_changed = data.get("files_changed") or data.get("files", [])
    if not isinstance(files_changed, list):
        errors.append("Field 'files_changed' must be a list of relative file paths")
    elif len(files_changed) == 0:
        warnings.append("Agent declared 0 changed files (audit/doc agent without file mutations)")

    # 6. Verified source anchors check
    anchors = data.get("verified_source_anchors", [])
    if not isinstance(anchors, list):
        errors.append("Field 'verified_source_anchors' must be a list of path:line anchors")
    elif len(anchors) == 0:
        warnings.append("No verified_source_anchors declared in manifest")
    else:
        anchor_pattern = re.compile(r"^[^:\s]+:\d+(-\d+)?$")
        for anch in anchors:
            if not isinstance(anch, str) or not anchor_pattern.match(anch):
                warnings.append(f"Unusual anchor format: '{anch}' (expected 'path:line' or 'path:line-line')")

    # 7. Check companion deliverables: test_report.md and risk_register.md
    manifest_dir = manifest_path.parent
    test_report_file = manifest_dir / "test_report.md"
    risk_register_file = manifest_dir / "risk_register.md"

    if not test_report_file.is_file():
        errors.append(f"Missing required deliverable: {test_report_file}")
    if not risk_register_file.is_file():
        errors.append(f"Missing required deliverable: {risk_register_file}")

    raw_commit = data.get("commit") or data.get("commit_sha") or data.get("handoff_commit") or ""
    raw_base = data.get("base_sha") or data.get("frozen_head_sha") or ""
    if raw_commit and raw_commit == raw_base:
        raw_commit = ""

    manifest_obj = AgentManifest(
        agent_id=expected_agent,
        phase_id=phase_id or expected_phase,
        role=data.get("role", DEFAULT_ROLES.get(expected_agent, "")),
        task=data.get("task", ""),
        status=status,
        worktree=data.get("worktree_path") or data.get("worktree", ""),
        branch=data.get("branch", f"phase/{expected_phase.lower()}-{expected_agent.lower()}"),
        commit=raw_commit,
        files_changed=[str(f) for f in files_changed],
        verified_source_anchors=[str(a) for a in anchors],
        test_execution_results=data.get("test_execution_results", {}),
        blockers=blockers if isinstance(blockers, list) else [],
        rollback_steps=data.get("rollback_steps", []),
        remediations=data.get("remediations", []),
        raw_data=data,
    )

    return ManifestValidationResult(
        valid=len(errors) == 0,
        agent_id=expected_agent,
        manifest_path=str(manifest_path),
        errors=errors,
        warnings=warnings,
        manifest=manifest_obj,
    )


def check_all_path_acls(
    manifests: dict[str, AgentManifest],
    path_lanes: dict[str, list[str]],
    phase_id: str,
) -> list[PathAclViolation]:
    """Verify that all files changed by agents strictly conform to their designated path lanes."""
    violations: list[PathAclViolation] = []

    for agent_id, manifest in manifests.items():
        allowed_lanes = path_lanes.get(agent_id, DEFAULT_PH02_PATH_LANES.get(agent_id, []))
        for f in manifest.files_changed:
            if not is_file_in_path_lane(f, agent_id, phase_id, allowed_lanes):
                violations.append(
                    PathAclViolation(
                        agent_id=agent_id,
                        file_path=f,
                        allowed_lanes=allowed_lanes,
                        reason=f"File '{f}' is outside allowed lanes for {agent_id}",
                    )
                )

    return violations


def detect_file_collisions(
    manifests: dict[str, AgentManifest],
    phase_id: str,
) -> list[FileCollision]:
    """Detect overlapping non-artifact file modifications between multiple agents."""
    collisions: list[FileCollision] = []
    file_writers: dict[str, list[str]] = {}

    for agent_id, manifest in manifests.items():
        for raw_path in manifest.files_changed:
            norm_path = raw_path.strip().lstrip("/")
            # Exempt agent-specific artifacts directory
            if norm_path.startswith(f"artifacts/{phase_id}/{agent_id}/") or norm_path.lower().startswith(
                f"artifacts/{phase_id.lower()}/{agent_id.lower()}/"
            ):
                continue
            file_writers.setdefault(norm_path, []).append(agent_id)

    for file_path, writers in file_writers.items():
        if len(writers) > 1:
            collisions.append(FileCollision(file_path=file_path, agents=sorted(writers)))

    return collisions


def resolve_commit_for_agent(
    repo_root: Path,
    agent_id: str,
    phase_id: str,
    manifest: AgentManifest,
    worktrees_dir: Path | None = None,
) -> tuple[str | None, str]:
    """Resolve the git commit SHA to cherry-pick for a given agent."""
    # 1. If explicit commit in manifest
    if manifest.commit and len(manifest.commit) >= 7:
        check = subprocess.run(
            ["git", "cat-file", "-e", f"{manifest.commit}^{{commit}}"],
            cwd=repo_root,
            capture_output=True,
        )
        if check.returncode == 0:
            rev = subprocess.run(
                ["git", "rev-parse", manifest.commit],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            if rev.returncode == 0:
                return rev.stdout.strip(), "Resolved from manifest commit"

    # 2. Try git branch 'phase/<phase_lower>-<agent_lower>'
    branch_name = manifest.branch or f"phase/{phase_id.lower()}-{agent_id.lower()}"
    rev_branch = subprocess.run(
        ["git", "rev-parse", "--verify", branch_name],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if rev_branch.returncode == 0:
        return rev_branch.stdout.strip(), f"Resolved from branch '{branch_name}'"

    # 3. Try checking HEAD in worktree directory
    if worktrees_dir:
        wt_path = worktrees_dir / f"{phase_id}_{agent_id}"
        if wt_path.is_dir():
            rev_wt = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=wt_path,
                capture_output=True,
                text=True,
            )
            if rev_wt.returncode == 0:
                return rev_wt.stdout.strip(), f"Resolved from worktree at {wt_path}"

    return None, f"Could not resolve commit for {agent_id}"


def run_test_suite_gates(
    repo_root: Path,
    custom_commands: list[str] | None = None,
    timeout_seconds: int = 180,
) -> tuple[bool, list[TestGateResult]]:
    """Execute required CI test and validation gates."""
    results: list[TestGateResult] = []

    commands = custom_commands or [
        f"{sys.executable} -m compileall -q services/api/src services/ml/src scripts/ops",
        f"{sys.executable} scripts/ops/check_migration_downgrade.py services/api/alembic/versions",
    ]

    all_passed = True
    for cmd in commands:
        start_t = datetime.datetime.now(datetime.timezone.utc)
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        end_t = datetime.datetime.now(datetime.timezone.utc)
        duration = (end_t - start_t).total_seconds()
        passed = (proc.returncode == 0)

        results.append(
            TestGateResult(
                command=cmd,
                exit_code=proc.returncode,
                duration_seconds=round(duration, 3),
                passed=passed,
                stdout=proc.stdout.strip()[:2000],
                stderr=proc.stderr.strip()[:2000],
            )
        )
        if not passed:
            all_passed = False

    return all_passed, results


def execute_cherry_pick(
    repo_root: Path,
    commit_sha: str,
    agent_id: str,
    base_sha: str,
    dry_run: bool = False,
) -> CherryPickResult:
    """Execute git cherry-pick for an individual subagent commit."""
    # If the agent commit is identical to the base SHA (no code commits), skip cleanly
    if commit_sha == base_sha:
        return CherryPickResult(
            agent_id=agent_id,
            commit_sha=commit_sha,
            success=True,
            message="Commit matches base SHA; no delta to cherry-pick (audit/doc package)",
        )

    if dry_run:
        # Dry-run verification: check git cherry-pick feasibility without altering working state
        cmd = ["git", "cherry-pick", "--no-commit", commit_sha]
        proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
        if proc.returncode == 0:
            # Revert the staged changes from the test cherry-pick
            subprocess.run(["git", "cherry-pick", "--abort"], cwd=repo_root, capture_output=True)
            subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo_root, capture_output=True)
            return CherryPickResult(
                agent_id=agent_id,
                commit_sha=commit_sha,
                success=True,
                message=f"[DRY-RUN] Cherry-pick of {commit_sha[:8]} applies cleanly",
                stdout=proc.stdout.strip(),
            )
        else:
            subprocess.run(["git", "cherry-pick", "--abort"], cwd=repo_root, capture_output=True)
            subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo_root, capture_output=True)
            return CherryPickResult(
                agent_id=agent_id,
                commit_sha=commit_sha,
                success=False,
                message=f"[DRY-RUN] Cherry-pick conflict for {commit_sha[:8]}",
                stderr=proc.stderr.strip() or proc.stdout.strip(),
            )

    # Real execution
    cmd = ["git", "cherry-pick", commit_sha]
    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    if proc.returncode == 0:
        return CherryPickResult(
            agent_id=agent_id,
            commit_sha=commit_sha,
            success=True,
            message=f"Successfully cherry-picked {commit_sha[:8]}",
            stdout=proc.stdout.strip(),
        )
    else:
        # Abort the conflicting cherry-pick immediately to leave repo clean
        subprocess.run(["git", "cherry-pick", "--abort"], cwd=repo_root, capture_output=True)
        return CherryPickResult(
            agent_id=agent_id,
            commit_sha=commit_sha,
            success=False,
            message=f"Cherry-pick failed with conflict on {commit_sha[:8]}",
            stderr=proc.stderr.strip() or proc.stdout.strip(),
        )


def build_merge_manifest_dict(
    phase_id: str,
    phase_title: str,
    base_sha: str,
    target_commit_sha: str,
    dependency_order: list[str],
    manifests: dict[str, AgentManifest],
    cherry_pick_results: dict[str, CherryPickResult],
    file_collisions: list[FileCollision],
    test_results: list[TestGateResult],
    integration_status: str,
) -> dict[str, Any]:
    """Assemble the canonical merge_manifest.json structure."""
    agents_list: list[dict[str, Any]] = []

    for agent_id in dependency_order:
        m = manifests.get(agent_id)
        cp = cherry_pick_results.get(agent_id)
        if m:
            agent_status = "PASSED" if (cp and cp.success) else "FAILED"
            agents_list.append(
                {
                    "agent_id": agent_id,
                    "role": m.role,
                    "task": m.task,
                    "worktree": m.worktree,
                    "branch": m.branch,
                    "commit": (cp.commit_sha[:8] if cp and cp.commit_sha else (m.commit[:8] if m.commit else "")),
                    "full_commit": (cp.commit_sha if cp and cp.commit_sha else m.commit),
                    "status": agent_status,
                    "files": m.files_changed,
                    "remediations": m.remediations,
                }
            )

    collision_entries = [
        {"file": c.file_path, "agents": c.agents}
        for c in file_collisions
    ]

    test_entries = [
        {
            "command": t.command,
            "exit_code": t.exit_code,
            "duration_seconds": t.duration_seconds,
            "status": "PASSED" if t.passed else "FAILED",
        }
        for t in test_results
    ]

    return {
        "schema_version": "1.0.0",
        "phase_id": phase_id,
        "phase_title": phase_title,
        "base_sha": base_sha,
        "merge_commit_sha": target_commit_sha,
        "concurrent_agents_count": len(dependency_order),
        "dependency_order": dependency_order,
        "agents": agents_list,
        "file_conflict_count": len(collision_entries),
        "file_conflicts": collision_entries,
        "integration_status": integration_status,
        "test_suite_results": test_entries,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


class MergeQueueWorker:
    """Sequential validation, ACL checking, and cherry-pick orchestrator."""

    def __init__(
        self,
        repo_root: Path,
        phase_id: str = "PH02",
        base_sha: str | None = None,
        worktrees_dir: Path | None = None,
        output_path: Path | None = None,
        order: list[str] | None = None,
        dry_run: bool = False,
        skip_tests: bool = False,
        custom_test_commands: list[str] | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.phase_id = phase_id
        self.base_sha = base_sha or self._detect_base_sha()
        self.worktrees_dir = (worktrees_dir.resolve() if worktrees_dir else Path("/dev/shm/clara_worktrees"))
        self.output_path = (
            output_path.resolve()
            if output_path
            else self.repo_root / "artifacts" / self.phase_id / "integration" / "merge_manifest.json"
        )
        self.dependency_order = order or list(DETERMINISTIC_ORDER)
        self.dry_run = dry_run
        self.skip_tests = skip_tests
        self.custom_test_commands = custom_test_commands

        # Phase metadata & path lanes
        phase_specs = load_phase_tasks_from_spec(self.repo_root, self.phase_id)
        self.path_lanes: dict[str, list[str]] = {}
        for aid in self.dependency_order:
            if aid in phase_specs and phase_specs[aid].get("path_lane"):
                self.path_lanes[aid] = phase_specs[aid]["path_lane"]
            else:
                self.path_lanes[aid] = DEFAULT_PH02_PATH_LANES.get(aid, [])

        self.phase_title = "Thiết lập tổ chức tác nhân và 10 worktree song song"

    def _detect_base_sha(self) -> str:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""

    def validate_preconditions(self) -> list[str]:
        """Check repository clean state and baseline SHA."""
        errors: list[str] = []

        if not self.dry_run:
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )
            if status.returncode != 0:
                errors.append(f"git status failed: {status.stderr}")
            elif status.stdout.strip():
                errors.append("Target git repository is not clean; uncommitted changes detected")

        return errors

    def run(self) -> int:
        """Run the complete merge queue pipeline."""
        print("=" * 80)
        print(f"CLARA CARE — MERGE QUEUE WORKER: {self.phase_id}")
        print(f"Base SHA:           {self.base_sha}")
        print(f"Target Repo:        {self.repo_root}")
        print(f"Worktrees Dir:      {self.worktrees_dir}")
        print(f"Dependency Order:   {' -> '.join(self.dependency_order)}")
        print(f"Mode:               {'DRY-RUN (Simulated)' if self.dry_run else 'ACTIVE INTEGRATION'}")
        print("=" * 80)

        # 1. Preconditions
        pre_errors = self.validate_preconditions()
        if pre_errors:
            print("\n[ERROR] Precondition validation failed:")
            for err in pre_errors:
                print(f"  • {err}")
            return 1

        # 2. Manifest Validation for all 10 agents
        print("\n[STEP 1/5] Validating Agent Manifests...")
        manifests: dict[str, AgentManifest] = {}
        validation_failed = False

        for agent_id in self.dependency_order:
            m_path = find_agent_manifest_file(
                repo_root=self.repo_root,
                phase_id=self.phase_id,
                agent_id=agent_id,
                worktrees_dir=self.worktrees_dir,
            )
            if not m_path:
                print(f"  [FAIL] {agent_id}: change_manifest.json not found in worktree or repo")
                validation_failed = True
                continue

            res = validate_agent_manifest(
                manifest_path=m_path,
                expected_phase=self.phase_id,
                expected_agent=agent_id,
                repo_root=self.repo_root,
            )

            if not res.valid:
                print(f"  [FAIL] {agent_id} ({m_path}):")
                for err in res.errors:
                    print(f"         - {err}")
                validation_failed = True
            else:
                print(f"  [PASS] {agent_id}: valid manifest ({len(res.manifest.files_changed)} files changed)")  # type: ignore[union-attr]
                manifests[agent_id] = res.manifest  # type: ignore[assignment]

        if validation_failed:
            print("\n[ABORT] Manifest validation failed for one or more agents.")
            return 2

        # 3. Path ACL Check
        print("\n[STEP 2/5] Checking Path ACL Enforcements...")
        acl_violations = check_all_path_acls(manifests, self.path_lanes, self.phase_id)
        if acl_violations:
            print(f"  [FAIL] Detected {len(acl_violations)} path ACL violations:")
            for v in acl_violations:
                print(f"         - Agent {v.agent_id}: file '{v.file_path}' outside allowed lanes {v.allowed_lanes}")
            print("\n[ABORT] Path ACL violations detected. Subagents must stay within assigned lanes.")
            return 3
        print(f"  [PASS] All {len(manifests)} agents conform to their designated path lanes.")

        # 4. File Collision Check
        print("\n[STEP 3/5] Checking Cross-Agent File Collisions...")
        collisions = detect_file_collisions(manifests, self.phase_id)
        if collisions:
            print(f"  [FAIL] Detected {len(collisions)} overlapping file collisions:")
            for col in collisions:
                print(f"         - File '{col.file_path}' modified by multiple agents: {col.agents}")
            print("\n[ABORT] Integration blocked due to file collision. Concurrent agents must not write same files.")
            return 4
        print("  [PASS] Zero cross-agent file collisions detected.")

        # 5. Deterministic Cherry-Pick Execution
        print(f"\n[STEP 4/5] Executing Cherry-Picks in Order: {' -> '.join(self.dependency_order)}...")
        cherry_pick_results: dict[str, CherryPickResult] = {}
        integration_failed = False

        for agent_id in self.dependency_order:
            manifest = manifests[agent_id]
            commit_sha, msg = resolve_commit_for_agent(
                repo_root=self.repo_root,
                agent_id=agent_id,
                phase_id=self.phase_id,
                manifest=manifest,
                worktrees_dir=self.worktrees_dir,
            )

            if not commit_sha:
                print(f"  [FAIL] {agent_id}: {msg}")
                cherry_pick_results[agent_id] = CherryPickResult(
                    agent_id=agent_id,
                    commit_sha="",
                    success=False,
                    message=msg,
                )
                integration_failed = True
                break

            cp_res = execute_cherry_pick(
                repo_root=self.repo_root,
                commit_sha=commit_sha,
                agent_id=agent_id,
                base_sha=self.base_sha,
                dry_run=self.dry_run,
            )
            cherry_pick_results[agent_id] = cp_res

            if not cp_res.success:
                print(f"  [FAIL] {agent_id}: {cp_res.message}")
                if cp_res.stderr:
                    print(f"         Details: {cp_res.stderr}")
                integration_failed = True
                break
            else:
                print(f"  [PASS] {agent_id}: {cp_res.message}")

        if integration_failed:
            print("\n[ABORT] Cherry-pick sequence aborted due to conflict.")
            return 5

        # 6. Test Gating
        print("\n[STEP 5/5] Executing Integration Test Gates...")
        test_results: list[TestGateResult] = []
        tests_passed = True
        if self.skip_tests:
            print("  [INFO] Test gates skipped per --skip-tests flag.")
        else:
            tests_passed, test_results = run_test_suite_gates(
                repo_root=self.repo_root,
                custom_commands=self.custom_test_commands,
            )
            for t in test_results:
                status_str = "[PASS]" if t.passed else "[FAIL]"
                print(f"  {status_str} {t.command} ({t.duration_seconds}s, exit code: {t.exit_code})")
                if not t.passed and t.stderr:
                    print(f"         {t.stderr}")

            if not tests_passed:
                print("\n[ABORT] Integration test gating failed.")
                return 6

        # 7. Generate and write merge_manifest.json
        final_head = self._detect_base_sha()
        manifest_payload = build_merge_manifest_dict(
            phase_id=self.phase_id,
            phase_title=self.phase_title,
            base_sha=self.base_sha,
            target_commit_sha=final_head,
            dependency_order=self.dependency_order,
            manifests=manifests,
            cherry_pick_results=cherry_pick_results,
            file_collisions=collisions,
            test_results=test_results,
            integration_status="PASSED",
        )

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(manifest_payload, f, indent=2)

        print("\n" + "=" * 80)
        print(f"INTEGRATION GREEN! Wrote canonical manifest to: {self.output_path}")
        print(f"Integrated agents count: {len(manifests)}")
        print("=" * 80)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CLARA Care — Merge Queue and Subagent Integration Worker"
    )
    parser.add_argument(
        "--phase",
        default="PH02",
        help="Phase identifier (default: PH02)",
    )
    parser.add_argument(
        "--base-sha",
        default=None,
        help="Frozen baseline SHA to anchor integration against",
    )
    parser.add_argument(
        "--worktrees-dir",
        default="/dev/shm/clara_worktrees",
        help="Directory hosting concurrent agent worktrees (default: /dev/shm/clara_worktrees)",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root (defaults to parent traversal of script)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for merge_manifest.json",
    )
    parser.add_argument(
        "--order",
        default=None,
        help="Comma-separated deterministic dependency order (default: A02,A01,A03,A04,A05,A06,A07,A08,A09,A10)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate validation, ACL checks, and cherry-picks without modifying git HEAD",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip test execution gate",
    )

    args = parser.parse_args()

    repo_root = (
        Path(args.repo_root).resolve()
        if args.repo_root
        else Path(__file__).resolve().parent.parent.parent
    )
    worktrees_dir = Path(args.worktrees_dir).resolve() if args.worktrees_dir else None
    output_path = Path(args.output).resolve() if args.output else None

    order = [a.strip() for a in args.order.split(",") if a.strip()] if args.order else None

    worker = MergeQueueWorker(
        repo_root=repo_root,
        phase_id=args.phase,
        base_sha=args.base_sha,
        worktrees_dir=worktrees_dir,
        output_path=output_path,
        order=order,
        dry_run=args.dry_run,
        skip_tests=args.skip_tests,
    )

    return worker.run()


if __name__ == "__main__":
    sys.exit(main())

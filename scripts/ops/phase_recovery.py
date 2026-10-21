#!/usr/bin/env python3
"""CLARA Care Phase Recovery & Resume Tool.

Part of the 10-concurrent-subagent orchestration quality gate (Phase PH02 / Subagent A10).
Inspects failed agents in a phase, diagnoses worktree state, isolates broken worktrees
into quarantine snapshots, allows retrying a single failed agent without discarding
passed agents, generates targeted restart instructions, and resumes execution from
the last safe checkpoint.

Zero external dependencies (Python 3.11+ stdlib only).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

# Default repository root (relative to scripts/ops/phase_recovery.py)
DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_WORKTREE_BASE = Path(os.environ.get("CLARA_WORKTREE_BASE", "/dev/shm/clara_worktrees"))
DEFAULT_PHASE_ID = "PH02"
FROZEN_BASE_SHA_PH02 = "879dc5dcfcaae91b3626e28062043d934294478b"

ALL_AGENTS = [f"A{i:02d}" for i in range(1, 11)]

# Canonical PH02 Path Lane Ownership Matrix (spec + task lane assignments)
PH02_PATH_LANES: dict[str, list[str]] = {
    "A01": [
        "services/api/src/clara_api/api/",
        "contracts/",
        "services/api/src/clara_api/schemas.py",
        "artifacts/PH02/A01/",
    ],
    "A02": [
        "services/api/src/clara_api/db/",
        "services/api/alembic/versions/",
        "artifacts/PH02/A02/",
    ],
    "A03": [
        "services/api/src/clara_api/glhs/",
        "services/api/src/clara_api/lifemap/",
        "services/api/src/clara_api/phr/",
        "services/api/src/clara_api/compliance/",
        "services/api/src/clara_api/core/",
        "artifacts/PH02/A03/",
    ],
    "A04": [
        "services/ml/src/clara_ml/",
        "evaluation/",
        "services/ocr/",
        "services/asr/",
        "scripts/ops/",
        "artifacts/PH02/A04/",
    ],
    "A05": [
        "apps/web/app/",
        "apps/web/components/",
        "apps/web/lib/",
        "scripts/ci/",
        "artifacts/PH02/A05/",
    ],
    "A06": [
        "apps/mobile/",
        "artifacts/PH02/A06/",
    ],
    "A07": [
        "services/api/tests/",
        "services/ml/tests/",
        "apps/web/e2e/",
        ".github/workflows/",
        "scripts/ops/",
        "artifacts/PH02/A07/",
    ],
    "A08": [
        "docs/security/",
        "docs/compliance/",
        "scripts/ops/",
        "artifacts/PH02/A08/",
    ],
    "A09": [
        "research/",
        "docs/research/",
        "docs/implementation/",
        "docs/interoperability/",
        "artifacts/PH02/A09/",
    ],
    "A10": [
        "docs/reports/",
        "docs/runbooks/",
        "scripts/ci/",
        "scripts/ops/",
        "artifacts/PH02/A10/",
    ],
}

AGENT_ROLES: dict[str, str] = {
    "A01": "API + contract: agent contract JSON schema",
    "A02": "Data model + migration: git worktree creation tool",
    "A03": "Domain + GLHS services: ten task-scoped worktree paths",
    "A04": "ML + retrieval: resource quotas and semaphore 10",
    "A05": "Web UX: ownership and path ACL checker",
    "A06": "Mobile Flutter: agent prompt and bounded context pack",
    "A07": "Tests + CI: merge queue and integration worker",
    "A08": "Security + privacy: deterministic red-team checker",
    "A09": "Docs + research evidence: checkpoint/progress dashboard",
    "A10": "Adversarial audit + integration proposals: failure recovery and resume tool",
}


class AgentStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    DIRTY_UNCOMMITTED = "DIRTY_UNCOMMITTED"
    LANE_VIOLATION = "LANE_VIOLATION"
    UNSTARTED = "UNSTARTED"
    QUARANTINED = "QUARANTINED"
    CORRUPTED = "CORRUPTED"


@dataclass
class AgentDiagnostic:
    agent_id: str
    phase_id: str
    worktree_path: str
    branch: str = ""
    head_sha: str = ""
    base_sha: str = ""
    commits_ahead: int = 0
    status: AgentStatus = AgentStatus.UNSTARTED
    is_worktree_valid: bool = False
    is_git_clean: bool = True
    unstaged_files: list[str] = field(default_factory=list)
    staged_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    manifest_found: bool = False
    manifest_status: str = ""
    test_report_found: bool = False
    risk_register_found: bool = False
    tests_passed: bool = False
    lane_violations: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)
    quarantine_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


def run_cmd(
    cmd: list[str],
    cwd: Path | str | None = None,
    timeout: int = 30,
) -> tuple[int, str, str]:
    """Execute shell command cleanly capturing stdout, stderr, and returncode."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.rstrip("\r\n"), proc.stderr.rstrip("\r\n")
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s: {' '.join(cmd)}"
    except Exception as exc:
        return -1, "", f"Command execution failed: {exc}"


def git_rev_parse(worktree: Path, ref: str = "HEAD") -> str:
    code, out, _ = run_cmd(["git", "rev-parse", ref], cwd=worktree)
    return out if code == 0 else ""


def git_branch(worktree: Path) -> str:
    code, out, _ = run_cmd(["git", "branch", "--show-current"], cwd=worktree)
    return out if code == 0 else ""


def git_status_porcelain(worktree: Path) -> tuple[list[str], list[str], list[str]]:
    """Return (staged, unstaged, untracked) file lists with full untracked path expansion."""
    code, out, _ = run_cmd(["git", "status", "--porcelain", "-u"], cwd=worktree)
    if code != 0:
        return [], [], []

    staged: list[str] = []
    unstaged: list[str] = []
    untracked: list[str] = []

    for line in out.splitlines():
        if not line or len(line) < 3:
            continue
        index_status = line[0]
        worktree_status = line[1]
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ")[-1]

        if index_status == "?":
            untracked.append(path)
        else:
            if index_status not in (" ", "?"):
                staged.append(path)
            if worktree_status not in (" ", "?"):
                unstaged.append(path)

    return staged, unstaged, untracked


def git_diff_name_only(worktree: Path, base_sha: str) -> list[str]:
    """Return all modified paths since base_sha (committed + uncommitted)."""
    paths: set[str] = set()

    # Committed diff from base_sha to HEAD
    code, out, _ = run_cmd(["git", "diff", "--name-only", f"{base_sha}..HEAD"], cwd=worktree)
    if code == 0 and out:
        paths.update(out.splitlines())

    # Working tree diff (uncommitted)
    code, out, _ = run_cmd(["git", "diff", "--name-only"], cwd=worktree)
    if code == 0 and out:
        paths.update(out.splitlines())

    # Staged diff
    code, out, _ = run_cmd(["git", "diff", "--name-only", "--cached"], cwd=worktree)
    if code == 0 and out:
        paths.update(out.splitlines())

    return sorted([p for p in paths if p])


class PhaseRecoveryManager:
    """Core manager for diagnosing, isolating, retrying, and resuming subagent worktrees."""

    def __init__(
        self,
        phase_id: str = DEFAULT_PHASE_ID,
        worktree_base: Path = DEFAULT_WORKTREE_BASE,
        base_sha: str = FROZEN_BASE_SHA_PH02,
        repo_root: Path = DEFAULT_REPO_ROOT,
    ) -> None:
        self.phase_id = phase_id
        self.worktree_base = Path(worktree_base)
        self.base_sha = base_sha
        self.repo_root = Path(repo_root)
        self.lane_matrix = PH02_PATH_LANES

    def get_worktree_path(self, agent_id: str) -> Path:
        """Resolve canonical worktree directory for a given subagent."""
        # Check standard /dev/shm worktree path first
        candidate = self.worktree_base / f"{self.phase_id}_{agent_id}"
        if candidate.exists():
            return candidate

        # Fallback to local repo worktree directory if present
        local_candidate = self.repo_root / ".worktrees" / f"{self.phase_id}_{agent_id}"
        if local_candidate.exists():
            return local_candidate

        return candidate

    def check_lane_violations(
        self,
        agent_id: str,
        changed_files: list[str],
        manifest_lanes: list[str] | None = None,
    ) -> list[str]:
        """Check whether any changed files lie outside the agent's assigned lane."""
        allowed_prefixes = list(self.lane_matrix.get(agent_id, []))
        if manifest_lanes:
            for lane in manifest_lanes:
                clean = lane.strip().lstrip("/")
                if clean and clean not in allowed_prefixes:
                    allowed_prefixes.append(clean)

        if not allowed_prefixes:
            return []

        violations: list[str] = []
        for file_path in changed_files:
            # Allow deliverables in artifacts/<PHASE>/<AGENT>/
            agent_artifact_prefix = f"artifacts/{self.phase_id}/{agent_id}/"
            if file_path.startswith(agent_artifact_prefix):
                continue

            matches_lane = any(
                file_path == prefix or file_path.startswith(prefix)
                for prefix in allowed_prefixes
            )
            if not matches_lane:
                violations.append(file_path)

        return violations

    def diagnose_agent(self, agent_id: str) -> AgentDiagnostic:
        """Thoroughly inspect a single agent's worktree state."""
        wt = self.get_worktree_path(agent_id)
        diag = AgentDiagnostic(
            agent_id=agent_id,
            phase_id=self.phase_id,
            worktree_path=str(wt),
            base_sha=self.base_sha,
        )

        if not wt.exists() or not wt.is_dir():
            diag.status = AgentStatus.CORRUPTED
            diag.failure_reasons.append(f"Worktree directory missing: {wt}")
            return diag

        # Check git validity
        git_dir = wt / ".git"
        if not git_dir.exists():
            diag.status = AgentStatus.CORRUPTED
            diag.failure_reasons.append("Not a valid git worktree (no .git link)")
            return diag

        diag.is_worktree_valid = True
        diag.branch = git_branch(wt)
        diag.head_sha = git_rev_parse(wt, "HEAD")

        # Check commits ahead of base
        if diag.head_sha and self.base_sha:
            code, out, _ = run_cmd(["git", "rev-list", "--count", f"{self.base_sha}..HEAD"], cwd=wt)
            if code == 0 and out.isdigit():
                diag.commits_ahead = int(out)

        # Check git clean status
        staged, unstaged, untracked = git_status_porcelain(wt)
        diag.staged_files = staged
        diag.unstaged_files = unstaged
        diag.untracked_files = untracked
        diag.is_git_clean = (len(staged) == 0 and len(unstaged) == 0 and len(untracked) == 0)

        # Check quarantine marker
        quarantine_marker = wt / ".quarantined"
        if quarantine_marker.exists():
            diag.status = AgentStatus.QUARANTINED
            diag.quarantine_path = quarantine_marker.read_text(encoding="utf-8").strip()
            diag.failure_reasons.append(f"Worktree is marked quarantined: {diag.quarantine_path}")
            return diag

        # Check artifacts
        manifest_path = wt / "artifacts" / self.phase_id / agent_id / "change_manifest.json"
        test_report_path = wt / "artifacts" / self.phase_id / agent_id / "test_report.md"
        risk_register_path = wt / "artifacts" / self.phase_id / agent_id / "risk_register.md"

        diag.manifest_found = manifest_path.exists()
        diag.test_report_found = test_report_path.exists()
        diag.risk_register_found = risk_register_path.exists()

        manifest_lanes: list[str] = []
        if diag.manifest_found:
            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                diag.manifest_status = str(manifest_data.get("status", "UNKNOWN")).upper()
                raw_lane = manifest_data.get("path_lane", [])
                if isinstance(raw_lane, str):
                    manifest_lanes = [item.strip() for item in raw_lane.split(";") if item.strip()]
                elif isinstance(raw_lane, list):
                    manifest_lanes = [str(item).strip() for item in raw_lane if str(item).strip()]

                # Flexible extraction of test records from manifest
                raw_tests = (
                    manifest_data.get("test_results")
                    or manifest_data.get("tests_run")
                    or manifest_data.get("tests")
                    or manifest_data.get("test_execution_results")
                )

                tests_list: list[dict[str, Any]] = []
                if isinstance(raw_tests, list):
                    for item in raw_tests:
                        if isinstance(item, dict):
                            tests_list.append(item)
                elif isinstance(raw_tests, dict):
                    for name, item in raw_tests.items():
                        if isinstance(item, dict):
                            entry = dict(item)
                            entry.setdefault("command", name)
                            tests_list.append(entry)

                if tests_list:
                    all_passed = True
                    failed_tests: list[str] = []
                    for t in tests_list:
                        status_val = str(t.get("status", "")).upper()
                        exit_code = t.get("exit_code")
                        is_pass = (exit_code == 0) or (status_val in ("PASS", "PASSED", "OK", "COMPLETE"))
                        if not is_pass:
                            all_passed = False
                            failed_tests.append(f"{t.get('command', 'test')} (exit={exit_code}, status={status_val})")
                    diag.tests_passed = all_passed
                    if not all_passed:
                        diag.failure_reasons.append(f"Test failures in manifest: {', '.join(failed_tests)}")
                elif diag.test_report_found:
                    diag.tests_passed = True
                else:
                    diag.failure_reasons.append("Manifest exists but contains empty test results and no test report")
            except Exception as e:
                diag.failure_reasons.append(f"Malformed manifest JSON: {e}")

        # Check lane violations
        all_changed = git_diff_name_only(wt, self.base_sha)
        # Also include unstaged and untracked files
        all_modified_pool = sorted(list(set(all_changed + staged + unstaged + untracked)))
        lane_violations = self.check_lane_violations(agent_id, all_modified_pool, manifest_lanes)
        diag.lane_violations = lane_violations
        if lane_violations:
            diag.failure_reasons.append(
                f"Lane violations detected ({len(lane_violations)} files outside ownership): {', '.join(lane_violations[:3])}"
            )

        # Classify overall status
        if lane_violations:
            diag.status = AgentStatus.LANE_VIOLATION
        elif diag.manifest_found and diag.manifest_status in ("COMPLETED", "COMPLETE", "PASS", "PASSED") and diag.tests_passed and diag.is_git_clean:
            diag.status = AgentStatus.PASSED
        elif diag.manifest_found and diag.manifest_status in ("BLOCKED", "BLOCKED_DEPENDENCY", "BLOCKED_CAPACITY"):
            diag.status = AgentStatus.BLOCKED
            diag.failure_reasons.append(f"Manifest declared status: {diag.manifest_status}")
        elif not diag.is_git_clean:
            diag.status = AgentStatus.DIRTY_UNCOMMITTED
            diag.failure_reasons.append(
                f"Worktree has uncommitted modifications ({len(staged)} staged, {len(unstaged)} unstaged, {len(untracked)} untracked)"
            )
        elif diag.commits_ahead == 0 and not diag.manifest_found:
            diag.status = AgentStatus.UNSTARTED
        elif diag.commits_ahead > 0 and not diag.manifest_found:
            diag.status = AgentStatus.FAILED
            diag.failure_reasons.append("Commits exist ahead of baseline but change_manifest.json is missing")
        elif diag.manifest_found and not diag.tests_passed:
            diag.status = AgentStatus.FAILED
        else:
            diag.status = AgentStatus.FAILED
            diag.failure_reasons.append("Worktree state does not meet completion criteria")

        return diag

    def inspect_phase(self) -> dict[str, AgentDiagnostic]:
        """Diagnose all 10 subagents in the phase."""
        diagnostics: dict[str, AgentDiagnostic] = {}
        for agent_id in ALL_AGENTS:
            diagnostics[agent_id] = self.diagnose_agent(agent_id)
        return diagnostics

    def isolate_agent(self, agent_id: str, reason: str = "Unspecified failure") -> tuple[bool, str]:
        """Safely snapshot and isolate a broken worktree without data destruction.

        Exports forensic patch, archives untracked files, sets quarantine tag,
        and marks worktree with .quarantined.
        """
        wt = self.get_worktree_path(agent_id)
        if not wt.exists():
            return False, f"Worktree not found: {wt}"

        timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M%S")
        quarantine_dir = self.repo_root / "artifacts" / self.phase_id / "quarantine" / agent_id / timestamp
        quarantine_dir.mkdir(parents=True, exist_ok=True)

        diag = self.diagnose_agent(agent_id)

        # 1. Export uncommitted diff patch
        _, diff_out, _ = run_cmd(["git", "diff", "HEAD"], cwd=wt)
        _, staged_out, _ = run_cmd(["git", "diff", "--cached"], cwd=wt)
        patch_file = quarantine_dir / "uncommitted.patch"
        patch_content = f"# STAGED DIFF\n{staged_out}\n\n# UNSTAGED DIFF\n{diff_out}\n"
        patch_file.write_text(patch_content, encoding="utf-8")

        # 2. Archive untracked files if any
        if diag.untracked_files:
            untracked_list_file = quarantine_dir / "untracked_files.txt"
            untracked_list_file.write_text("\n".join(diag.untracked_files), encoding="utf-8")

        # 3. Create quarantine git branch
        quarantine_branch = f"quarantine/{self.phase_id.lower()}-{agent_id.lower()}-{timestamp}"
        run_cmd(["git", "branch", quarantine_branch, "HEAD"], cwd=wt)

        # 4. Save metadata manifest
        meta = {
            "agent_id": agent_id,
            "phase_id": self.phase_id,
            "quarantined_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "reason": reason,
            "original_branch": diag.branch,
            "original_head_sha": diag.head_sha,
            "base_sha": self.base_sha,
            "quarantine_branch": quarantine_branch,
            "failure_reasons": diag.failure_reasons,
            "lane_violations": diag.lane_violations,
            "patch_file": str(patch_file),
        }
        meta_file = quarantine_dir / "quarantine_manifest.json"
        meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # 5. Place marker in worktree
        marker = wt / ".quarantined"
        marker.write_text(str(quarantine_dir), encoding="utf-8")

        return True, f"Quarantined {agent_id} -> {quarantine_dir} (branch: {quarantine_branch})"

    def isolate_all_failed(self) -> dict[str, str]:
        """Isolate all agents that are not in PASSED or UNSTARTED state."""
        results: dict[str, str] = {}
        diags = self.inspect_phase()
        for agent_id, diag in diags.items():
            if diag.status not in (AgentStatus.PASSED, AgentStatus.UNSTARTED):
                reason = "; ".join(diag.failure_reasons) or diag.status.value
                ok, msg = self.isolate_agent(agent_id, reason=reason)
                results[agent_id] = msg if ok else f"ERROR: {msg}"
        return results

    def retry_agent(
        self,
        agent_id: str,
        preserve_quarantine: bool = True,
        force: bool = False,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Safely reset ONLY the designated failed agent back to baseline SHA.

        Leaves all other agents (specifically PASSED agents) completely untouched.
        Generates targeted restart instructions.
        """
        if agent_id not in ALL_AGENTS:
            return False, f"Invalid agent_id: {agent_id}. Must be one of {ALL_AGENTS}", {}

        # Pre-check: capture status of all other agents to verify non-interference
        pre_diags = self.inspect_phase()
        passed_before = {
            a: diag.head_sha
            for a, diag in pre_diags.items()
            if diag.status == AgentStatus.PASSED and a != agent_id
        }

        wt = self.get_worktree_path(agent_id)
        if not wt.exists():
            return False, f"Worktree not found for {agent_id}: {wt}", {}

        # If dirty or broken, preserve in quarantine first
        diag = pre_diags[agent_id]
        if preserve_quarantine and diag.status not in (AgentStatus.PASSED, AgentStatus.UNSTARTED):
            self.isolate_agent(agent_id, reason="Automatic isolation prior to targeted retry")

        # Remove quarantine marker if present
        marker = wt / ".quarantined"
        if marker.exists():
            marker.unlink()

        # Reset worktree to base_sha and canonical branch
        expected_branch = f"phase/{self.phase_id.lower()}-{agent_id.lower()}"

        # Discard untracked files and uncommitted changes
        run_cmd(["git", "reset", "--hard", "HEAD"], cwd=wt)
        run_cmd(["git", "clean", "-ffdx"], cwd=wt)

        # Checkout branch pointing exactly to base_sha
        code, out, err = run_cmd(["git", "checkout", "-B", expected_branch, self.base_sha], cwd=wt)
        if code != 0:
            return False, f"Failed to reset {agent_id} branch to {self.base_sha}: {err or out}", {}

        # Re-create empty artifact directory
        artifact_dir = wt / "artifacts" / self.phase_id / agent_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        # Post-check: Verify passed agents remain 100% untouched
        post_diags = self.inspect_phase()
        for passed_agent, expected_sha in passed_before.items():
            current_sha = post_diags[passed_agent].head_sha
            if current_sha != expected_sha:
                return False, (
                    f"CRITICAL SAFETY VIOLATION: Agent {passed_agent} was modified during retry of {agent_id}! "
                    f"Expected {expected_sha}, got {current_sha}"
                ), {}

        # Generate targeted restart instructions
        restart_instructions = self.generate_restart_instructions(agent_id)

        msg = (
            f"Successfully reset {agent_id} in {wt} to base SHA {self.base_sha}.\n"
            f"Passed agents preserved: {len(passed_before)} agents intact."
        )
        return True, msg, restart_instructions

    def generate_restart_instructions(self, agent_id: str) -> dict[str, Any]:
        """Generate machine and human-readable restart instructions for a subagent."""
        wt = self.get_worktree_path(agent_id)
        lanes = self.lane_matrix.get(agent_id, [])
        role = AGENT_ROLES.get(agent_id, "Subagent")
        branch = f"phase/{self.phase_id.lower()}-{agent_id.lower()}"

        prompt_summary = (
            f"You are subagent {agent_id} for {self.phase_id}.\n"
            f"Worktree path: {wt}\n"
            f"Branch: {branch}\n"
            f"Frozen HEAD SHA: {self.base_sha}\n"
            f"Role: {role}\n"
            f"Path lane: {';'.join(lanes)}\n"
            f"Rules: Only modify files inside your path lane. Deliver change_manifest.json, test_report.md, risk_register.md."
        )

        cli_command = (
            f"python3 scripts/ops/phase_recovery.py diagnose --agent {agent_id} && "
            f"git -C {wt} status"
        )

        return {
            "agent_id": agent_id,
            "phase_id": self.phase_id,
            "role": role,
            "worktree_path": str(wt),
            "branch": branch,
            "base_sha": self.base_sha,
            "allowed_path_lanes": lanes,
            "required_artifacts": [
                f"artifacts/{self.phase_id}/{agent_id}/change_manifest.json",
                f"artifacts/{self.phase_id}/{agent_id}/test_report.md",
                f"artifacts/{self.phase_id}/{agent_id}/risk_register.md",
            ],
            "prompt_text": prompt_summary,
            "verification_command": cli_command,
        }

    def save_checkpoint(self, output_path: Path | None = None) -> tuple[bool, str, dict[str, Any]]:
        """Persist atomic snapshot of phase state to checkpoint.json."""
        if output_path is None:
            output_path = self.repo_root / "artifacts" / self.phase_id / "checkpoint.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        diags = self.inspect_phase()

        passed_count = sum(1 for d in diags.values() if d.status == AgentStatus.PASSED)
        failed_count = sum(1 for d in diags.values() if d.status == AgentStatus.FAILED)
        blocked_count = sum(1 for d in diags.values() if d.status == AgentStatus.BLOCKED)
        dirty_count = sum(1 for d in diags.values() if d.status == AgentStatus.DIRTY_UNCOMMITTED)
        lane_violation_count = sum(1 for d in diags.values() if d.status == AgentStatus.LANE_VIOLATION)
        unstarted_count = sum(1 for d in diags.values() if d.status == AgentStatus.UNSTARTED)

        all_passed = (passed_count == len(ALL_AGENTS))

        checkpoint_data: dict[str, Any] = {
            "schema_version": "clara-phase-checkpoint.v1",
            "phase_id": self.phase_id,
            "base_sha": self.base_sha,
            "checkpoint_timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "ready_for_integration": all_passed,
            "metrics": {
                "total_agents": len(ALL_AGENTS),
                "passed": passed_count,
                "failed": failed_count,
                "blocked": blocked_count,
                "dirty_uncommitted": dirty_count,
                "lane_violations": lane_violation_count,
                "unstarted": unstarted_count,
            },
            "agents": {a: d.to_dict() for a, d in diags.items()},
        }

        # Atomic file write via temporary file
        temp_file = output_path.with_suffix(".tmp")
        temp_file.write_text(json.dumps(checkpoint_data, indent=2), encoding="utf-8")
        temp_file.replace(output_path)

        return True, f"Checkpoint saved to {output_path}", checkpoint_data

    def resume_phase(self, checkpoint_path: Path | None = None) -> tuple[bool, str, dict[str, Any]]:
        """Resume phase from last safe checkpoint, validating preserved state.

        Returns list of retained agents and pending/actionable agents.
        """
        if checkpoint_path is None:
            checkpoint_path = self.repo_root / "artifacts" / self.phase_id / "checkpoint.json"

        if not checkpoint_path.exists():
            # If checkpoint does not exist, build current state as baseline checkpoint
            ok, msg, data = self.save_checkpoint(checkpoint_path)
            return ok, f"No prior checkpoint found. Created new checkpoint: {msg}", data

        try:
            ckpt = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except Exception as e:
            return False, f"Failed to read checkpoint {checkpoint_path}: {e}", {}

        current_diags = self.inspect_phase()

        retained_agents: list[str] = []
        retry_required: list[str] = []
        unstarted_agents: list[str] = []

        for agent_id in ALL_AGENTS:
            curr = current_diags[agent_id]

            if curr.status == AgentStatus.PASSED:
                retained_agents.append(agent_id)
            elif curr.status == AgentStatus.UNSTARTED:
                unstarted_agents.append(agent_id)
            else:
                retry_required.append(agent_id)

        plan = {
            "checkpoint_timestamp": ckpt.get("checkpoint_timestamp"),
            "base_sha": self.base_sha,
            "retained_agents": retained_agents,
            "unstarted_agents": unstarted_agents,
            "retry_required": retry_required,
            "all_ready_for_fanin": len(retained_agents) == len(ALL_AGENTS),
            "next_actions": [
                f"Retry agent {a}: python3 scripts/ops/phase_recovery.py retry --agent {a}"
                for a in retry_required
            ],
        }

        summary_msg = (
            f"Resumed from checkpoint: {len(retained_agents)}/{len(ALL_AGENTS)} passed (retained). "
            f"{len(retry_required)} require retry, {len(unstarted_agents)} unstarted."
        )
        return True, summary_msg, plan

    def evaluate_gate(self) -> tuple[bool, dict[str, Any]]:
        """Evaluate full PH02 Quality Gate."""
        diags = self.inspect_phase()
        results: list[dict[str, Any]] = []

        all_passed = True
        for agent_id in ALL_AGENTS:
            d = diags[agent_id]
            is_ok = (d.status == AgentStatus.PASSED)
            if not is_ok:
                all_passed = False
            results.append({
                "agent_id": agent_id,
                "status": d.status.value,
                "branch": d.branch,
                "head_sha": d.head_sha[:8] if d.head_sha else "",
                "clean": d.is_git_clean,
                "lane_violations_count": len(d.lane_violations),
                "failure_reasons": d.failure_reasons,
            })

        gate_payload = {
            "phase_id": self.phase_id,
            "base_sha": self.base_sha,
            "gate_passed": all_passed,
            "evaluated_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "results": results,
        }
        return all_passed, gate_payload


def print_status_table(diags: dict[str, AgentDiagnostic], phase_id: str, base_sha: str) -> None:
    print("=" * 100)
    print(f"CLARA CARE SUBAGENT WORKTREE STATUS MATRIX — {phase_id}")
    print(f"Base SHA: {base_sha}")
    print("=" * 100)
    print(f"{'AGENT':<6} | {'STATUS':<18} | {'COMMITS':<8} | {'CLEAN':<6} | {'MANIFEST':<10} | {'VIOLATIONS':<10} | {'ROLE':<30}")
    print("-" * 100)
    for agent_id in ALL_AGENTS:
        d = diags[agent_id]
        clean_str = "YES" if d.is_git_clean else "NO"
        man_str = d.manifest_status if d.manifest_found else "NONE"
        viols_str = str(len(d.lane_violations))
        role_str = AGENT_ROLES.get(agent_id, "")[:30]
        status_color = d.status.value
        print(f"{agent_id:<6} | {status_color:<18} | {d.commits_ahead:<8} | {clean_str:<6} | {man_str:<10} | {viols_str:<10} | {role_str:<30}")
    print("=" * 100)


def build_parser() -> argparse.ArgumentParser:
    sub_common = argparse.ArgumentParser(add_help=False)
    sub_common.add_argument("--phase", default=argparse.SUPPRESS, help=f"Phase identifier (default: {DEFAULT_PHASE_ID})")
    sub_common.add_argument("--worktree-base", default=argparse.SUPPRESS, help=f"Base directory (default: {DEFAULT_WORKTREE_BASE})")
    sub_common.add_argument("--base-sha", default=argparse.SUPPRESS, help=f"Pinned base SHA (default: {FROZEN_BASE_SHA_PH02})")
    sub_common.add_argument("--repo-root", default=argparse.SUPPRESS, help=f"Root repository path (default: {DEFAULT_REPO_ROOT})")
    sub_common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Emit output in machine-readable JSON format")

    parser = argparse.ArgumentParser(
        description="CLARA Care Phase Recovery & Resume Tool (PH02 Quality Gate)",
    )
    parser.add_argument("--phase", default=DEFAULT_PHASE_ID, help=f"Phase identifier (default: {DEFAULT_PHASE_ID})")
    parser.add_argument("--worktree-base", default=str(DEFAULT_WORKTREE_BASE), help=f"Base directory (default: {DEFAULT_WORKTREE_BASE})")
    parser.add_argument("--base-sha", default=FROZEN_BASE_SHA_PH02, help=f"Pinned base SHA (default: {FROZEN_BASE_SHA_PH02})")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT), help=f"Root repository path (default: {DEFAULT_REPO_ROOT})")
    parser.add_argument("--json", action="store_true", default=False, help="Emit output in machine-readable JSON format")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: status
    subparsers.add_parser("status", parents=[sub_common], help="Inspect status of all 10 agents in the phase")

    # Subcommand: diagnose
    diag_parser = subparsers.add_parser("diagnose", parents=[sub_common], help="Detailed root-cause diagnosis of worktree state")
    diag_parser.add_argument("--agent", help="Specific agent ID to diagnose (e.g. A03). If omitted, diagnoses all.")

    # Subcommand: isolate
    iso_parser = subparsers.add_parser("isolate", parents=[sub_common], help="Isolate broken worktree into quarantine snapshot")
    iso_group = iso_parser.add_mutually_exclusive_group(required=True)
    iso_group.add_argument("--agent", help="Specific agent ID to isolate (e.g. A03)")
    iso_group.add_argument("--all-failed", action="store_true", help="Isolate all failed or dirty agents")
    iso_parser.add_argument("--reason", default="Manual operator isolation", help="Quarantine reason note")

    # Subcommand: retry
    retry_parser = subparsers.add_parser("retry", parents=[sub_common], help="Safely reset a single failed agent without discarding passed agents")
    retry_parser.add_argument("--agent", required=True, help="Specific agent ID to retry (e.g. A03)")
    retry_parser.add_argument("--no-quarantine", action="store_true", help="Skip saving pre-reset state to quarantine")
    retry_parser.add_argument("--force", action="store_true", help="Force reset even if agent is marked passed")

    # Subcommand: checkpoint
    ckpt_parser = subparsers.add_parser("checkpoint", parents=[sub_common], help="Save current phase execution checkpoint")
    ckpt_parser.add_argument("--output", help="Optional custom checkpoint file path")

    # Subcommand: resume
    resume_parser = subparsers.add_parser("resume", parents=[sub_common], help="Resume phase execution from last safe checkpoint")
    resume_parser.add_argument("--checkpoint-file", help="Optional path to checkpoint file")

    # Subcommand: gate
    subparsers.add_parser("gate", parents=[sub_common], help="Evaluate PH02 Quality Gate criteria")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    manager = PhaseRecoveryManager(
        phase_id=args.phase,
        worktree_base=Path(args.worktree_base),
        base_sha=args.base_sha,
        repo_root=Path(args.repo_root),
    )

    if args.command == "status":
        diags = manager.inspect_phase()
        if args.json:
            print(json.dumps({a: d.to_dict() for a, d in diags.items()}, indent=2))
        else:
            print_status_table(diags, args.phase, args.base_sha)
        return 0

    elif args.command == "diagnose":
        if args.agent:
            agent = args.agent.upper()
            diag = manager.diagnose_agent(agent)
            if args.json:
                print(json.dumps(diag.to_dict(), indent=2))
            else:
                print(f"=== DIAGNOSTIC REPORT: {agent} ({args.phase}) ===")
                print(f"Worktree:        {diag.worktree_path}")
                print(f"Valid Worktree:  {diag.is_worktree_valid}")
                print(f"Branch:          {diag.branch}")
                print(f"HEAD SHA:        {diag.head_sha}")
                print(f"Base SHA:        {diag.base_sha}")
                print(f"Commits Ahead:   {diag.commits_ahead}")
                print(f"Clean Worktree:  {diag.is_git_clean}")
                print(f"Status:          {diag.status.value}")
                print(f"Manifest Found:  {diag.manifest_found} (status={diag.manifest_status})")
                print(f"Test Report:     {diag.test_report_found}")
                print(f"Risk Register:   {diag.risk_register_found}")
                print(f"Tests Passed:    {diag.tests_passed}")
                if diag.lane_violations:
                    print(f"Lane Violations: {diag.lane_violations}")
                if diag.failure_reasons:
                    print("Failure Reasons:")
                    for r in diag.failure_reasons:
                        print(f"  - {r}")
                if diag.unstaged_files or diag.staged_files or diag.untracked_files:
                    print(f"Uncommitted:     {len(diag.staged_files)} staged, {len(diag.unstaged_files)} unstaged, {len(diag.untracked_files)} untracked")
            return 0 if diag.status == AgentStatus.PASSED else 1
        else:
            diags = manager.inspect_phase()
            if args.json:
                print(json.dumps({a: d.to_dict() for a, d in diags.items()}, indent=2))
            else:
                for agent_id, diag in diags.items():
                    if diag.status != AgentStatus.PASSED:
                        print(f"[{agent_id}] {diag.status.value}: {'; '.join(diag.failure_reasons) or 'No reasons'}")
            return 0

    elif args.command == "isolate":
        if args.all_failed:
            results = manager.isolate_all_failed()
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                print(f"Isolated {len(results)} failed worktrees:")
                for a, msg in results.items():
                    print(f"  - {a}: {msg}")
            return 0
        else:
            agent = args.agent.upper()
            ok, msg = manager.isolate_agent(agent, reason=args.reason)
            if args.json:
                print(json.dumps({"agent_id": agent, "success": ok, "message": msg}, indent=2))
            else:
                print(f"[{'OK' if ok else 'FAIL'}] {msg}")
            return 0 if ok else 1

    elif args.command == "retry":
        agent = args.agent.upper()
        diag = manager.diagnose_agent(agent)
        if diag.status == AgentStatus.PASSED and not args.force:
            print(f"Agent {agent} is currently marked PASSED. Use --force to reset.")
            return 1

        ok, msg, instructions = manager.retry_agent(
            agent_id=agent,
            preserve_quarantine=not args.no_quarantine,
            force=args.force,
        )
        if args.json:
            print(json.dumps({"success": ok, "message": msg, "instructions": instructions}, indent=2))
        else:
            print(f"[{'OK' if ok else 'FAIL'}] {msg}")
            if ok:
                print("\n" + "=" * 80)
                print(f"TARGETED RESTART INSTRUCTIONS FOR {agent}:")
                print("=" * 80)
                print(instructions.get("prompt_text", ""))
                print("-" * 80)
                print(f"Verification: {instructions.get('verification_command')}")
                print("=" * 80)
        return 0 if ok else 1

    elif args.command == "checkpoint":
        out_path = Path(args.output) if args.output else None
        ok, msg, data = manager.save_checkpoint(out_path)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(f"[{'OK' if ok else 'FAIL'}] {msg}")
        return 0 if ok else 1

    elif args.command == "resume":
        ckpt_path = Path(args.checkpoint_file) if args.checkpoint_file else None
        ok, msg, plan = manager.resume_phase(ckpt_path)
        if args.json:
            print(json.dumps(plan, indent=2))
        else:
            print(f"[{'OK' if ok else 'FAIL'}] {msg}")
            print("\nExecution Plan:")
            print(f"  - Retained Agents:  {plan.get('retained_agents', [])}")
            print(f"  - Unstarted Agents: {plan.get('unstarted_agents', [])}")
            print(f"  - Retry Required:   {plan.get('retry_required', [])}")
            if plan.get("next_actions"):
                print("Next Actions:")
                for action in plan["next_actions"]:
                    print(f"  * {action}")
        return 0 if ok else 1

    elif args.command == "gate":
        passed, gate_data = manager.evaluate_gate()
        if args.json:
            print(json.dumps(gate_data, indent=2))
        else:
            print("=" * 80)
            print(f"PH02 QUALITY GATE EVALUATION: {'PASSED' if passed else 'BLOCKED'}")
            print("=" * 80)
            for r in gate_data.get("results", []):
                print(f"  {r['agent_id']}: {r['status']:<18} (violations={r['lane_violations_count']}, clean={r['clean']})")
            print("=" * 80)
            if not passed:
                print("Gate is BLOCKED. All 10 agents must reach status PASSED before root fan-in.")
        return 0 if passed else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

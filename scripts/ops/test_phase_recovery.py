#!/usr/bin/env python3
"""Hermetic Test Suite for CLARA Care Phase Recovery & Resume Tool.

Part of Phase PH02 / Subagent A10 Quality Gate.
Validates:
1. Lane violation detection and manifest lane overrides.
2. Worktree state diagnosis (UNSTARTED, DIRTY, LANE_VIOLATION, FAILED, PASSED, BLOCKED).
3. Quarantine isolation of broken worktrees (patch extraction, branch creation, metadata).
4. Targeted single-agent retry with zero-mutation invariant for passed agents.
5. Checkpoint serialization and resume reconciliation.
6. PH02 Quality Gate evaluation.
7. CLI interface execution.

Zero external dependencies (stdlib unittest).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure repo root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ops.phase_recovery import (  # noqa: E402
    ALL_AGENTS,
    AgentStatus,
    PhaseRecoveryManager,
    run_cmd,
)


class TestPhaseRecoveryManager(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name)
        self.repo_dir = self.test_root / "repo"
        self.worktree_base = self.test_root / "worktrees"
        self.repo_dir.mkdir(parents=True)
        self.worktree_base.mkdir(parents=True)

        # Initialize mock git repository
        run_cmd(["git", "init", "-b", "main"], cwd=self.repo_dir)
        run_cmd(["git", "config", "user.name", "CLARA Test Agent"], cwd=self.repo_dir)
        run_cmd(["git", "config", "user.email", "agent@theclaracare.com"], cwd=self.repo_dir)

        # Initial commit as baseline
        readme = self.repo_dir / "README.md"
        readme.write_text("# CLARA Test Mock Repository\n", encoding="utf-8")
        run_cmd(["git", "add", "README.md"], cwd=self.repo_dir)
        run_cmd(["git", "commit", "-m", "chore: initial baseline commit"], cwd=self.repo_dir)
        _, self.base_sha, _ = run_cmd(["git", "rev-parse", "HEAD"], cwd=self.repo_dir)

        # Create 10 mock worktrees
        self.phase_id = "PH02"
        for agent_id in ALL_AGENTS:
            branch_name = f"phase/{self.phase_id.lower()}-{agent_id.lower()}"
            wt_path = self.worktree_base / f"{self.phase_id}_{agent_id}"
            run_cmd(
                ["git", "worktree", "add", "-b", branch_name, str(wt_path), self.base_sha],
                cwd=self.repo_dir,
            )

        self.mgr = PhaseRecoveryManager(
            phase_id=self.phase_id,
            worktree_base=self.worktree_base,
            base_sha=self.base_sha,
            repo_root=self.repo_dir,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_all_unstarted_at_baseline(self) -> None:
        """Fresh worktrees at base_sha should all be diagnosed as UNSTARTED."""
        diags = self.mgr.inspect_phase()
        self.assertEqual(len(diags), 10)
        for agent_id, diag in diags.items():
            self.assertEqual(diag.status, AgentStatus.UNSTARTED, f"Agent {agent_id} should be UNSTARTED")
            self.assertEqual(diag.commits_ahead, 0)
            self.assertTrue(diag.is_git_clean)
            self.assertFalse(diag.manifest_found)

    def test_lane_violation_detection(self) -> None:
        """Mutating files outside an agent's assigned lane must trigger LANE_VIOLATION."""
        agent_id = "A02"  # A02 owns db/ and alembic/
        wt = self.mgr.get_worktree_path(agent_id)

        # Write an out-of-lane file: apps/web/app/rogue.ts
        rogue_file = wt / "apps" / "web" / "app" / "rogue.ts"
        rogue_file.parent.mkdir(parents=True, exist_ok=True)
        rogue_file.write_text("// Unauthorized file mutation\n", encoding="utf-8")

        diag = self.mgr.diagnose_agent(agent_id)
        self.assertEqual(diag.status, AgentStatus.LANE_VIOLATION)
        self.assertIn("apps/web/app/rogue.ts", diag.lane_violations)
        self.assertFalse(diag.is_git_clean)

    def test_dirty_uncommitted_detection(self) -> None:
        """Uncommitted changes in allowed lane must trigger DIRTY_UNCOMMITTED when no manifest exists."""
        agent_id = "A01"
        wt = self.mgr.get_worktree_path(agent_id)

        schema_file = wt / "services" / "api" / "src" / "clara_api" / "schemas.py"
        schema_file.parent.mkdir(parents=True, exist_ok=True)
        schema_file.write_text("# Agent schema contract\n", encoding="utf-8")

        diag = self.mgr.diagnose_agent(agent_id)
        self.assertEqual(diag.status, AgentStatus.DIRTY_UNCOMMITTED)
        self.assertFalse(diag.is_git_clean)
        self.assertEqual(len(diag.lane_violations), 0)

    def test_passed_agent_lifecycle(self) -> None:
        """Agent with clean git, commit ahead, valid manifest and passing tests must be PASSED."""
        agent_id = "A03"
        wt = self.mgr.get_worktree_path(agent_id)

        # 1. Modify allowed file
        core_file = wt / "services" / "api" / "src" / "clara_api" / "core" / "task.py"
        core_file.parent.mkdir(parents=True, exist_ok=True)
        core_file.write_text("# Core domain\n", encoding="utf-8")

        # 2. Add deliverables
        artifact_dir = wt / "artifacts" / self.phase_id / agent_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "schema_version": "clara-phase-change-manifest.v1",
            "phase_id": self.phase_id,
            "agent_id": agent_id,
            "status": "COMPLETED",
            "base_sha": self.base_sha,
            "path_lane": ["services/api/src/clara_api/core/", f"artifacts/{self.phase_id}/{agent_id}/"],
            "test_results": [
                {"command": "pytest tests/test_task.py", "status": "PASS", "exit_code": 0}
            ],
        }
        (artifact_dir / "change_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (artifact_dir / "test_report.md").write_text("# Test Report\nAll passed.\n", encoding="utf-8")
        (artifact_dir / "risk_register.md").write_text("# Risk Register\nZero residual.\n", encoding="utf-8")

        # 3. Commit changes to worktree
        run_cmd(["git", "add", "."], cwd=wt)
        run_cmd(["git", "commit", "-m", f"feat({self.phase_id.lower()}-{agent_id.lower()}): deliver task"], cwd=wt)

        diag = self.mgr.diagnose_agent(agent_id)
        self.assertEqual(diag.status, AgentStatus.PASSED)
        self.assertTrue(diag.is_git_clean)
        self.assertEqual(diag.commits_ahead, 1)
        self.assertTrue(diag.tests_passed)
        self.assertEqual(len(diag.lane_violations), 0)

    def test_failed_tests_in_manifest(self) -> None:
        """Manifest reporting failed test exit code must evaluate to FAILED status."""
        agent_id = "A07"
        wt = self.mgr.get_worktree_path(agent_id)

        artifact_dir = wt / "artifacts" / self.phase_id / agent_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "schema_version": "clara-phase-change-manifest.v1",
            "phase_id": self.phase_id,
            "agent_id": agent_id,
            "status": "COMPLETED",
            "base_sha": self.base_sha,
            "test_results": [
                {"command": "pytest services/api/tests/test_flow.py", "status": "FAIL", "exit_code": 1}
            ],
        }
        (artifact_dir / "change_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        run_cmd(["git", "add", "."], cwd=wt)
        run_cmd(["git", "commit", "-m", "feat: test failure commit"], cwd=wt)

        diag = self.mgr.diagnose_agent(agent_id)
        self.assertEqual(diag.status, AgentStatus.FAILED)
        self.assertFalse(diag.tests_passed)
        self.assertTrue(any("Test failures" in r for r in diag.failure_reasons))

    def test_quarantine_isolation(self) -> None:
        """Quarantine must preserve patch, uncommitted files, metadata, and mark worktree."""
        agent_id = "A04"
        wt = self.mgr.get_worktree_path(agent_id)

        # Dirty state
        dirty_file = wt / "services" / "ml" / "src" / "clara_ml" / "pipeline.py"
        dirty_file.parent.mkdir(parents=True, exist_ok=True)
        dirty_file.write_text("# Broken syntax leak\n", encoding="utf-8")
        run_cmd(["git", "add", "services/ml/src/clara_ml/pipeline.py"], cwd=wt)

        untracked = wt / "untracked_leak.tmp"
        untracked.write_text("temporary scratchpad", encoding="utf-8")

        ok, msg = self.mgr.isolate_agent(agent_id, reason="Unit test quarantine")
        self.assertTrue(ok)
        self.assertIn("Quarantined A04", msg)

        # Check .quarantined marker
        marker = wt / ".quarantined"
        self.assertTrue(marker.exists())
        quarantine_dir = Path(marker.read_text(encoding="utf-8").strip())
        self.assertTrue(quarantine_dir.exists())

        # Check forensic assets
        patch_file = quarantine_dir / "uncommitted.patch"
        self.assertTrue(patch_file.exists())
        self.assertIn("Broken syntax leak", patch_file.read_text(encoding="utf-8"))

        manifest_file = quarantine_dir / "quarantine_manifest.json"
        self.assertTrue(manifest_file.exists())
        meta = json.loads(manifest_file.read_text(encoding="utf-8"))
        self.assertEqual(meta["agent_id"], "A04")
        self.assertEqual(meta["reason"], "Unit test quarantine")

        # Diagnosis should report QUARANTINED
        diag = self.mgr.diagnose_agent(agent_id)
        self.assertEqual(diag.status, AgentStatus.QUARANTINED)

    def test_targeted_retry_preserves_passed_agents(self) -> None:
        """Retrying a failed agent must reset ONLY that agent and preserve passed agents."""
        # 1. Establish A01 as PASSED
        wt_a01 = self.mgr.get_worktree_path("A01")
        (wt_a01 / "contracts").mkdir(parents=True, exist_ok=True)
        (wt_a01 / "contracts" / "agent.json").write_text("{}", encoding="utf-8")
        art_a01 = wt_a01 / "artifacts" / self.phase_id / "A01"
        art_a01.mkdir(parents=True, exist_ok=True)
        (art_a01 / "change_manifest.json").write_text(
            json.dumps({
                "schema_version": "clara-phase-change-manifest.v1",
                "phase_id": self.phase_id,
                "agent_id": "A01",
                "status": "COMPLETED",
                "base_sha": self.base_sha,
                "test_results": [{"command": "echo pass", "status": "PASS", "exit_code": 0}],
            }),
            encoding="utf-8",
        )
        run_cmd(["git", "add", "."], cwd=wt_a01)
        run_cmd(["git", "commit", "-m", "feat: A01 valid completion"], cwd=wt_a01)
        _, a01_passed_sha, _ = run_cmd(["git", "rev-parse", "HEAD"], cwd=wt_a01)

        # 2. Establish A05 as BROKEN / DIRTY
        wt_a05 = self.mgr.get_worktree_path("A05")
        (wt_a05 / "apps" / "web").mkdir(parents=True, exist_ok=True)
        (wt_a05 / "apps" / "web" / "broken.js").write_text("syntax error", encoding="utf-8")

        # 3. Retry A05
        ok, msg, instructions = self.mgr.retry_agent("A05")
        self.assertTrue(ok)
        self.assertIn("Successfully reset A05", msg)
        self.assertIn("prompt_text", instructions)
        self.assertEqual(instructions["agent_id"], "A05")
        self.assertEqual(instructions["base_sha"], self.base_sha)

        # 4. Invariant Check: A01 must remain strictly PASSED with identical commit SHA
        diag_a01 = self.mgr.diagnose_agent("A01")
        self.assertEqual(diag_a01.status, AgentStatus.PASSED)
        self.assertEqual(diag_a01.head_sha, a01_passed_sha)

        # 5. Invariant Check: A05 is clean at base_sha
        diag_a05 = self.mgr.diagnose_agent("A05")
        self.assertEqual(diag_a05.status, AgentStatus.UNSTARTED)
        self.assertEqual(diag_a05.head_sha, self.base_sha)
        self.assertTrue(diag_a05.is_git_clean)

    def test_checkpoint_and_resume_cycle(self) -> None:
        """Saving checkpoint and resuming should accurately reflect execution state."""
        # Save checkpoint with all unstarted
        ckpt_file = self.repo_dir / "artifacts" / self.phase_id / "checkpoint.json"
        ok, msg, data = self.mgr.save_checkpoint(ckpt_file)
        self.assertTrue(ok)
        self.assertTrue(ckpt_file.exists())
        self.assertFalse(data["ready_for_integration"])
        self.assertEqual(data["metrics"]["unstarted"], 10)

        # Resume from checkpoint
        ok, msg, plan = self.mgr.resume_phase(ckpt_file)
        self.assertTrue(ok)
        self.assertEqual(len(plan["unstarted_agents"]), 10)
        self.assertEqual(len(plan["retained_agents"]), 0)
        self.assertFalse(plan["all_ready_for_fanin"])

    def test_gate_evaluation_blocked_and_passed(self) -> None:
        """Gate should block when any agent is unstarted/failed and pass when all 10 pass."""
        # Initially blocked
        passed, gate_data = self.mgr.evaluate_gate()
        self.assertFalse(passed)
        self.assertFalse(gate_data["gate_passed"])

        # Complete all 10 agents
        for agent_id in ALL_AGENTS:
            wt = self.mgr.get_worktree_path(agent_id)
            art = wt / "artifacts" / self.phase_id / agent_id
            art.mkdir(parents=True, exist_ok=True)
            manifest = {
                "schema_version": "clara-phase-change-manifest.v1",
                "phase_id": self.phase_id,
                "agent_id": agent_id,
                "status": "COMPLETED",
                "base_sha": self.base_sha,
                "test_results": [{"command": "echo test", "status": "PASS", "exit_code": 0}],
            }
            (art / "change_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (art / "test_report.md").write_text("# Report", encoding="utf-8")
            (art / "risk_register.md").write_text("# Risks", encoding="utf-8")
            run_cmd(["git", "add", "."], cwd=wt)
            run_cmd(["git", "commit", "-m", f"feat({agent_id}): pass"], cwd=wt)

        passed, gate_data = self.mgr.evaluate_gate()
        self.assertTrue(passed)
        self.assertTrue(gate_data["gate_passed"])

    def test_cli_invocation_end_to_end(self) -> None:
        """Test executing CLI commands via sys.executable."""
        script_path = REPO_ROOT / "scripts" / "ops" / "phase_recovery.py"

        # 1. status --json
        cmd = [
            sys.executable,
            str(script_path),
            "--phase", self.phase_id,
            "--worktree-base", str(self.worktree_base),
            "--base-sha", self.base_sha,
            "--repo-root", str(self.repo_dir),
            "--json",
            "status",
        ]
        code, out, err = run_cmd(cmd)
        self.assertEqual(code, 0, f"status failed: {err}")
        data = json.loads(out)
        self.assertIn("A01", data)
        self.assertEqual(data["A01"]["status"], "UNSTARTED")

        # 2. checkpoint
        ckpt_path = self.repo_dir / "artifacts" / self.phase_id / "cli_checkpoint.json"
        cmd = [
            sys.executable,
            str(script_path),
            "--phase", self.phase_id,
            "--worktree-base", str(self.worktree_base),
            "--base-sha", self.base_sha,
            "--repo-root", str(self.repo_dir),
            "--json",
            "checkpoint",
            "--output", str(ckpt_path),
        ]
        code, out, err = run_cmd(cmd)
        self.assertEqual(code, 0, f"checkpoint failed: {err}")
        self.assertTrue(ckpt_path.exists())

        # 3. resume
        cmd = [
            sys.executable,
            str(script_path),
            "--phase", self.phase_id,
            "--worktree-base", str(self.worktree_base),
            "--base-sha", self.base_sha,
            "--repo-root", str(self.repo_dir),
            "--json",
            "resume",
            "--checkpoint-file", str(ckpt_path),
        ]
        code, out, err = run_cmd(cmd)
        self.assertEqual(code, 0, f"resume failed: {err}")
        resume_data = json.loads(out)
        self.assertEqual(len(resume_data["unstarted_agents"]), 10)

        # 4. gate (should fail initially with 1 because unstarted)
        cmd = [
            sys.executable,
            str(script_path),
            "--phase", self.phase_id,
            "--worktree-base", str(self.worktree_base),
            "--base-sha", self.base_sha,
            "--repo-root", str(self.repo_dir),
            "--json",
            "gate",
        ]
        code, out, err = run_cmd(cmd)
        self.assertEqual(code, 1, "gate should exit 1 when not all agents passed")
        gate_data = json.loads(out)
        self.assertFalse(gate_data["gate_passed"])


if __name__ == "__main__":
    unittest.main()

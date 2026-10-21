# PH02 / A07 — Risk Register: Merge Queue & Concurrent Integration

**Phase:** PH02 (Thiết lập tổ chức tác nhân và 10 worktree song song)
**Agent:** A07 (Tests + CI)
**Frozen Base SHA:** `879dc5dcfcaae91b3626e28062043d934294478b`
**Date:** October 21, 2026
**Status:** COMPLETE

---

## 1. Overview

This risk register tracks operational, architectural, and security risks associated with the automated integration of 10 concurrent subagents (A01..A10) and the execution of the merge queue worker during phase integration.

---

## 2. Risk Matrix & Mitigations

### RISK-MQ01: Silent Git Conflict Resolution or Automatic Merging
- **Category:** Integration Integrity / Race Conditions
- **Severity:** HIGH (P1)
- **Description:**
  If git cherry-picks or merges are attempted with auto-resolve strategies (e.g., `-X theirs` or `--strategy-option`), unexpected semantic changes or broken invariants could be silently committed.
- **Compensating Control:**
  `merge_queue_worker.py` strictly uses vanilla cherry-picking without fallback merge strategies. At the first sign of any merge conflict (non-zero exit code), the worker immediately issues `git cherry-pick --abort`, halts the integration sequence, marks the agent as FAILED, and records the exact conflicting files in the report.

---

### RISK-MQ02: Cross-Lane Scope Creep / ACL Bypasses
- **Category:** Architecture / Governance
- **Severity:** HIGH (P1)
- **Description:**
  A subagent tasked with web UI or documentation might inadvertently alter API contracts, database migrations, or core safety policies outside its assigned path lane.
- **Compensating Control:**
  `check_all_path_acls` enforces strict whitelist filtering on `files_changed` before any git commit is cherry-picked. Any file mutation outside the assigned path lanes causes immediate rejection (exit code 3) without executing cherry-picks.

---

### RISK-MQ03: False Success via Mocked or Missing Tests
- **Category:** Quality Assurance / Verification Safety
- **Severity:** HIGH (P1)
- **Description:**
  Subagents could claim success without providing automated test executions, or manifests could declare status "COMPLETE" despite unresolved blockers.
- **Compensating Control:**
  `validate_agent_manifest` verifies that:
  1. Status is explicitly `COMPLETE` or `PASSED`.
  2. `blockers` list is strictly empty (`[]`). Any declared blocker fails validation.
  3. Companion files `test_report.md` and `risk_register.md` physically exist on disk.
  4. Integration test gates (`python3 -m compileall` and migration downgrade checks) run as an active gate step before generating the final `merge_manifest.json`.

---

### RISK-MQ04: Dirty Target Repository or Uncommitted Workspace Drift
- **Category:** Environment / Reproducibility
- **Severity:** MEDIUM (P2)
- **Description:**
  Running integration against a dirty working tree could accidentally include untracked developer files or uncommitted mutations into the integrated release candidate.
- **Compensating Control:**
  `validate_preconditions` checks `git status --porcelain` and refuses to proceed unless the working tree is completely clean (or `--dry-run` is active).

---

### RISK-MQ05: Worktree Path Non-Uniformity in Non-Standard Environments
- **Category:** Tooling Compatibility
- **Severity:** LOW (P3)
- **Description:**
  If an environment mounts worktrees under a directory other than `/dev/shm/clara_worktrees`, the worker might not automatically locate other worktrees.
- **Compensating Control:**
  The worker provides the `--worktrees-dir` argument, searches `<repo_root>/artifacts/...` as an immediate fallback, and supports direct manifest path resolution.

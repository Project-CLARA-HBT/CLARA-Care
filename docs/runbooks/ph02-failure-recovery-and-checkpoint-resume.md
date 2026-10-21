# Runbook: PH02 Failure Recovery, Worktree Isolation, and Checkpoint Resumption

**Phase:** PH02 — Establishing 10-Concurrent-Subagent Organization & Worktree Protocol
**Scope:** Worktree Failure Diagnosis, Quarantine Isolation, Targeted Single-Agent Retry, and Checkpoint-Based Resumption
**Target Environments:** Local Development Worktrees, CI Integration Workers, Staging Runners
**Owner:** Subagent A10 (Adversarial Audit & Integration Proposals)
**Last Updated:** October 2026 (PH02 Baseline)

---

## 1. Executive Overview & Core Invariants

During multi-agent parallel execution phases (such as PH02, PH40, PH71..PH100), 10 subagents (`A01` through `A10`) operate simultaneously in isolated `git worktree` instances. When an individual subagent experiences a failure (e.g. test regressions, unhandled exceptions, git conflicts, lane violations, or model context timeouts), the entire phase execution must **not** be discarded.

Instead, the orchestration protocol mandates:
1. **Preservation of Passed Agents:** Agents that have completed their tasks, produced valid `change_manifest.json` deliverables, and passed all test suites must remain strictly preserved with zero mutation to their worktrees, commits, or manifests.
2. **Deterministic Forensic Quarantine:** Before resetting or retrying any failed agent, all partial work, staged/unstaged diffs, and untracked files must be extracted into a non-destructive quarantine directory (`artifacts/<PHASE>/quarantine/<AGENT>/<TIMESTAMP>/`) and tagged in git (`quarantine/<phase>-<agent>-<timestamp>`).
3. **Targeted Single-Agent Retry:** The operator or root orchestrator can selectively reset and re-launch *only* the failed subagent at the frozen base SHA (`879dc5dcfcaae91b3626e28062043d934294478b`), supplying bounded context and explicit path lane instructions.
4. **Checkpoint Reconciliation:** State transitions are atomically written to `artifacts/<PHASE>/checkpoint.json`. On phase interruption or system restart, the runner resumes from the checkpoint, retaining passed agents and re-queueing only pending or failed tasks.
5. **Quality Gate Enforcement:** Before root fan-in merge, the phase quality gate (`scripts/ci/ph02_quality_gate.py`) verifies that all 10 subagents have reached `PASSED` status, 0 lane violations exist, and all artifacts are sealed.

---

## 2. Tool Reference: `scripts/ops/phase_recovery.py`

The CLI tool `scripts/ops/phase_recovery.py` implements the failure diagnosis, quarantine, retry, checkpoint, and gate commands.

```
usage: python3 scripts/ops/phase_recovery.py [-h] [--phase PHASE] [--worktree-base WORKTREE_BASE]
                                           [--base-sha BASE_SHA] [--repo-root REPO_ROOT]
                                           [--json]
                                           {status,diagnose,isolate,retry,checkpoint,resume,gate} ...
```

### 2.1 Subcommands Summary

| Command | Purpose | Key Arguments | Exit Code |
|---|---|---|---|
| `status` | Print status matrix across all 10 agents | `--phase PH02`, `--json` | `0` |
| `diagnose` | Perform deep root-cause inspection | `--agent <ID>` (optional) | `0` (clean) / `1` (issue found) |
| `isolate` | Quarantine broken worktree and export forensic diff | `--agent <ID>` or `--all-failed`, `--reason <text>` | `0` (success) / `1` (error) |
| `retry` | Reset only the targeted agent to base SHA; preserve passed | `--agent <ID>`, `--force`, `--no-quarantine` | `0` (success) / `1` (error) |
| `checkpoint` | Atomically persist execution state to JSON | `--output <path>` | `0` (success) / `1` (error) |
| `resume` | Reconcile worktrees against last checkpoint and emit plan | `--checkpoint-file <path>` | `0` (success) / `1` (error) |
| `gate` | Validate all 10 agents and phase invariants | `--phase PH02`, `--json` | `0` (passed) / `1` (blocked) |

---

## 3. Step-by-Step Recovery Workflows

### 3.1 Scenario A: Inspecting Active Phase Health

To inspect the operational status of all 10 subagents:

```bash
# Formatted status table
python3 scripts/ops/phase_recovery.py status --phase PH02

# Machine-readable JSON output for automated runners
python3 scripts/ops/phase_recovery.py status --phase PH02 --json
```

**Status Codes:**
- `PASSED`: Worktree is clean, commits exist ahead of base, `change_manifest.json` indicates `COMPLETED`, all test commands passed (exit=0), 0 lane violations.
- `UNSTARTED`: Worktree is clean at base SHA; no commits or manifests yet.
- `DIRTY_UNCOMMITTED`: File modifications exist in worktree but have not been committed.
- `LANE_VIOLATION`: One or more files modified lie outside the agent's assigned `path_lane`.
- `FAILED`: Manifest reports failed tests, non-zero exit codes, or unhandled exceptions.
- `BLOCKED`: Manifest reports dependency or capacity blockage.
- `QUARANTINED`: Worktree contains a `.quarantined` marker; isolated from fan-in.
- `CORRUPTED`: Git directory missing or unreadable.

---

### 3.2 Scenario B: Diagnosing a Failed or Blocked Subagent

When an agent fails, run the diagnostic engine to extract exact root causes:

```bash
# Diagnose specific agent (e.g. A04)
python3 scripts/ops/phase_recovery.py diagnose --agent A04

# Diagnose all failed or incomplete agents
python3 scripts/ops/phase_recovery.py diagnose
```

**Diagnostic Output Details:**
- Exact git worktree directory and branch validation.
- Commit distance ahead of base SHA (`commits_ahead`).
- Full list of staged, unstaged, and untracked files.
- Manifest presence, status, and individual test command exit codes.
- Specific out-of-lane file paths violating path governance.
- Quarantine state and historical isolation links.

---

### 3.3 Scenario C: Quarantining a Broken Worktree

If an agent has corrupted state, merge conflicts, or invalid modifications that need forensic preservation before cleanup:

```bash
# Isolate single agent
python3 scripts/ops/phase_recovery.py isolate --agent A04 --reason "Regression in ML pipeline"

# Isolate all failed agents simultaneously
python3 scripts/ops/phase_recovery.py isolate --all-failed
```

**Quarantine Actions Executed:**
1. Staged and unstaged git diffs are extracted to `artifacts/<PHASE>/quarantine/<AGENT>/<TIMESTAMP>/uncommitted.patch`.
2. Untracked file inventory is recorded to `untracked_files.txt`.
3. A local git quarantine branch `quarantine/<phase>-<agent>-<timestamp>` is created from current HEAD.
4. Quarantine metadata manifest (`quarantine_manifest.json`) is saved recording the operator note, original branch, commit SHA, and failure reasons.
5. A `.quarantined` marker is written into the agent's worktree root.

---

### 3.4 Scenario D: Retrying a Single Failed Subagent (Zero-Mutation Guarantee)

To retry a single failed agent without discarding work completed by passed agents:

```bash
# Retry Subagent A04
python3 scripts/ops/phase_recovery.py retry --agent A04
```

**Safety Guarantees During Retry:**
1. **Automated Isolation:** Unless `--no-quarantine` is passed, existing worktree modifications are automatically snapshotted into quarantine before any reset.
2. **Isolated Reset:** Untracked files are cleaned (`git clean -ffdx`), and the branch `phase/ph02-a04` is reset to the pinned base SHA (`879dc5dcfcaae91b3626e28062043d934294478b`).
3. **Passed Agent Invariant:** The tool captures the HEAD SHA of every passed agent prior to retry, and asserts that no passed agent's worktree or branch was mutated during the operation.
4. **Targeted Restart Output:** Emits exact prompt instructions, bounded path lanes, and verification commands for re-launching the subagent session.

**Sample Targeted Restart Output:**
```
================================================================================
TARGETED RESTART INSTRUCTIONS FOR A04:
================================================================================
You are subagent A04 for PH02.
Worktree path: /dev/shm/clara_worktrees/PH02_A04
Branch: phase/ph02-a04
Frozen HEAD SHA: 879dc5dcfcaae91b3626e28062043d934294478b
Role: ML + retrieval: resource quotas and semaphore 10
Path lane: services/ml/src/clara_ml/;evaluation/;services/ocr/;services/asr/;scripts/ops/;artifacts/PH02/A04/
Rules: Only modify files inside your path lane. Deliver change_manifest.json, test_report.md, risk_register.md.
--------------------------------------------------------------------------------
Verification: python3 scripts/ops/phase_recovery.py diagnose --agent A04 && git -C /dev/shm/clara_worktrees/PH02_A04 status
================================================================================
```

---

### 3.5 Scenario E: State Checkpointing & Interrupted Phase Resumption

During long-running or distributed execution, agents may finish at different times. Checkpointing ensures resilience against runner restarts or environment disruptions.

```bash
# 1. Save checkpoint
python3 scripts/ops/phase_recovery.py checkpoint --phase PH02

# 2. Checkpoint saved atomically to artifacts/PH02/checkpoint.json
```

If the execution environment reboots or crashes, resume with:

```bash
python3 scripts/ops/phase_recovery.py resume --phase PH02
```

**Resumption Output:**
- Reports all retained agents (already completed and verified; skipped from re-run).
- Reports unstarted or pending agents.
- Emits explicit action items for retrying failed agents.

---

### 3.6 Scenario F: Phase Quality Gate Verification

Before the root integrator executes fan-in merges across branches, the PH02 quality gate must be verified:

```bash
# Run CI quality gate
python3 scripts/ci/ph02_quality_gate.py

# Or via phase recovery gate subcommand
python3 scripts/ops/phase_recovery.py gate --phase PH02
```

---

## 4. Emergency Escalation & Disaster Recovery

### 4.1 Full Phase Abort & Reset
If a systemic issue occurs requiring complete phase teardown back to the initial base commit:
```bash
# Reset all 10 worktrees back to clean base SHA
for a in $(seq -w 1 10); do
  wt="/dev/shm/clara_worktrees/PH02_A${a}"
  if [ -d "$wt" ]; then
    git -C "$wt" reset --hard 879dc5dcfcaae91b3626e28062043d934294478b
    git -C "$wt" clean -ffdx
    git -C "$wt" checkout -B "phase/ph02-a${a}" 879dc5dcfcaae91b3626e28062043d934294478b
  fi
done
```

### 4.2 Restoring from Quarantine
If an isolated agent's work needs to be inspected or restored:
```bash
# Navigate to agent worktree
cd /dev/shm/clara_worktrees/PH02_A04

# Apply quarantined patch
git apply artifacts/PH02/quarantine/A04/<TIMESTAMP>/uncommitted.patch
```

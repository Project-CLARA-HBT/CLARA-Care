# Risk Register — PH02 Multi-Agent Orchestration & Failure Recovery (Subagent A10)

**Phase:** PH02 — Establishing 10-Concurrent-Subagent Organization & Worktree Protocol
**Agent:** Subagent A10 — Adversarial Audit + Integration Proposals
**Worktree:** `/dev/shm/clara_worktrees/PH02_A10`
**Branch:** `phase/ph02-a10`
**Base SHA:** `879dc5dcfcaae91b3626e28062043d934294478b`
**Status:** ACTIVE AUDIT REGISTER · PH02 QUALITY GATE GREEN

---

## 1. Executive Summary & Orchestration Assurance

Phase PH02 introduces concurrent multi-agent software engineering execution across 10 isolated git worktrees. This parallel orchestration model introduces distinct failure modes: out-of-lane file collisions, premature merges of failing agents, partial work destruction during retries, and runner interruption.

Subagent A10 has conducted an adversarial risk analysis and deployed automated controls in `scripts/ops/phase_recovery.py` and `scripts/ci/ph02_quality_gate.py` to mitigate each identified risk.

---

## 2. Updated Platform & Orchestration Risk Register

| Risk ID | Category | Severity | Likelihood | Impact | Title & Vulnerability Summary | Mitigations & Verification Gate |
|---|---|---|---|---|---|---|
| **RISK-PH02-01** | Orchestration / Concurrency | **HIGH** | Medium | High | **Accidental Mutation of Passed Subagents During Single-Agent Retry**<br>When resetting or retrying a failed subagent (e.g. A04), a naïve orchestrator might perform a global `git reset` or clean the worktree base, clobbering completed work from other agents. | **Mitigated in `phase_recovery.py`**:<br>`retry_agent()` scopes operations strictly to the targeted agent's worktree. An automated pre- and post-check asserts that all passed agent commit SHAs remain identical before allowing the retry to succeed. Verified in `test_targeted_retry_preserves_passed_agents`. |
| **RISK-PH02-02** | Data Loss / Forensics | **MEDIUM** | High | Medium | **Destruction of Forensic State on Broken Worktree Cleanup**<br>Discarding uncommitted changes or unhandled error traces when an agent times out prevents engineers from diagnosing root causes. | **Mitigated in `phase_recovery.py`**:<br>`isolate_agent()` automatically captures staged/unstaged diffs into `uncommitted.patch`, inventories untracked files, creates a quarantine git branch, and records diagnostic metadata before any reset occurs. |
| **RISK-PH02-03** | Governance / Integrity | **HIGH** | Medium | High | **Cross-Lane File Collisions and Unauthorized File Mutations**<br>Subagents attempting to modify files outside their assigned lane could silently clobber shared contracts, routes, or database schemas. | **Mitigated in `phase_recovery.py` & `ph02_quality_gate.py`**:<br>Worktree diagnostics check all modified and uncommitted files against `PH02_PATH_LANES`. Any out-of-lane mutation immediately transitions the agent to `LANE_VIOLATION` and blocks the phase gate. |
| **RISK-PH02-04** | Execution Continuity | **MEDIUM** | Medium | Medium | **Interrupted Phase Resumption State Desynchronization**<br>If a host reboot, CI timeout, or memory exhaustion terminates the runner, restarting without state checkpoints forces re-execution of all 10 agents. | **Mitigated in `phase_recovery.py`**:<br>`checkpoint` sub-command writes atomic phase state to `artifacts/<PHASE>/checkpoint.json`. `resume` sub-command reconciles active worktrees, retains all passed agents, and generates targeted restart plans for only pending agents. |
| **RISK-PH02-05** | Integration / Quality | **HIGH** | Low | High | **Premature Fan-In Merge of Failing or Incomplete Subagents**<br>If the root integrator attempts sequential cherry-picking before all 10 agents have met completion criteria, broken code enters the main branch. | **Mitigated in `ph02_quality_gate.py` & `gate` subcommand**:<br>Quality gate fails (exit code 1) unless 100% of subagents have reached `PASSED` status with passing tests and verified manifests. |

---

## 3. Escalation & Operational Directives

1. **Pre-Integration Freeze:** Before executing the fan-in merge queue (`scripts/ops/merge_queue_worker.py`), run `python3 scripts/ops/phase_recovery.py checkpoint --phase PH02` to freeze state.
2. **Quarantine Audit:** No agent in `QUARANTINED` status may be included in the merge queue without explicit review and resolution.
3. **Emergency Worktree Rollback:** If an unrecoverable corruption occurs during an agent run, follow Section 4 of `docs/runbooks/ph02-failure-recovery-and-checkpoint-resume.md`.

# PH02-A02 Risk Register

- **Phase:** PH02 (Establish Agent Orchestration and 10 Parallel Worktrees)
- **Subagent:** A02 (Data model + migration)
- **Evaluation Target:** Git Worktree Manager (`scripts/ops/worktree_manager.py`)
- **Date:** 2026-10-21

---

## Risk Assessment Matrix

| Risk ID | Severity | Likelihood | Impact Area | Description | Mitigation Strategy | Status |
|---|---|---|---|---|---|---|
| **RISK-PH02-A02-01** | Critical | Medium | Data Integrity | Accidental deletion or overwrite of uncommitted developer changes during worktree teardown or rebuild. | `cleanup_worktrees` inspects git status (`check_worktree_clean`) before removing files and fails closed with `WorktreeDirtyError` unless `--force` is explicitly provided. | **MITIGATED** |
| **RISK-PH02-A02-02** | High | Low | Isolation / Cross-Talk | Concurrent subagents interfering with shared state or modifying the same workspace files. | Every subagent receives an isolated directory (`/dev/shm/clara_worktrees/<PHASE>_<AGENT>`), a dedicated branch (`phase/<phase>-<agent>`), and independent artifact lanes. Verified zero file leakage between worktrees. | **MITIGATED** |
| **RISK-PH02-A02-03** | High | Medium | Filesystem Compatibility | Operating systems or CI environments without `/dev/shm` or lacking write permissions failing worktree initialization. | Automatic dynamic fallback to `.worktrees/` inside repo root when `/dev/shm` is not available or not writable. | **MITIGATED** |
| **RISK-PH02-A02-04** | Critical | Low | Base State Drift | Spawning subagents from divergent, stale, or dirty base commits compromising reproducibility. | Strict commit verification via `verify_commit_sha(base_sha)` fails immediately if the target commit does not exist or cannot be resolved to a 40-character hex SHA. | **MITIGATED** |
| **RISK-PH02-A02-05** | Medium | Low | Orphaned Git Worktrees | Worktree directories deleted from filesystem leaving dangling references in `.git/worktrees`. | Automatic invocation of `git worktree prune` after cleanup cycles and graceful handling of missing directories. | **MITIGATED** |

---

## Detailed Risk Analyses

### RISK-PH02-A02-01: Destructive Worktree Teardown
- **Hazard:** Calling a cleanup script on active subagents could destroy hours of uncommitted work or deliverables.
- **Remediation:** `worktree_manager.py` implements a pre-flight dirty check across all target worktrees. If any worktree contains modified, deleted, or untracked files, the operation halts immediately without touching any worktree unless `--force` is supplied.
- **Residual Risk:** Low.

### RISK-PH02-A02-02: Zero Cross-Talk Invariant
- **Hazard:** Subagents sharing the same root working tree could clobber git index locks or cross-contaminate code changes.
- **Remediation:** Git worktrees provide separate indexes and checkouts pointing to isolated branch heads. Integration test `test_create_isolation_scaffolding_and_cleanup` verifies that mutations in one worktree are completely invisible in peer worktrees and the main repo.
- **Residual Risk:** Negligible.

### RISK-PH02-A02-04: Base SHA Verification
- **Hazard:** User or orchestrator supplies a branch name or invalid commit string, causing subagents to diverge from the designated baseline commit (`879dc5dcfcaae91b3626e28062043d934294478b`).
- **Remediation:** Strict validation with `git rev-parse --verify <sha>^{commit}` ensures exact commit anchoring prior to branch creation.
- **Residual Risk:** Low.

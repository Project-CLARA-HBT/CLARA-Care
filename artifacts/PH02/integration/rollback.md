# PH02 Rollback Procedure

## Scope
Phase PH02 delivers the 10-concurrent-subagent orchestration toolchain:
- Agent contract JSON schema (`contracts/agent-execution/agent-manifest.schema.json`)
- Worktree manager tool (`scripts/ops/worktree_manager.py`)
- Path governance and lane disjointness verifier (`services/api/src/clara_api/core/path_governance.py`)
- Agent concurrency limiter & semaphore (`scripts/ops/agent_concurrency_limiter.py`)
- Agent path ACL checker (`scripts/ci/check_agent_path_acl.py`)
- Prompt and bounded context pack generator (`scripts/ops/generate_agent_prompts.py`)
- Merge queue worker (`scripts/ops/merge_queue_worker.py`)
- Red-team manifest checker (`scripts/security/redteam_manifest_checker.py`)
- Progress dashboard (`scripts/ops/progress_dashboard.py`)
- Phase recovery and resume tool (`scripts/ops/phase_recovery.py`, `scripts/ci/ph02_quality_gate.py`)

## Rollback Procedures
1. **Full Rollback to Phase Base Commit:**
   ```bash
   git reset --hard 879dc5dcfcaae91b3626e28062043d934294478b
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH02 --force
   ```

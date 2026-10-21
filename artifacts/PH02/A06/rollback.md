# Rollback Runbook — Subagent A06 (Mobile Flutter)

## Rollback Scope
- **Subagent**: `A06`
- **Phase**: `PH02`
- **Component**: Agent Prompt and Bounded Context Pack Generator
- **Base SHA**: `879dc5dcfcaae91b3626e28062043d934294478b`
- **Branch**: `phase/ph02-a06`

---

## 1. Fast Rollback Command Sequence

If any regression or defect is identified with `generate_agent_prompts.py` or the generated artifacts, execute:

```bash
# 1. Navigate to repository root or worktree
cd /dev/shm/clara_worktrees/PH02_A06

# 2. Remove generator script and unit tests
git rm -f scripts/ops/generate_agent_prompts.py scripts/ops/test_generate_agent_prompts.py

# 3. Remove generated artifacts directory
rm -rf artifacts/PH02/A06/

# 4. Reset branch cleanly to frozen ground-truth SHA
git reset --hard 879dc5dcfcaae91b3626e28062043d934294478b
```

---

## 2. Invariant Verification Post-Rollback

1. Verify working directory is completely clean:
   ```bash
   git status --short
   ```
2. Verify repo HEAD equals frozen SHA:
   ```bash
   git rev-parse HEAD
   # Output must be: 879dc5dcfcaae91b3626e28062043d934294478b
   ```
3. Verify no lingering files in `scripts/ops/` or `artifacts/PH02/A06/`:
   ```bash
   ls -la scripts/ops/generate_agent_prompts.py 2>/dev/null || echo "CLEAN"
   ```

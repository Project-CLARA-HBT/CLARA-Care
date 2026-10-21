# Rollback Plan: PH02_A04 Concurrency Limiter & Resource Quotas

## Scope
Rollback plan for changes introduced in Phase PH02 Subagent A04 (`scripts/ops/agent_concurrency_limiter.py`, `services/ml/src/clara_ml/agent_concurrency.py`, `evaluation/tests/test_agent_concurrency_limiter.py`, and deliverables).

---

## 1. Runtime Abort / Live Deactivation

If the concurrency limiter or lock directory experiences an unexpected operational issue:
1. **Clear lock directory:**
   ```bash
   rm -rf /dev/shm/.clara_agent_concurrency /tmp/.clara_agent_concurrency*
   ```
2. **Bypass headroom enforcement:**
   If host memory or disk thresholds trigger false positives on constrained CI runners, run tasks with `--bypass-headroom` or set:
   ```bash
   export CLARA_MIN_RAM_FREE_MB=0
   export CLARA_MIN_RAMDISK_FREE_MB=0
   ```
3. **Emergency Unbounded Fallback:**
   To bypass slot limits entirely, execute commands directly in bash without the `scripts/ops/agent_concurrency_limiter.py run` prefix.

---

## 2. Git Branch Reversion

To completely remove all changes introduced by this patch and return to the baseline SHA:
```bash
# 1. Clean up runtime slot directories
rm -rf /dev/shm/.clara_agent_concurrency /tmp/.clara_agent_concurrency*

# 2. Revert branch to pinned base SHA
git reset --hard 879dc5dcfcaae91b3626e28062043d934294478b

# 3. Clean any untracked artifacts
git clean -fd
```

---

## 3. Verification Post-Rollback
Verify working tree is clean:
```bash
git status
git rev-parse HEAD
# Output must equal: 879dc5dcfcaae91b3626e28062043d934294478b
```

# Rollback Plan — PH12 A07 (Mobile LifeMap Parity Integration Tests)

## 1. Overview
Subagent A07 changes introduce additive integration test coverage in `services/api/tests/test_lifemap_mobile_parity_integration.py` and test documentation deliverables in `artifacts/PH12/A07/`. No production schemas, migrations, or application routes were modified.

## 2. Automated Rollback Commands
To revert the worktree cleanly to the frozen base commit `36e5b95fac7e65712f0779de253d8ed18dc693d7`:

```bash
# 1. Navigate to worktree root
cd /dev/shm/clara_worktrees/PH12_A07

# 2. Remove added integration test file
rm -f services/api/tests/test_lifemap_mobile_parity_integration.py

# 3. Remove generated artifacts directory
rm -rf artifacts/PH12/A07

# 4. Verify worktree is completely clean and matches base SHA
git reset --hard 36e5b95fac7e65712f0779de253d8ed18dc693d7
git clean -fd
```

## 3. Post-Rollback Validation
1. Verify git status is clean:
   ```bash
   git status
   ```
2. Verify repo HEAD SHA:
   ```bash
   git rev-parse HEAD
   # Output must match: 36e5b95fac7e65712f0779de253d8ed18dc693d7
   ```
3. Run existing test suite baseline:
   ```bash
   (cd services/api && DATABASE_URL=sqlite+pysqlite:////tmp/clara_api_ci.db uv run pytest -q tests/test_lifemap_client_contract.py)
   ```

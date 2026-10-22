# Rollback Plan — PH07 A02 (D2 Semantic Digest Indexing)

## Rollback Procedure
1. Revert models modification:
   ```bash
   git -C /dev/shm/clara_worktrees/PH07_A02 checkout e8533cb029a1470ce2d1bc027a421b47664871c5 -- services/api/src/clara_api/db/models.py
   ```
2. Remove migration and deliverables:
   ```bash
   rm -f services/api/alembic/versions/20260904_0067_glhs_d2_semantic_digest_index.py
   rm -rf artifacts/PH07/A02
   ```
3. Verification:
   ```bash
   git status
   ```

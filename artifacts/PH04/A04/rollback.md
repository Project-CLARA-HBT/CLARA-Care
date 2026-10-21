# Rollback Guide: Multi-Tenant Organizations, Workspace Membership Invitations & RAG Retrieval Isolation

- **Phase:** PH04 (Multi-tenant organizations và workspaces)
- **Agent ID:** A04
- **Role:** ML + retrieval
- **Worktree:** `/dev/shm/clara_worktrees/PH04_A04`
- **Branch:** `phase/ph04-a04`
- **Base SHA:** `7f458c915a59a75568e344b670d2f12ce9133a4e`

---

## 1. Fast Rollback Procedure (Emergency Reversion)

If any regression occurs in production or staging environments, follow these steps to revert all code and test changes to the frozen base commit:

### Step 1: Revert Code Files to Baseline SHA
```bash
cd /dev/shm/clara_worktrees/PH04_A04

# Revert modified core files
git checkout 7f458c915a59a75568e344b670d2f12ce9133a4e -- \
  services/ml/src/clara_ml/rag/store/schema.py \
  services/ml/src/clara_ml/rag/store/document_store.py \
  services/ml/src/clara_ml/rag/store/hybrid_retriever.py \
  services/ml/src/clara_ml/rag/store/sparse_index.py \
  services/ml/src/clara_ml/rag/store/cache.py \
  services/ml/src/clara_ml/rag/pipeline.py \
  services/ml/src/clara_ml/main.py
```

### Step 2: Remove Newly Created Files
```bash
rm -f services/ml/src/clara_ml/tenant_boundary.py
rm -f evaluation/tests/test_tenant_rag_isolation.py
rm -rf artifacts/PH04/A04
```

### Step 3: Hard Reset Worktree
```bash
git reset --hard 7f458c915a59a75568e344b670d2f12ce9133a4e
git clean -fd
```

---

## 2. Database & Schema Rollback Considerations

- The ORM schema modifications to `KbSourceRegistry` and `KbDocument` introduced nullable `tenant_id` columns with defaults to `None` / `"global"`.
- Because these additions are purely additive and nullable, reverting code to `7f458c915a59a75568e344b670d2f12ce9133a4e` causes zero schema conflicts with existing Postgres databases. Existing un-tenanted rows remain readable by the previous code version.

---

## 3. Post-Rollback Verification

Execute the baseline verification command to confirm the environment is restored:
```bash
git status
# Expect: On branch phase/ph04-a04, nothing to commit, working tree clean

git rev-parse HEAD
# Expect: 7f458c915a59a75568e344b670d2f12ce9133a4e

PYTHONPATH=services/ml/src python3 -m pytest -q \
  services/ml/tests/test_router.py \
  services/ml/tests/test_model_router.py \
  services/ml/tests/test_rag_pipeline.py
# Expect: All baseline tests PASS
```

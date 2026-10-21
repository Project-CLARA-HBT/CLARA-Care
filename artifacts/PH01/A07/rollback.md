# PH01 / A07 — Rollback Plan

**Phase:** PH01 (Toolchain tái lập và dependency supply-chain)
**Agent:** A07 (Tests + CI)
**Frozen Base SHA:** `2aa9016a57b49b53f1a433d076e1028a6ec45f64`
**Branch:** `phase/ph01-a07`

---

## 1. Safety & Production Impact

All changes introduced by A07 in PH01 are confined to testing and CI/ops tooling:
- `scripts/ops/generate_sbom.py`
- `scripts/ops/check_dependency_integrity.py`
- `services/api/tests/test_sbom_and_dependency_integrity.py`
- `.github/workflows/ci.yml` (additive CI steps)
- Artifact deliverables under `artifacts/PH01/A07/`

No runtime database schemas, data records, API endpoints, or user-facing services are modified.

---

## 2. Rollback Steps

If any tool or CI workflow modification causes unexpected failures or conflicts during root integration:

1. **Revert CI Workflow Changes:**
   ```bash
   git checkout 2aa9016a57b49b53f1a433d076e1028a6ec45f64 -- .github/workflows/ci.yml
   ```

2. **Remove Ops Scripts and Test Suite:**
   ```bash
   rm -f scripts/ops/generate_sbom.py \
         scripts/ops/check_dependency_integrity.py \
         services/api/tests/test_sbom_and_dependency_integrity.py
   ```

3. **Remove Artifact Deliverables:**
   ```bash
   rm -rf artifacts/PH01/A07
   ```

4. **Verify Clean Git Status:**
   ```bash
   git status
   ```

5. **Commit Rollback:**
   ```bash
   git commit -am "Rollback PH01 A07 SBOM and dependency integrity tooling"
   ```

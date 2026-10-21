# PH01 Rollback Procedure

## Scope
Phase PH01 establishes hermetic toolchain reproducibility, generates the CycloneDX SBOM, remediates SEC-CRIT-01, fixes DEFECT-01 (public route boundary), and fixes DEFECT-02 (Alembic migration 0062 constraint naming).

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard 2aa9016a57b49b53f1a433d076e1028a6ec45f64
   ```
2. **Selective Rollbacks:**
   - **Route Inventory Fix (DEFECT-01):**
     ```bash
     git checkout 2aa9016a57b49b53f1a433d076e1028a6ec45f64 -- services/api/src/clara_api/core/route_inventory.py
     ```
   - **Migration 0062 Fix (DEFECT-02):**
     ```bash
     git checkout 2aa9016a57b49b53f1a433d076e1028a6ec45f64 -- services/api/alembic/versions/20260824_0062_social_bookmarks_and_threading.py
     ```
   - **SBOM Tooling:**
     ```bash
     rm -f scripts/ops/generate_sbom.py scripts/ops/check_dependency_integrity.py services/api/tests/test_sbom_and_dependency_integrity.py
     ```
   - **Bootstrap Script:**
     ```bash
     rm -f scripts/ops/bootstrap_dev.sh scripts/ops/test_bootstrap_dev.sh docs/implementation/DEVELOPER_LOCAL_BOOTSTRAP.md
     ```
3. **Clean Worktrees:**
   ```bash
   for id in A01 A02 A03 A04 A05 A06 A07 A08 A09 A10; do
       git worktree remove --force "/tmp/opencode/worktrees/PH01_${id}" 2>/dev/null || true
       git branch -D "phase/ph01-${id,,}" 2>/dev/null || true
   done
   git worktree prune
   ```

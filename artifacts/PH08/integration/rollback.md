# PH08 Rollback Procedure

## Scope
Phase PH08 hardens GLHS dependency completeness and concurrency:
- Clinical dependency schema registry (`contracts/glhs/clinical_dependency_registry.v1.json`)
- Dependency derivation engine by mutation kind (`services/api/src/clara_api/db/dependency_derivation.py`)
- Entity-local OCC locking adapters (`services/api/src/clara_api/glhs/occ_locking_adapters.py`)
- Cross-partition write skew guards (`services/ml/src/clara_ml/write_skew_guard.py`)
- Mixed conflict resolver (`apps/web/lib/mixed-conflict-resolver.ts`)
- Mobile staleness rejection taxonomy (`apps/mobile/lib/core/staleness_taxonomy.dart`)
- Mobile clinical draft reconciliation tests (`services/api/tests/test_mobile_reconciliation.py`)
- Postgres randomized TOCTOU concurrency audit (`docs/security/POSTGRES_TOCTOU_CONCURRENCY_AUDIT.md`, `scripts/ops/simulate_toctou_concurrency.py`)
- Formal refinement proofs for OCC correctness (`docs/research/FORMAL_REFINEMENT_OCC_PROPERTIES.md`)
- Concurrency benchmark report & PH08 quality gate (`docs/reports/ph08-concurrency-hardening-audit.md`, `scripts/ci/ph08_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard 94ec2c1e2f0935d84114d800eff8e5da8e379a3c
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH08 --force
   ```

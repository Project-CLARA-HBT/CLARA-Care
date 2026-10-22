# PH49 Rollback Procedure

## Scope
Phase PH49 establishes GLHS operations and immutable lineage audit console:
- GLHS proposal redacted read API (`contracts/control-plane/`, `services/control-plane/src/clara_control/api/router.py`)
- Control GLHS provenance audits model and migration 0005 (`services/control-plane/src/clara_control/db/models.py`, `services/control-plane/alembic/versions/20260908_0005_glhs_provenance_audit.py`)
- GLHS reconciliation service & deny reason codes (`services/control-plane/src/clara_control/domain/glhs_reconciliation.py`)
- Read-only commit kernel introspection adapter (`services/api/src/clara_api/glhs/commit_kernel.py`)
- GLHS trace explorer & human review queue UI (`apps/admin/app/glhs/page.tsx`)
- GLHS evidence status badge component (`apps/admin/components/glhs_evidence_badge.tsx`)
- Adversarial lineage & snapshot parity tests (`services/control-plane/tests/test_glhs_lineage_adversarial_reconciliation.py`)
- Lineage anti-downgrade threat model (`docs/security/GLHS_LINEAGE_ANTI_DOWNGRADE_THREAT_MODEL.md`)
- Scientific claim linkage runbook (`docs/runbooks/scientific-claim-linkage-and-incident-support.md`)
- Adversarial replay audit & PH49 quality gate (`docs/reports/ph49-adversarial-replay-lineage-audit.md`, `scripts/ci/ph49_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard 670a050a124d9860a0f10fc2214f3938c7371a75
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH49 --force
   ```

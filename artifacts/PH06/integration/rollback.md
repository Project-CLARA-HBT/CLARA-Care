# PH06 Rollback Procedure

## Scope
Phase PH06 integrates mandatory THSS admission and proposal sealing into GLHS:
- AI-derived write routes contract inventory (`contracts/glhs/ai_derived_write_routes_inventory.v1.json`)
- Clinical proposal `admission_decision` column & migration 0066 (`services/api/src/clara_api/db/models.py`, `services/api/alembic/versions/20260902_0066_thss_mandatory_admission.py`)
- GRWC admission verifier and proposal sealing (`services/api/src/clara_api/glhs/admission.py`)
- Lineage anti-downgrade verifier (`services/ml/src/clara_ml/lineage_verifier.py`)
- Commit kernel OCC client & dependency vector builder (`apps/web/lib/commit-kernel-client.ts`)
- Mobile proposal decision modal sheet (`apps/mobile/lib/widgets/proposal_decision_sheet.dart`)
- Pending proposal lifecycle integration tests (`services/api/tests/test_thss_pending_proposal_state.py`)
- Stale-write and downgrade threat model (`docs/security/GLHS_STALE_WRITE_AND_DOWNGRADE_THREAT_MODEL.md`)
- Forensic trace redaction audit (`docs/research/GLHS_THSS_FORENSIC_TRACE_REDACTION_AUDIT.md`)
- Rollback runbook & PH06 quality gate (`docs/runbooks/thss-admission-rollback-and-compatibility.md`, `scripts/ci/ph06_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard 23703299659c5257573dcd800a64cb6b46f75e9b
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH06 --force
   ```

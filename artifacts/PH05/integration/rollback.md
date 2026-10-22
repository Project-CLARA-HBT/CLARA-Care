# PH05 Rollback Procedure

## Scope
Phase PH05 hardens consent, purpose, privacy, and authority policy:
- Versioned consent resource endpoints (`contracts/consent/`, `services/api/src/clara_api/api/v1/endpoints/auth.py`)
- Consent policy snapshot model & migration 0065 (`services/api/src/clara_api/db/models.py`, `services/api/alembic/versions/20260827_0065_consent_policy_snapshots.py`)
- Purpose-based policy evaluator (`services/api/src/clara_api/compliance/policy_evaluator.py`)
- ML policy epoch and revocation retrieval filtering (`services/ml/src/clara_ml/policy_epoch.py`)
- Web delegated authority restrictions (`apps/web/lib/delegated-authority.ts`)
- Mobile consent explanation UX sheet (`apps/mobile/lib/widgets/consent_explanation_sheet.dart`)
- Consent gates and append-only revocation test suite (`services/api/tests/test_consent_gates_and_revocation.py`)
- Consent drift security matrix (`docs/security/CONSENT_DRIFT_CONCURRENT_SECURITY_MATRIX.md`, `scripts/ops/audit_consent_drift.py`)
- Consent retention and DSAR impact specification (`docs/implementation/CONSENT_RETENTION_AND_DSAR_IMPACT.md`)
- Policy management runbook & PH05 quality gate (`docs/runbooks/consent-policy-management-and-owner-approval.md`, `scripts/ci/ph05_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard 1c626f461cd14dc61f7a84e6b4d713fc55bab565
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH05 --force
   ```

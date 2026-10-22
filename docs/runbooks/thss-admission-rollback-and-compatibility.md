# Runbook: THSS Admission Rollback & Compatibility Migration (PH06)

## 1. Overview
Governs emergency downgrade and backwards compatibility procedures for GLHS R4 Temporal Health State Snapshot (THSS) admission integration.

## 2. Compatibility Guarantees
- **Legacy Proposals (v1):** Historical proposals created before Phase PH06 lack `admission_decision` and `inference_context_binding_id`. The database schema defaults `admission_decision = 'PENDING'`.
- **Read Compatibility:** Historical commitment records remain fully readable and valid without retroactively inventing missing attestation receipts.

## 3. Rollback Procedure
If THSS admission verifier introduces unexpected rejections on clinical workflows:
1. **Revert Alembic Migration 0066:**
   ```bash
   cd services/api
   alembic downgrade -1
   ```
2. **Verify Downgrade Execution:**
   ```bash
   python3 scripts/ops/check_migration_downgrade.py services/api/alembic/versions
   ```
3. **Emergency Circuit Breaker:**
   If model inference is failing, Scribe and Council switch to manual clinician documentation without blocking patient care.

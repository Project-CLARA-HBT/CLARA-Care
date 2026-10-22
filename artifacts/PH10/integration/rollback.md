# PH10 Rollback Procedure

## Scope
Phase PH10 implements health data normalization and master patient health records:
- Clinical event assertion and evidence contract (`contracts/clinical/event_assertion_evidence.v1.json`)
- Medical vocabulary codes model and migration 0068 (`services/api/src/clara_api/db/models.py`, `services/api/alembic/versions/20260906_0068_medical_vocabulary_codes.py`)
- Clinical conflict and uncertainty preservation engine (`services/api/src/clara_api/lifemap/conflict_preservation.py`)
- Bi-temporal knowledge replay engine (`services/ml/src/clara_ml/bitemporal_replay.py`)
- Web clinical source provenance model (`apps/web/lib/clinical-provenance.ts`)
- Mobile PHR provenance badge widget (`apps/mobile/lib/widgets/phr_provenance_badge.dart`)
- Mobile measurement capture integration tests (`services/api/tests/test_mobile_measurement_capture.py`)
- Master record conflict-resolution golden evaluation (`docs/security/MASTER_RECORD_CONFLICT_RESOLUTION_AUDIT.md`, `scripts/ops/run_golden_conflict_tests.py`)
- Source authenticity and medical licensing audit (`docs/research/SOURCE_AUTHENTICITY_AND_LICENSING_AUDIT.md`)
- Vocabulary cutover runbook & PH10 quality gate (`docs/runbooks/clinical-data-dictionary-and-vocabulary-cutover.md`, `scripts/ci/ph10_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard d17260aa2f70b79fcce8965615d6a2f3068e217d
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH10 --force
   ```

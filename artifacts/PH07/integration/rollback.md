# PH07 Rollback Procedure

## Scope
Phase PH07 establishes GLHS transport, model-dispatch, and receipt integrity:
- D1 projection digest schema & contract (`contracts/glhs/d1_projection_contract.v1.json`, `services/api/src/clara_api/schemas.py`)
- D2 semantic envelope digest indexing & migration 0067 (`services/api/src/clara_api/db/models.py`, `services/api/alembic/versions/20260904_0067_glhs_d2_semantic_digest_index.py`)
- GLHS transport verifier & D3 egress check (`services/api/src/clara_api/glhs/transport_verifier.py`)
- Server-attested model inference dispatch (`services/ml/src/clara_ml/attested_dispatch.py`)
- Web model registry client & provider binding (`apps/web/lib/model-registry.ts`)
- Mobile model dispatch lifecycle state machine (`apps/mobile/lib/core/dispatch_lifecycle.dart`)
- User-facing attestation disclosure integration tests (`services/api/tests/test_glhs_attestation_disclosure.py`)
- Transport serialization fuzz tests (`docs/security/TRANSPORT_SERIALIZATION_FUZZ_TESTS.md`, `scripts/ops/fuzz_transport_serialization.py`)
- Cryptographic key lifecycle audit specification (`docs/research/CRYPTOGRAPHIC_KEY_LIFECYCLE_AND_AUDIT.md`)
- Receipt tier audit & PH07 quality gate (`docs/reports/ph07-glhs-transport-and-receipt-audit.md`, `scripts/ci/ph07_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard e8533cb02932ae88e6ce32735f45e5eac48271e7
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH07 --force
   ```

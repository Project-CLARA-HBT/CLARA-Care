# PH40 Rollback Procedure

## Scope
Phase PH40 establishes the forensic inventory of mocks, skeletons, and fake successes across the codebase:
- Web route capability inventory & control router (`contracts/control-plane/`, `services/control-plane/src/clara_control/api/`)
- Control-plane DB models & route enumeration (`services/control-plane/src/clara_control/db/`)
- Domain route dependency traversal (`services/control-plane/src/clara_control/domain/`)
- ML provider safe-fallback boundaries (`services/ml/src/clara_ml/llm/audit_boundaries.py`)
- Web UI button disabled state audit (`artifacts/PH40/A05/ui_fixture_and_dead_button_audit.json`)
- Mobile screen entrypoint & dark flag audit (`artifacts/PH40/A06/mobile_screen_entrypoints_audit.json`)
- Cross-layer zero-mock integration test suite (`services/api/tests/test_mock_and_synthetic_fixtures.py`)
- False-success security audit (`docs/security/MOCK_SKELETON_FALSE_SUCCESS_SECURITY_AUDIT.md`)
- Standardized issue taxonomy (`docs/implementation/MOCK_SKELETON_ISSUE_TAXONOMY.md`)
- Adversarial review & PH40 quality gate (`docs/reports/ph40-mock-forensic-inventory-audit.md`, `scripts/ci/ph40_quality_gate.py`)

## Rollback Procedures
1. **Full Phase Rollback to Base Commit:**
   ```bash
   git reset --hard db1ba377c0bc9093c18d0296821672aaff223c9d
   ```
2. **Worktree Cleanup:**
   ```bash
   python3 scripts/ops/worktree_manager.py --cleanup --phase PH40 --force
   ```

# Rollback Plan — PH40 A07 (Zero-Mock CI Detector & Fixture Tests)

## Rollback Procedure
1. Remove created test file:
   ```bash
   rm -f services/api/tests/test_mock_and_synthetic_fixtures.py
   ```
2. Remove deliverables:
   ```bash
   rm -rf artifacts/PH40/A07
   ```
3. Verification:
   ```bash
   git status
   ```

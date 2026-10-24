# Rollback Plan — PH51 A08 (Revoked-Consent Replay & SSRF Mitigation)

## Rollback Procedure
1. Remove threat model, test file, and artifacts:
   ```bash
   rm -f docs/security/REVOKED_CONSENT_JOB_REPLAY_AND_CONNECTOR_SSRF_THREAT_MODEL.md
   rm -f services/control-plane/tests/security/test_ssrf_and_revoked_consent_negative.py
   rm -rf artifacts/PH51/A08
   ```
2. Verification:
   ```bash
   git status
   ```

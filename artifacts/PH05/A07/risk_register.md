# Risk Register — PH05 A07 (Consent Gates & Revocation Tests)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH05-A07-01 | Race condition in concurrent grant/revoke leaving inconsistent consent state | High | Low | Core ledger locks on user consent anchor (`acquire_consent_lock_anchor`). | Mitigated |
| RISK-PH05-A07-02 | In-memory session caches bypassing revoked consent check | High | Low | Verification tests validate DB ledger status reflects latest event immediately upon transaction commit. | Mitigated |

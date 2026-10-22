# Risk Register — PH07 A09 (Cryptographic Key Lifecycle)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH07-A09-01 | Stale keys retained in validator rings beyond decommissioning schedule | High | Low | Automated rotation cron job purges expired keys after 14-day overlap window. | Mitigated |
| RISK-PH07-A09-02 | Compromised private key allowing receipt forgery | Critical | Low | Key revocation immediately drops key from verification set, invalidating forged receipts. | Mitigated |

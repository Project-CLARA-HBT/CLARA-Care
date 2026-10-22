# Risk Register — PH42 A02 (Constrained Session/Device TTL Schema)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH42-A02-01 | Unbounded session lifetime allowing session hijacking persistence | Critical | Low | Hard enforced `expires_at` column indexed for automated TTL cleanup sweeps. | Mitigated |
| RISK-PH42-A02-02 | Session revocation not reflected immediately across concurrent requests | High | Low | Indexed `is_revoked` boolean column checked in query paths. | Mitigated |

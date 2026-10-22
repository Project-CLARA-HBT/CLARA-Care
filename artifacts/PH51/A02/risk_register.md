# Risk Register — PH51 A02 (Job States, Leases & Retry Ledger)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH51-A02-01 | Unbounded table scan when workers poll for next available job | High | Low | Composite indexes on `(status, lease_expires_at)` optimize worker claim queries. | Mitigated |
| RISK-PH51-A02-02 | Stale lease lock preventing recovery from crashed worker | High | Low | `lease_expires_at` timestamp allows peer workers to reclaim abandoned jobs. | Mitigated |

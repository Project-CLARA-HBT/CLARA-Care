# Risk Register — PH41 A02 (Control-Plane Schema & Migration Plan)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH41-A02-01 | Shared database engine creating cross-boundary privilege escalation risk | Critical | Low | Control-plane database configuration uses segregated URL and connection pool with dedicated credentials. | Mitigated |
| RISK-PH41-A02-02 | Incomplete downgrade logic causing migration rollback deadlock | High | Low | Initial migration drops all 4 declared control plane tables cleanly during downgrade. | Mitigated |

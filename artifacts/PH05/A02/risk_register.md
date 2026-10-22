# Risk Register — PH05 A02 (Consent Policy Snapshots Persistence)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH05-A02-01 | In-place modification of accepted consent text creating compliance audit invalidation | Critical | Low | Policy snapshots are strictly immutable with distinct `policy_version` and `content_hash` attributes. | Mitigated |
| RISK-PH05-A02-02 | SQLite/PostgreSQL DDL syntax discrepancy during table creation | Medium | Low | Standard SQLAlchemy core types used with batch alter compatibility. | Mitigated |

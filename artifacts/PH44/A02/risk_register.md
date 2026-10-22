# Risk Register — PH44 A02 (Org Slug & Lifecycle Status Migration)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH44-A02-01 | Suspended tenant retaining active login capabilities | Critical | Low | Status `SUSPENDED` indexed and validated on all data-plane auth queries. | Mitigated |
| RISK-PH44-A02-02 | Column addition locking control database | Medium | Low | Non-null column added with non-null `server_default="ACTIVE"`. | Mitigated |

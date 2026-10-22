# Risk Register — PH06 A02 (THSS Mandatory Admission Decision)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH06-A02-01 | Stale proposals committed directly without explicit reviewer admission decision | Critical | Low | Database default is 'PENDING'; commit kernel enforces 'ADMITTED' status invariant. | Mitigated |
| RISK-PH06-A02-02 | SQLite/PostgreSQL batch alter column addition lock contention | Medium | Low | Batch alter table syntax with non-null server_default applied cleanly. | Mitigated |

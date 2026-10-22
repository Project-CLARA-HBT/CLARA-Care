# Risk Register — PH09 A02 (Idempotent Outbox Publisher)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH09-A02-01 | Outbox event committed without parent database transaction succeeding | Critical | Low | Publisher flushes within the caller's active SQLAlchemy session; single transactional boundary commits both. | Mitigated |
| RISK-PH09-A02-02 | Poison pill event stuck retrying indefinitely, exhausting queue | High | Low | Events transition to `dead_letter` status upon reaching `max_attempts`. | Mitigated |

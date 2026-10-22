# Risk Register — PH08 A08 (Postgres TOCTOU Concurrency Audit)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH08-A08-01 | Read-skew in concurrent transactions reading partition without shared locks | High | Low | Lock plan mandates SHARED lock on read dependencies and EXCLUSIVE lock on write partitions. | Mitigated |
| RISK-PH08-A08-02 | Heavy lock contention during mass simultaneous patient chart reviews | Medium | Low | Fine-grained entity-local partition keys prevent full-table database locks. | Mitigated |

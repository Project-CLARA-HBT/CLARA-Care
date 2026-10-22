# Risk Register — PH08 A03 (Entity-Local OCC Locking Adapters)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH08-A03-01 | Deadlock during concurrent multi-partition updates | Critical | Low | Strict lexicographical sorting of entity keys prior to acquiring row-level locks. | Mitigated |
| RISK-PH08-A03-02 | Stale read committed due to lock acquisition after read phase | High | Low | Phase 3 revalidation under lock asserts observed version matches current partition version. | Mitigated |

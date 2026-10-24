# Risk Register — PH51 A07 (Worker Death, Duplicate & TTL Expiration Tests)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH51-A07-01 | Flaky tests caused by real wall-clock sleep timing | Medium | Low | Tests parameterize synthetic UTC timestamps (`t0 + delta`) avoiding flaky `time.sleep()`. | Mitigated |
| RISK-PH51-A07-02 | Split-brain lease acquisition if two workers claim simultaneously | Critical | Low | Lease check verifies atomic lease expiry condition (`lease_expires_at is None or lease_expires_at <= now`). | Mitigated |

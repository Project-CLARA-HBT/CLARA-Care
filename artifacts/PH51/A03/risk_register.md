# Risk Register — PH51 A03 (Job Requeue, Idempotency & Consent Recheck)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH51-A03-01 | Requeue of job processing patient data after consent was explicitly withdrawn | Critical | Low | Hard gate verifies active user consent purposes before altering job status from DEAD_LETTER. | Mitigated |
| RISK-PH51-A03-02 | Concurrent replay calls creating duplicate execution workers | High | Low | State check returns ALREADY_ACTIVE if job status is already RUNNING or PENDING. | Mitigated |

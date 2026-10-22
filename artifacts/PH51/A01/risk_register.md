# Risk Register — PH51 A01 (Admin Job Queue API & Safe DTO)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH51-A01-01 | Webhook auth credentials or patient PHI leaked in job inspection payload | Critical | Low | DTO response emits strictly metadata (queue, status, attempt counters, error codes). | Mitigated |
| RISK-PH51-A01-02 | Uncontrolled replay of job flooding external hospital webhook | High | Low | Replay resets attempts to 0 and re-enters exponential backoff schedule. | Mitigated |

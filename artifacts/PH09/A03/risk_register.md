# Risk Register — PH09 A03 (Outbox Retry & DLQ Policy)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH09-A03-01 | Thundering herd during recovery from downstream message broker outage | High | Low | Random jitter (0.8x to 1.2x) added to exponential backoff prevents synchronized retries. | Mitigated |
| RISK-PH09-A03-02 | Silent dropping of failed events without operator notification | High | Low | Dead-lettered events record timestamp and error code; monitored via DLQ alarm metrics. | Mitigated |

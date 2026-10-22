# Risk Register — PH09 A04 (API Event Subscriptions)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH09-A04-01 | Event subscriber crash blocking overall outbox queue progression | High | Low | Subscribers execute asynchronously and record independent execution states. | Mitigated |
| RISK-PH09-A04-02 | Duplicate event dispatch causing redundant vector embedding re-computations | Medium | Low | Idempotency key tracking in subscribers de-duplicates incoming event IDs. | Mitigated |

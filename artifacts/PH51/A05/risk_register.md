# Risk Register — PH51 A05 (Job Queues, Outbox & Connector Console)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH51-A05-01 | Unredacted patient PHI rendered in job inspection view | Critical | Low | Inspector modal deliberately excludes raw request payloads; shows only queue identifiers and error codes. | Mitigated |
| RISK-PH51-A05-02 | Accidental double-replay invocation causing flood | High | Low | UI updates job state immediately on trigger and disables replay button for non-DLQ jobs. | Mitigated |

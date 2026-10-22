# Risk Register — PH09 A01 (Outbox Domain Event Schema)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH09-A01-01 | Event consumers receiving unredacted patient medical records | Critical | Low | Contract stipulates strictly pseudonymized payloads with zero raw patient identifying markers. | Mitigated |
| RISK-PH09-A01-02 | Unrecognized event types causing downstream deserialization failure | Medium | Low | Canonical `supported_event_types` registry governs all emitted outbox records. | Mitigated |

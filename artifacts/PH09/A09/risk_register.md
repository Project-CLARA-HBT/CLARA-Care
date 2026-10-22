# Risk Register — PH09 A09 (PHI-Minimized Event Payload Security)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH09-A09-01 | Developer adding sensitive medical fields directly into outbox payload dictionary | Critical | Low | CI claim lint and schema validator check for presence of disallowed PII keys. | Mitigated |
| RISK-PH09-A09-02 | Pseudonymized UUID linkage allowing correlation across external services | Medium | Low | Public UUIDs generated per profile and distinct from internal database integer keys. | Mitigated |

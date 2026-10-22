# Risk Register — PH44 A01 (Tenant Organization REST Contract)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH44-A01-01 | Suspended tenant organization continuing to issue client invitations | High | Low | Endpoint `/control/v1/tenants/{id}/suspend` disables invitation acceptance immediately. | Mitigated |
| RISK-PH44-A01-02 | Slug collision creating tenant routing ambiguity | Critical | Low | Slug format constrained and uniqueness enforced in database schema. | Mitigated |

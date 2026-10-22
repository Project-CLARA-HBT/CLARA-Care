# Risk Register — PH44 A03 (Organization Lifecycle & Invitations)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH44-A03-01 | Replay of signed invitation token to join multiple clinics | High | Low | Invitation tokens encode target `tenant_id` and single-use redemption marks. | Mitigated |
| RISK-PH44-A03-02 | Suspended organization users continuing to read clinical notes | Critical | Low | Data-plane authorization checks `is_tenant_active()` returning 403 when suspended. | Mitigated |

# Risk Register — PH44 A07 (Suspended Org & Invite Replay)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH44-A07-01 | Replaying expired invitation token | High | Low | Token encodes epoch expiry timestamp and HMAC signature; expired tokens fail closed. | Mitigated |
| RISK-PH44-A07-02 | Suspended clinic users continuing to issue invitations | Critical | Low | Onboarding manager evaluates `is_tenant_active` before generating or verifying invitations. | Mitigated |

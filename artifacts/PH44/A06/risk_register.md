# Risk Register — PH44 A06 (Signed Invite & Membership Components)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH44-A06-01 | Sharing invitation link publicly allowing arbitrary user account escalation | Critical | Low | Link is bound to explicit recipient email and role; server rejects unmatching redemptions. | Mitigated |
| RISK-PH44-A06-02 | Overriding seat limit quotas through mass invitation generation | High | Low | Generation checks active user count against `max_users` ceiling before minting token. | Mitigated |

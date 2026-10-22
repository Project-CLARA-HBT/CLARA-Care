# Risk Register — PH42 A08 (OIDC MFA Step-Up & Token Theft Threat Model)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH42-A08-01 | Stolen session cookie executing destructive root actions | Critical | Low | Privileged mutations require elevated `step_up_level == "PRIVILEGED"` with active 30-minute window. | Mitigated |
| RISK-PH42-A08-02 | Compromised developer workstation retaining valid administrative tokens | High | Low | Revocation API allows one-click termination of all other sessions, invalidating token family. | Mitigated |

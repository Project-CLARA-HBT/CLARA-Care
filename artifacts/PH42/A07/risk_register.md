# Risk Register — PH42 A07 (OIDC MFA Step-Up & Session Fixation)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH42-A07-01 | Regression permitting revoked session token reuse | Critical | Low | Continuous test suite validates revocation introspection immediately returns 401. | Mitigated |
| RISK-PH42-A07-02 | Step-up bypass with forged parameters | Critical | Low | Assertions enforce validation of TOTP code format and value. | Mitigated |

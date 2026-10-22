# Risk Register — PH42 A05 (Admin Sign-In & MFA Step-Up Flows)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH42-A05-01 | Phishing of admin credentials via consumer login interface | Critical | Low | Admin login page is isolated on separate domain/port and strictly enforces MFA step-up. | Mitigated |
| RISK-PH42-A05-02 | Brute forcing MFA TOTP codes on admin account | High | Low | Rate limits and exponential delay lockouts apply to failed step-up attempts. | Mitigated |

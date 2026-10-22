# Risk Register — PH42 A01 (Session Lifecycle & Step-Up Contract)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH42-A01-01 | Step-up bypass allowing standard session to execute root mutations | Critical | Low | Step-up endpoint requires valid 6-digit MFA code and shortens TTL to 30 minutes. | Mitigated |
| RISK-PH42-A01-02 | Session revocation latency across distributed workers | High | Low | Introspection endpoint performs active status check against database `is_revoked`. | Mitigated |

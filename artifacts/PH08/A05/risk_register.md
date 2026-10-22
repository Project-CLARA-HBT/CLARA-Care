# Risk Register — PH08 A05 (Mixed Conflict Rules)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH08-A05-01 | Treating consent revocation as recoverable version conflict and auto-retrying | Critical | Low | Resolver assigns `autoRetryAllowed = false` and hard-stops when consent is revoked. | Mitigated |
| RISK-PH08-A05-02 | Uninformative generic error banner causing clinician confusion | Medium | Low | Distinct Vietnamese and English guidance provided for each conflict category. | Mitigated |

# Risk Register — PH05 A08 (Consent Drift Security Matrix)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH05-A08-01 | Silent drift between server policy version and stored client consent | Critical | Low | Strict server version matching blocks access until user re-acknowledges new terms. | Mitigated |
| RISK-PH05-A08-02 | Race conditions in concurrent multi-device consent mutation | High | Low | Lock anchor hierarchy ensures deterministic transaction serialization. | Mitigated |

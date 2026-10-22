# Risk Register — PH07 A04 (Server-Attested Inference Dispatch)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH07-A04-01 | Model receipt spoofing by upstream proxy | High | Low | Provider receipt digest binds attempt ID, exact transport hash, and signing key ID. | Mitigated |
| RISK-PH07-A04-02 | Dispatch timeout leading to ungrounded fallback | Critical | Low | Timeout trips circuit breaker directly to safe clinician review rather than fake output. | Mitigated |

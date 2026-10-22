# Risk Register — PH05 A03 (Purpose-Based Policy Evaluator)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH05-A03-01 | Processing user queries when research or cross-border consent was explicitly revoked | Critical | Low | Policy evaluator checks active unrevoked grants via `has_consent` on every evaluated intent. | Mitigated |
| RISK-PH05-A03-02 | Delegated authority proxy exceeding permissible scope | High | Low | Explicit relationship validation rejects unauthorized actor roles with fail-closed denial. | Mitigated |

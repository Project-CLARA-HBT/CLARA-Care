# Risk Register — PH43 A05 (Role & Permission Matrix UI)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH43-A05-01 | Unapproved inline editing of roles allowing unauthorized privilege grant | Critical | Low | Matrix is strictly read-only; role modifications require dual-operator approval workflow. | Mitigated |
| RISK-PH43-A05-02 | UI displaying mock or fabricated permissions not supported by backend | Medium | Low | Permissions rendered conform strictly to canonical schema registry. | Mitigated |

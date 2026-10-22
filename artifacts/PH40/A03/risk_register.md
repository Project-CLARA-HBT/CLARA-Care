# Risk Register — PH40 A03 (Route Dependency Traversal)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH40-A03-01 | Unmapped async background worker tasks causing silent failures in production | High | Low | Traversal engine detects missing worker bindings and flags ungrounded execution paths. | Mitigated |
| RISK-PH40-A03-02 | Incomplete fallback safety declarations leading to fail-open vulnerability | High | Low | Explicit `fallback_safety` policy enforced on all critical clinical paths (e.g. FIDES drug safety, emergency escalation). | Mitigated |

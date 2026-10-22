# Risk Register — PH09 A10 (Outbox Operator Runbook & Quality Gate)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH09-A10-01 | Replaying a poisoned event repeatedly crashing downstream workers | High | Low | Runbook mandates inspecting and resolving root cause prior to issuing manual replay. | Mitigated |
| RISK-PH09-A10-02 | Quality gate drift from frozen baseline commit invariants | High | Low | Automated SHA verification anchored to pinned commit with DAG merge-base descent checks. | Mitigated |

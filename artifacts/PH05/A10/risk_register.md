# Risk Register — PH05 A10 (Policy Language & Owner Approval)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH05-A10-01 | Unilateral policy text modification by developers without clinical sign-off | Critical | Low | Runbook mandates dual approval from Chief Medical Officer and DPO prior to database publication. | Mitigated |
| RISK-PH05-A10-02 | Quality gate drift from frozen baseline commit invariants | High | Low | Automated SHA verification anchored to pinned commit with DAG merge-base descent checks. | Mitigated |

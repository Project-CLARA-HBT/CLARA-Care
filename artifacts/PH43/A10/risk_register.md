# Risk Register — PH43 A10 (Cross-Tenant IDOR & Quality Gate)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH43-A10-01 | IDOR vulnerability allowing clinic administrator to access peer clinic records | Critical | Low | Scoped SQL `WHERE tenant_id == :user_tenant` and policy engine deny-by-default. | Mitigated |
| RISK-PH43-A10-02 | Quality gate drift from frozen baseline commit invariants | High | Low | Automated SHA verification anchored to pinned commit with DAG merge-base descent checks. | Mitigated |

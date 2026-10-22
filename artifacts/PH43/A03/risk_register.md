# Risk Register — PH43 A03 (Control-Plane Policy Evaluator)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH43-A03-01 | Tenant administrator managing users in another clinic | Critical | Low | Strict check `target_tenant_id in authorized_tenant_ids` fails closed with 403. | Mitigated |
| RISK-PH43-A03-02 | Unintended permission expansion via complex ABAC rule interactions | High | Low | Deny-by-default terminal rule rejects any non-explicitly allowed action. | Mitigated |

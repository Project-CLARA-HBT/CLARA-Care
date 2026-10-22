# Risk Register — PH43 A02 (Role Binding Schema & Org FKs)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH43-A02-01 | Orphaned role bindings remaining after tenant deletion | High | Low | Foreign key constraints enforce `ON DELETE CASCADE` on `tenant_id`. | Mitigated |
| RISK-PH43-A02-02 | Cross-tenant role assignment escalation | Critical | Low | Role binding schema couples `tenant_id` directly to each assigned permission set. | Mitigated |

# Risk Register — PH43 A01 (RBAC/ABAC Permission Registry)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH43-A01-01 | Implicit permission grant allowing platform administrator to access tenant patient PHI | Critical | Low | Invariant `platform_root_cannot_read_phi = true` strictly excludes clinical scopes. | Mitigated |
| RISK-PH43-A01-02 | Broad wildcard matching (`*`) granting unauthorized privilege escalation | High | Low | Deny-by-default architecture rejects unlisted permissions explicitly. | Mitigated |

# Risk Register — PH40 A02 (Control-Plane DB Models & Route Reflection)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH40-A02-01 | Accidental coupling of control-plane admin models with end-user clinical PHI tables | High | Low | Segregated package `clara_control.db` completely independent from `clara_api.db.models`; separate engine and connection pool. | Mitigated |
| RISK-PH40-A02-02 | Unregistered API routes bypassing OpenAPI documentation and RBAC gate | Medium | Low | Authoritative route-reflection engine `build_route_inventory` validates route coverage against intentional allowlist. | Mitigated |

# Risk Register — PH42 A04 (Legacy Admin Deprecation & Sunset Headers)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH42-A04-01 | Client breakage upon abrupt shutdown of legacy /admin endpoints | High | Low | RFC 8594 standard `Sunset` and `Deprecation` headers provide structured notice until cutover date. | Mitigated |
| RISK-PH42-A04-02 | Client-side role spoofing bypassing server RBAC | Critical | Low | Deprecation notice reaffirms that server-side `require_roles('admin')` remains enforced. | Mitigated |

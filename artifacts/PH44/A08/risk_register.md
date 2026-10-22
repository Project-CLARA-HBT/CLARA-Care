# Risk Register — PH44 A08 (Tenant Bleed & Malicious Org Owner Threat Model)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH44-A08-01 | SQL injection parameter manipulating tenant ID scoping | Critical | Low | Scoped adapters use parameterized SQLAlchemy statements with identifier regex validation. | Mitigated |
| RISK-PH44-A08-02 | Organization administrator locking out peer administrators maliciously | High | Low | Minimum dual-admin threshold and break-glass emergency recovery runbooks prevent lockouts. | Mitigated |

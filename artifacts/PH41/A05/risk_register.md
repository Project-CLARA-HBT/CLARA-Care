# Risk Register — PH41 A05 (Independent Admin Route Tree)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH41-A05-01 | Shared browser cookie scope between admin control plane and consumer web app | High | Low | Hosted on segregated domain/origin (e.g. `admin.theclaracare.com` or dedicated port 8200). | Mitigated |
| RISK-PH41-A05-02 | Unauthenticated access to admin pages | Critical | Low | Gated by OIDC/MFA session verification enforced on all admin layout roots. | Mitigated |

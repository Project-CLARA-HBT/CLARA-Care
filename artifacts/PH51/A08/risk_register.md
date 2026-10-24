# Risk Register — PH51 A08 (Revoked-Consent Replay & SSRF Mitigation)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH51-A08-01 | DNS rebinding bypass where domain resolves to public IP during validation then private IP during fetch | Critical | Low | Egress HTTP adapter uses socket pin hooks to reject connections that resolve to RFC 1918 addresses at connect time. | Mitigated |
| RISK-PH51-A08-02 | Stale cached consent purpose used during async job execution | High | Low | Replay kernel queries primary DB replica with read-your-writes guarantees. | Mitigated |

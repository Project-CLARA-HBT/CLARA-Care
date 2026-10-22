# Risk Register — PH43 A04 (Secondary Server Guard in Health Adapter)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH43-A04-01 | Header injection via malformed organization IDs | High | Low | Regex pattern `^[a-zA-Z0-9_-]{3,64}$` rejects control characters or SQL metacharacters. | Mitigated |
| RISK-PH43-A04-02 | Secondary guard interfering with valid platform-level health probes | Medium | Low | Organization header is optional; platform telemetry functions without org scope cleanly. | Mitigated |

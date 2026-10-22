# Risk Register — PH41 A01 (OpenAPI Control Baseline & Health Schema)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH41-A01-01 | Unauthenticated access to control-plane tenant management endpoints | Critical | Low | Control-plane architecture requires dedicated service-token gateway and network isolation. | Mitigated |
| RISK-PH41-A01-02 | Schema drift between OpenAPI contract and FastAPI handler implementations | Medium | Low | OpenAPI spec generated dynamically from live FastAPI router instance. | Mitigated |

# Risk Register — PH41 A04 (Authenticated Health API Adapter)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH41-A04-01 | Unauthenticated exposure of internal telemetry components | High | Low | Requires non-empty `X-Control-Service-Token` header, returning HTTP 401 on missing token. | Mitigated |
| RISK-PH41-A04-02 | Telemetry queries unintentionally joining patient tables and leaking PHI | Critical | Low | Zero queries issued to patient tables; inspects only process ID, runtime, and pool counters. | Mitigated |

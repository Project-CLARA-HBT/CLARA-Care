# Risk Register — PH10 A04 (Bi-Temporal Knowledge Replay)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH10-A04-01 | Retrospective data leakage corrupting clinical ML historical evaluation | High | Low | Replay engine asserts transaction-time cutoff, hiding facts recorded after evaluation date. | Mitigated |
| RISK-PH10-A04-02 | Clock skew in distributed timestamps altering replay order | Medium | Low | All timestamps normalized to ISO 8601 UTC with monotonic sequencing. | Mitigated |

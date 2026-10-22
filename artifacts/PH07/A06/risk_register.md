# Risk Register — PH07 A06 (Failed/Timeout Dispatch Lifecycle)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH07-A06-01 | Infinite spinner / UI hang when remote AI inference model stalls | High | Low | Hard client-side timeout transition surfaces localized retry message cleanly. | Mitigated |
| RISK-PH07-A06-02 | Client fabricating artificial response upon timeout | Critical | Low | Dispatch lifecycle transitions strictly to terminal `timedOut`/`failed` status. | Mitigated |

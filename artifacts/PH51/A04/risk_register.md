# Risk Register — PH51 A04 (Health API Outbox & Connector Status Adapters)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH51-A04-01 | Outbox event enqueue failure causes sync request to fail silently | High | Low | Event creation runs inside database transaction alongside audit record. | Mitigated |
| RISK-PH51-A04-02 | Sensitive device credentials exposed via connector status adapter | High | Low | Status adapter returns strictly counts and booleans, no vendor tokens or device serials. | Mitigated |

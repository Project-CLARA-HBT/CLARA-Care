# Risk Register — PH51 A09 (DLQ Runbook & Webhook SLO)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH51-A09-01 | Unclear incident escalation leading to DLQ buildup exceeding SLO threshold | Medium | Low | Runbook specifies exact alert thresholds (<30m dwell time) and curl commands for triage. | Mitigated |
| RISK-PH51-A09-02 | Operator bypassing consent recheck during emergency DLQ flush | High | Low | Runbook mandates verifying patient consent purpose before initiating replay. | Mitigated |

# Risk Register — PH09 A05 (Async Job Monitoring SSE/Polling)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH09-A05-01 | Unbounded SSE stream connection leaking client memory on background tab | Medium | Low | Monitor automatically closes stream upon reaching terminal status (`completed`, `failed`, `dead_letter`). | Mitigated |
| RISK-PH09-A05-02 | Polling flood exhausting backend web server during massive queue backlog | High | Low | Polling interval is throttled to 2000ms and terminates upon job completion. | Mitigated |

# Risk Register — PH09 A08 (Queue Failure & Recovery Tests)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH09-A08-01 | Crash loop backoff starving queue when external webhook is down | High | Low | Maximum attempts ceiling (default 8) shifts un-deliverable events to dead-letter state. | Mitigated |
| RISK-PH09-A08-02 | Competing workers double-delivering events on lease boundary race | High | Low | Lease acquisition uses atomic `UPDATE ... RETURNING` with row-level locks. | Mitigated |

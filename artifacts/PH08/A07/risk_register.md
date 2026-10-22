# Risk Register — PH08 A07 (Mobile Reconciliation UI Tests)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH08-A07-01 | Clinician loses multi-paragraph consultation SOAP note on version collision | Critical | Low | Reconciliation architecture caches draft locally and prompts clinician with visual diff merge. | Mitigated |
| RISK-PH08-A07-02 | Silent retry with stale draft overwriting newer medication changes | High | Low | Automated retry allowed only for background read syncs; mutations require explicit user confirmation. | Mitigated |

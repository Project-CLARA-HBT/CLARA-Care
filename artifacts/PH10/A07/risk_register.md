# Risk Register — PH10 A07 (Mobile Measurement Capture)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH10-A07-01 | Corrupted sensor reading triggering false emergency escalation | Critical | Low | Normalization logic applies physiological sanity filters prior to clinical inference dispatch. | Mitigated |
| RISK-PH10-A07-02 | Ambiguity in blood glucose units (mg/dL vs mmol/L) | High | Low | Schemas require explicit UCUM unit tags and validate value ranges against expected scale. | Mitigated |

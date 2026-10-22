# Risk Register — PH10 A03 (Clinical Conflict Preservation)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH10-A03-01 | Silent overwrite of earlier clinician notes upon second opinion entry | Critical | Low | Conflict engine appends assertions as parallel competing claims rather than overwriting. | Mitigated |
| RISK-PH10-A03-02 | Patient dispute ignored in clinical decision support reasoning | High | Low | Reasoning pipelines inspect assertion `status == 'DISPUTED'` and surface uncertainty alerts. | Mitigated |

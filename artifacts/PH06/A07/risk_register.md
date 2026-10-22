# Risk Register — PH06 A07 (Mobile Pending Proposal State)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH06-A07-01 | Unadmitted proposal executing commitment transition | Critical | Low | Commit kernel enforces proposal admission check prior to executing transition Phase 4. | Mitigated |
| RISK-PH06-A07-02 | Rejected proposal lingering in mobile client queue | Medium | Low | Status reconciliation purges or marks rejected items in client pending cache. | Mitigated |

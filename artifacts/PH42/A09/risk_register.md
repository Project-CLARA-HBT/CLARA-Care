# Risk Register — PH42 A09 (Emergency Root Recovery Runbook)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH42-A09-01 | Rogue operator unilaterally triggering break-glass root recovery | Critical | Low | Two-operator quorum required; secret shares split between SRE Lead and Security Officer. | Mitigated |
| RISK-PH42-A09-02 | Key shares lost during emergency leaving system unrecoverable | Critical | Low | 2-of-3 Shamir threshold allows recovery even if one share is inaccessible. | Mitigated |

# Risk Register — PH06 A01 (AI-Derived Write Routes Inventory)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH06-A01-01 | Model-generated clinical recommendation directly writing to health record without clinician review | Critical | Low | All AI write routes mandate `requires_human_admission=true` through THSS commitment proposals. | Mitigated |
| RISK-PH06-A01-02 | Unaudited route added bypassing THSS admission invariant | High | Low | Contract inventory is tested continuously by CI traceability detectors. | Mitigated |

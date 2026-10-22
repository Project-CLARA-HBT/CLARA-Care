# Risk Register — PH10 A02 (Vocabulary Code Mapping Registry)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH10-A02-01 | Ambiguous code collisions across different coding systems | High | Low | Table enforces composite unique constraint on `(system, code)`. | Mitigated |
| RISK-PH10-A02-02 | Inaccurate clinical coding mapping altering medication safety alerts | Critical | Low | Mappings require explicit curation source and audit timestamps. | Mitigated |

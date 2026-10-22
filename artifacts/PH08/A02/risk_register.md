# Risk Register — PH08 A02 (Dependency Derivation Rules)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH08-A02-01 | Omission of critical read dependency allowing write skew across partitions | Critical | Low | Engine explicitly binds both governance policy epoch and entity keys. | Mitigated |
| RISK-PH08-A02-02 | Unrecognized mutation kind bypassing OCC validation | High | Low | Engine provides safe default fallback deriving entity write partition and default epoch. | Mitigated |

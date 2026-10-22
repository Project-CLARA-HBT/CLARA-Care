# Risk Register — PH07 A10 (Receipt Tier Claims & Quality Gate)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH07-A10-01 | Third-party provider changing JSON serialization subtly breaking D3 match | High | Low | Provider receipts verified against provider public key; D3 binds local egress socket bytes. | Mitigated |
| RISK-PH07-A10-02 | Quality gate drift from frozen baseline commit invariants | High | Low | Automated SHA verification anchored to pinned commit with DAG merge-base descent checks. | Mitigated |

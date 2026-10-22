# Risk Register — PH49 A10 (Lineage Replay & Quality Gate)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH49-A10-01 | Rogue proposal replaying historical transition under altered snapshot | Critical | Low | GRWC admission verifies proposal digest, root binding, and exact snapshot ID. | Mitigated |
| RISK-PH49-A10-02 | Quality gate drift from frozen baseline commit invariants | High | Low | Automated SHA verification anchored to pinned commit with DAG merge-base descent checks. | Mitigated |

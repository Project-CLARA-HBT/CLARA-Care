# Risk Register — PH08 A10 (Benchmark & Quality Gate)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH08-A10-01 | Lock acquisition ordering regression causing intermittent deadlock under load | Critical | Low | Strict adherence to total order: Class 1-7 and UTF-8 key byte sort in lock plan. | Mitigated |
| RISK-PH08-A10-02 | Quality gate drift from frozen baseline commit invariants | High | Low | Automated SHA verification anchored to pinned commit with DAG merge-base descent checks. | Mitigated |

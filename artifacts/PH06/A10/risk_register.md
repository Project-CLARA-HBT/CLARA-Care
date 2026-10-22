# Risk Register — PH06 A10 (Rollback & Compatibility Plan)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH06-A10-01 | Migration 0066 failure blocking production clinical workflows | Critical | Low | Non-null `admission_decision` column includes server_default='PENDING'; tested with SQLite and PostgreSQL syntax. | Mitigated |
| RISK-PH06-A10-02 | Quality gate drift from frozen baseline commit invariants | High | Low | Automated SHA verification anchored to pinned commit with DAG merge-base descent checks. | Mitigated |

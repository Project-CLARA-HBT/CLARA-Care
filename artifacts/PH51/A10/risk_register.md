# Risk Register — PH51 A10 (Adversarial Replay & Starvation Scenarios)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH51-A10-01 | Cascade failure from continuous worker crashes re-executing poisonous jobs | Critical | Low | Exponential backoff with ceiling and transition to DLQ after 8 attempts. | Mitigated |
| RISK-PH51-A10-02 | Resource starvation of interactive queries by massive background batch jobs | High | Low | Dedicated queue priorities and worker pool partitioning between interactive and batch pipelines. | Mitigated |

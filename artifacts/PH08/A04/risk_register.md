# Risk Register — PH08 A04 (Cross-Partition Write Skew Guards)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH08-A04-01 | Write skew anomaly allowing contra-indicated prescription under snapshot isolation | Critical | Low | Guard requires explicit read dependency on safety policy epoch and clinical baseline. | Mitigated |
| RISK-PH08-A04-02 | Overly broad read dependencies causing excessive OCC aborts | Medium | Low | Fine-grained partition scoping restricts read locks to relevant patient domain keys. | Mitigated |

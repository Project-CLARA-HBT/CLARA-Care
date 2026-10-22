# Risk Register — PH49 A07 (GLHS Adversarial Lineage & Snapshot Parity)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH49-A07-01 | Proposal executing against stale or foreign snapshot | Critical | Low | Admission check Step 13 verifies exact match between proposal, binding, and snapshot ID. | Mitigated |
| RISK-PH49-A07-02 | Patient consent revocation ignored during deferred human review | Critical | Low | Reviewer admission re-evaluates active consent ledger under transactional row locks. | Mitigated |

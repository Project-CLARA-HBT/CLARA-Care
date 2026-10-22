# Risk Register — PH06 A03 (THSS Identity & Digest Check)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH06-A03-01 | Re-admitting a previously rejected clinical proposal | Critical | Low | Hard fail-closed check on `proposal.admission_decision == 'REJECTED'`. | Mitigated |
| RISK-PH06-A03-02 | Unsealed admitted proposal altered in-flight before commit | Critical | Low | Sealed timestamp applied under transactional row lock in Phase 3. | Mitigated |

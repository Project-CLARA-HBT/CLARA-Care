# Risk Register — PH05 A04 (Policy Epoch & Revocation Anchors)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH05-A04-01 | Stale vector cache serving chunks from revoked consent purposes | Critical | Low | PolicyEpochGate checks epoch timestamp and active purposes on every retrieval chunk. | Mitigated |
| RISK-PH05-A04-02 | Epoch drift between API gateway consent ledger and ML retrieval service | High | Low | Retrieval requests pass explicit active purpose set from authenticated session context. | Mitigated |

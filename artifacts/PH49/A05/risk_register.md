# Risk Register — PH49 A05 (GLHS Trace Explorer & Human Review Queue)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH49-A05-01 | Exposure of raw patient identifying information in trace explorer | Critical | Low | Table renders strictly pseudonymized proposal IDs, clinical action descriptors, and truncated digests. | Mitigated |
| RISK-PH49-A05-02 | Reviewer accidentally admitting dangerous drug proposal without viewing full digest | High | Low | UI presents attestation level badge and truncated D1/D3 hashes prominently. | Mitigated |

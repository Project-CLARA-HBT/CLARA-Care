# Risk Register — PH06 A04 (Lineage Anti-Downgrade Verifier)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH06-A04-01 | Review descendant silently discarding model inference provenance | Critical | Low | Anti-downgrade verifier enforces strict attestation level monotonicity and snapshot preservation. | Mitigated |
| RISK-PH06-A04-02 | Cycle in proposal review chain causing infinite recursion | High | Low | Lineage depth limit <= 4 and cycle detection hash set enforced during traversal. | Mitigated |

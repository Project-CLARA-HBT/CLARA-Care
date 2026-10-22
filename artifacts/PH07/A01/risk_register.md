# Risk Register — PH07 A01 (D1 Projection Digest & Schema)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH07-A01-01 | Non-deterministic JSON serialization causing digest mismatch across platforms | Critical | Low | RFC 8785 JSON Canonicalization Scheme (JCS) enforced for all digest calculations. | Mitigated |
| RISK-PH07-A01-02 | Inadvertent inclusion of internal metadata in D1 health projection | High | Low | D1 projection strictly scopes to model-visible clinical attributes, isolating infrastructure metadata. | Mitigated |

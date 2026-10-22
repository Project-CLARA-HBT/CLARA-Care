# Risk Register — PH49 A02 (GLHS Provenance Audit Read Model)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH49-A02-01 | Inadvertent inclusion of raw patient clinical data in control provenance audits | Critical | Low | Table schema strictly limited to public UUIDs, cryptographic digests, and categorical admission decisions. | Mitigated |
| RISK-PH49-A02-02 | Forensic query slowdown under high proposal volumes | Medium | Low | Indexes created across `tenant_id`, `proposal_public_id`, `attestation_level`, and `admission_decision`. | Mitigated |

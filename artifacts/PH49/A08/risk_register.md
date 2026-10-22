# Risk Register — PH49 A08 (Lineage Anti-Downgrade & Audit Reconstruction Threat Model)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH49-A08-01 | Reviewer erasing model ID to conceal AI participation | Critical | Low | Database schema constraint and GRWC Step 6 forbid stripping `inference_context_binding_id`. | Mitigated |
| RISK-PH49-A08-02 | Compromised administrator modifying past proposal rows | Critical | Low | Hash chain linking each proposal to predecessor's cryptographic digest breaks upon modification. | Mitigated |

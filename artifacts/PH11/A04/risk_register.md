# Risk Register — PH11 A04 (Consent & Provenance Mapping for ML & Research Pipelines)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH11-A04-01 | Unconsented ML inference or research retrieval on patient PHI | Critical | Low | Fail-closed `FhirConsentEnforcer` gates all pipeline runs, verifying purpose authorization and active validity period before execution. | Mitigated |
| RISK-PH11-A04-02 | Cross-border data leakage during external LLM inference | High | Low | Explicit Decree 13/2023/ND-CP statutory gate checks `cross_border_processing` consent purpose prior to any cloud model dispatch. | Mitigated |
| RISK-PH11-A04-03 | Provenance attestation downgrade across multi-tier clinical review chains | High | Low | Integrated `LineageAntiDowngradeVerifier` strictly forbids child proposals from reducing provenance attestation level (L3 -> L0). | Mitigated |
| RISK-PH11-A04-04 | PHI/PII leakage in exported FHIR Provenance entity descriptors or targets | High | Low | `FhirProvenanceMapper.redact_fhir_provenance_pii` sanitizes Vietnamese CCCD (12-digit), CMND (9-digit), phone numbers, emails, and pseudonyimizes patient references. | Mitigated |
| RISK-PH11-A04-05 | Inconsistent policy drift between FHIR R4 Consent and internal PolicyEpoch retrieval filter | Medium | Low | Bidirectional mapping ensures lossless translation between FHIR Consent provisions and CLARA `PolicyEpoch` gate. | Mitigated |
| RISK-PH11-A04-06 | Breaking changes to legacy pipeline invocations prior to validation | Medium | Low | Entire capability is protected behind feature flag `FHIR_CONSENT_PROVENANCE_ENABLED=False` until production signoff. | Mitigated |

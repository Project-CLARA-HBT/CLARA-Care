# Risk Register — PH07 A05 (Provider Identity & Model-Registry Binding)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH07-A05-01 | Client-side tampering requesting unvetted or untrusted LLM endpoints | Critical | Low | Client rejects unapproved models; API server discards request-level `llm_runtime` payloads. | Mitigated |
| RISK-PH07-A05-02 | Low-attestation model applied to critical clinical reasoning task | High | Low | Task family mapping enforces minimum required `minAttestationLevel`. | Mitigated |

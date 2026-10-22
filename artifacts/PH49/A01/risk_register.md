# Risk Register — PH49 A01 (GLHS Provenance Redacted Read API)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH49-A01-01 | Exposure of raw patient clinical notes through control plane audit endpoints | Critical | Low | DTO response emits strictly digests (D1/D2/D3), attestation levels, and public UUIDs. | Mitigated |
| RISK-PH49-A01-02 | Unauthenticated submission of reconciliation decisions | High | Low | Endpoint enforces control plane authentication and records reviewer identity. | Mitigated |

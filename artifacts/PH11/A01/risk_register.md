# Risk Register — PH11 A01 (FHIR CapabilityStatement API)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---|---|---|---|---|---|
| RISK-PH11-A01-01 | Premature exposure of FHIR endpoints to unauthenticated external traffic before clinical validation | High | Medium | Endpoint feature-gated behind `FHIR_CAPABILITY_STATEMENT_ENABLED` defaulting to `false`. Strict RBAC enforcement requiring explicit authentication. | Mitigated |
| RISK-PH11-A01-02 | Falsely advertising unverified external capabilities (e.g., claiming full unconstrained FHIR server or IPS compliance without legal approval) | High | Low | Conformance statement explicitly declares bounded capabilities (`fhir-r4-production-profile`, not IPS claim), lists only verified active resources and operations ($export, $import). | Mitigated |
| RISK-PH11-A01-03 | Patient health information (PHI) or personal identifiable information (PII) leakage in CapabilityStatement responses | Critical | Low | CapabilityStatement is strictly architectural and structural metadata; zero patient data is queried or projected. Response DTO validated via Pydantic. | Mitigated |
| RISK-PH11-A01-04 | Malformed client queries crashing gateway through unsupported format/media negotiation | Medium | Low | Strict content negotiation: unsupported `_format` returns 400 Bad Request; unsupported `Accept` headers (e.g. XML) return 406 Not Acceptable; invalid modes return 400. | Mitigated |

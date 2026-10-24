# Risk Register — PH11 A06 (Mobile Flutter: Web Integration Status Dashboard and FHIR Export View)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH11-A06-01 | Unconsented export or accidental disclosure of Protected Health Information (PHI) via mobile export view | Critical | Low | Hard consent gate invariant: export button is disabled until explicit user confirmation of medical disclaimer and declaration of purpose-of-use. | Mitigated |
| RISK-PH11-A06-02 | Misrepresentation of CLARA FHIR projection as an accredited, certified general FHIR R4 server | High | Low | Prominent non-accredited / summary-not-ips disclosure card displayed in the dashboard and export views; conformance string matches server-authoritative `fhir-r4-summary-not-ips`. | Mitigated |
| RISK-PH11-A06-03 | Accidental leakage of PHI in telemetry, analytics, or error banners during export failure | High | Low | Error banners display sanitized user-facing messages only; client analytics log event metadata (resource count, purpose code) without payload content or patient names. | Mitigated |
| RISK-PH11-A06-04 | Premature feature exposure before end-to-end backend verification and clinical review | Medium | Low | Entire feature is gated behind `fhir_interoperability_mobile_enabled`, defaulting to `false` (fail-closed); UI components remain dark unless explicitly enabled. | Mitigated |
| RISK-PH11-A06-05 | Client-side race or duplicate submission on manual connector sync | Low | Low | Debouncing state with active spinner (`_syncingConnectorIds`) prevents concurrent repeated sync requests on the same connector. | Mitigated |

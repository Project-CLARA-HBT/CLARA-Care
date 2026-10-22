# Risk Register — PH05 A01 (Versioned Consent Resource Endpoints)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH05-A01-01 | Client accepting outdated policy version bypassing updated medical risk disclosure | Critical | Low | Server-side validation strictly enforces matching `required_medical_disclaimer_version()`. | Mitigated |
| RISK-PH05-A01-02 | Incomplete purpose disclosure violating PDPD Vietnam statutory consent validity | High | Low | Published contract maps purpose codes explicitly (core_service, ai_transparency, cross_border_processing). | Mitigated |

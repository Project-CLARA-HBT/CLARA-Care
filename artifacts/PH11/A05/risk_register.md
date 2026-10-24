# Risk Register — PH11 A05 (Web UX: Encounter/Documents Export)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---|---|---|---|---|---|
| **RISK-PH11-A05-01** | Premature exposure of uncertified FHIR R4 clinical documents export prior to regulatory audit | High | Low | Feature flag `NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED` defaults to `false`. Both Web UX and Next.js routes fail closed with 404 `feature_disabled`. | **Mitigated** |
| **RISK-PH11-A05-02** | Export of encounter or clinical documents without explicit, versioned medical consent | High | Low | Pre-flight consent gate checks `medical_disclaimer` consent status; rejects unaccepted consent with 403 `consent_required`. | **Mitigated** |
| **RISK-PH11-A05-03** | Credential, session token, or internal DB identifier leakage in exported FHIR R4 JSON | Critical | Low | `validateRedaction` verifies exported JSON against token/secret patterns prior to download; profile contexts mapped to opaque patient identifiers. | **Mitigated** |
| **RISK-PH11-A05-04** | Filename injection or directory traversal attack via user-supplied document/visit titles | High | Low | `sanitizeExportFilename` strips traversal sequences (`..`), path separators (`/`, `\`), and special characters, guaranteeing safe filenames. | **Mitigated** |
| **RISK-PH11-A05-05** | Exporting unreviewed or unsigned drafts as confirmed clinical documents | Medium | Low | FHIR Composition status strictly distinguishes `preliminary` vs `final` based on clinician electronic signature timestamp. | **Mitigated** |

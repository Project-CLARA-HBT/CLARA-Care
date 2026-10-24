# PH11 Integration Demo — FHIR R4 Interoperability Production Profiles

## Scenario 1: FHIR CapabilityStatement Discovery
1. Query conformance metadata:
   ```bash
   curl -s -H "Accept: application/fhir+json" http://localhost:8000/api/v1/fhir/metadata | jq .
   ```
2. Verify FHIR R4 conformance (`4.0.1`), active resources (`Patient`, `Observation`, `Condition`, `MedicationStatement`, `AllergyIntolerance`, `Consent`, `Provenance`), and purpose-bound capabilities.

## Scenario 2: Consented Health Record Export
1. Patient initiates export with explicit statutory consent and purpose:
   ```bash
   curl -s -H "Authorization: Bearer $PATIENT_TOKEN" \
     "http://localhost:8000/api/v1/lifemap/v2/export/fhir-r4?purpose=self_download&include=patient,observations,medications" \
     -H "Accept: application/fhir+json" | jq .
   ```
2. System returns FHIR R4 Collection Bundle stamped with `X-CLARA-Conformance: fhir-r4-summary-not-ips`.

## Scenario 3: Untrusted External Import Quarantine
1. Post external observation bundle to Universal Capture staging:
   ```bash
   curl -s -X POST -H "Authorization: Bearer $PATIENT_TOKEN" \
     -H "Content-Type: application/fhir+json" \
     http://localhost:8000/api/v1/lifemap/v2/import/fhir-r4 \
     -d @bundle.json | jq .
   ```
2. Resources are staged exclusively as `untrusted_external_draft` candidates awaiting clinician review; zero direct EHR mutation occurs without verification.

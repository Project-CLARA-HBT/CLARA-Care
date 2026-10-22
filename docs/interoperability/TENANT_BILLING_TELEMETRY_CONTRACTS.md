# Interoperability Contracts: Multi-Tenant Billing Telemetry and Privacy Receipts (PH04_A09)

## 1. Scope & Standards Baseline

This document defines interoperability contracts and schema representations for exchanging multi-tenant usage telemetry, financial billing records, and cryptographic privacy audit receipts between CLARA Care subsystems and external platforms (OpenTelemetry collectors, Stripe/payment gateways, ERP systems, and FHIR R4 audit repositories).

The interface guarantees:
- **Zero-PII / Zero-PHI Export**: Payload schemas only permit computational metrics and accounting units.
- **Tenant Scope Attestation**: Every billing export is sealed with a cryptographic scope digest.
- **Standards Compliance**: OpenTelemetry Semantic Conventions v1.26.0, HL7 FHIR Release 4 (`AuditEvent`, `Provenance`), and RFC 7519 / RFC 7235.

---

## 2. OpenTelemetry Semantic Conventions for Tenant Telemetry

### 2.1 Meter Attributes & Spans

All internal telemetry meters exported to OTLP collectors MUST follow the namespaced conventions below:

```json
{
  "name": "clara.usage.meter",
  "kind": "COUNTER",
  "unit": "1",
  "attributes": {
    "tenant.id": "org_hospital_bach_mai",
    "clara.surface": "scribe",
    "meter.dimension": "asr_audio_seconds",
    "service.name": "clara-api",
    "service.version": "2026.10.0"
  }
}
```

### 2.2 Telemetry Export Restrictions
- **Allowed Attributes:** `tenant.id`, `clara.surface`, `meter.dimension`, `service.name`, `status_code`, `tier`.
- **Forbidden Attributes:** Any user email, patient ID, diagnosis, clinical query string, prompt, medication name, or internal database primary key.
- **Span Name Cloaking:** Span names must reflect high-level operational routes (`POST /v1/scribe/transcribe`), never parameters containing PHI.

---

## 3. Financial & Accounting Interoperability Contract

### 3.1 Stripe & ERP Usage Record Schema

For automated billing through Stripe Metered Billing or hospital ERP systems, usage is converted into the following canonical schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "TenantUsageRecordExport",
  "type": "object",
  "required": [
    "export_id",
    "tenant_id",
    "billing_period",
    "currency",
    "subtotal_cents",
    "tax_cents",
    "total_cents",
    "line_items",
    "cryptographic_seal"
  ],
  "properties": {
    "export_id": {
      "type": "string",
      "pattern": "^exp_[a-f0-9]{16}$"
    },
    "tenant_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64
    },
    "billing_period": {
      "type": "string",
      "pattern": "^[0-9]{4}-(0[1-9]|1[0-2])$"
    },
    "currency": {
      "type": "string",
      "enum": ["VND", "USD"]
    },
    "subtotal_cents": {
      "type": "integer",
      "minimum": 0
    },
    "tax_cents": {
      "type": "integer",
      "minimum": 0
    },
    "total_cents": {
      "type": "integer",
      "minimum": 0
    },
    "line_items": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["meter_kind", "surface", "units", "unit_price_cents", "line_total_cents"],
        "properties": {
          "meter_kind": {"type": "string"},
          "surface": {"type": "string"},
          "units": {"type": "number", "minimum": 0},
          "unit_price_cents": {"type": "integer", "minimum": 0},
          "line_total_cents": {"type": "integer", "minimum": 0}
        },
        "additionalProperties": false
      }
    },
    "cryptographic_seal": {
      "type": "string",
      "pattern": "^[a-f0-9]{64}$"
    }
  },
  "additionalProperties": false
}
```

---

## 4. FHIR R4 AuditEvent Interoperability Mapping

Cross-tenant access attempts and billing compliance events map to HL7 FHIR R4 `AuditEvent` resources for ingestion into hospital Security Operations Centers (SOC):

```json
{
  "resourceType": "AuditEvent",
  "id": "audit-tenant-boundary-probe-001",
  "type": {
    "system": "http://terminology.hl7.org/CodeSystem/audit-event-type",
    "code": "rest",
    "display": "Restful Operation"
  },
  "subtype": [
    {
      "system": "https://theclaracare.com/audit/types",
      "code": "TENANT_BOUNDARY_PROBE",
      "display": "Cross-Tenant Authorization Violation"
    }
  ],
  "action": "E",
  "recorded": "2026-10-21T23:30:00Z",
  "outcome": "8",
  "outcomeDesc": "Major failure - Insecure Direct Object Reference blocked fail-closed (404 Not Found)",
  "agent": [
    {
      "type": {
        "coding": [
          {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
            "code": "IRX",
            "display": "Identity Hashed Subject"
          }
        ]
      },
      "who": {
        "identifier": {
          "system": "urn:ietf:rfc:6920",
          "value": "ni:///sha-256;e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        }
      },
      "requestor": true
    }
  ],
  "source": {
    "site": "CLARA-API-Gateway",
    "observer": {
      "display": "TenantBoundaryEnforcer"
    }
  },
  "entity": [
    {
      "type": {
        "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
        "code": "4",
        "display": "Domain Resource"
      },
      "detail": [
        {
          "type": "attemptedTenantId",
          "valueString": "org_target_hospital"
        },
        {
          "type": "callerTenantId",
          "valueString": "org_attacker_clinic"
        }
      ]
    }
  ]
}
```

---

## 5. Cryptographic Privacy Audit Receipt Specification

To provide mathematical non-repudiation that an exported billing aggregate is untampered and isolated, CLARA Care produces a `PrivacyAuditReceipt`:

### 5.1 JSON Schema Representation

```json
{
  "audit_id": "aud_7a9f82c401be33d5",
  "scanner_version": "1.0.0-ph04",
  "tenant_id": "org_hospital_bach_mai",
  "scope_digest": "4c8f9b8823d14234032d8478fe1bc89a69a8e2cb3201402280d944c6883e4981",
  "result": "pass",
  "finding_count": 0,
  "artifact_digest": "f9b40091c01e6a2dc983058a5c37021eb9da718104860b7d3f18e95c18a280c4",
  "executed_at": "2026-10-21T23:35:00Z",
  "verified_invariants": [
    "INV-TEN-01: Partitioned Meter Storage",
    "INV-TEN-02: Zero Cross-Tenant Query Bleed",
    "INV-TEN-03: Zero-PII/PHI Billing Line-Items",
    "INV-TEN-04: Non-Enumeration Resource Scoping (404)",
    "INV-TEN-05: Side-Channel Isolated Rate Limiting",
    "INV-TEN-06: Cryptographic Scope Digest Attestation"
  ]
}
```

### 5.2 Verification Procedure
Third-party auditors or hospital compliance officers verify the receipt by:
1. Re-hashing the boundary parameters:
   $$\text{scope\_digest} = \text{SHA-256}(\text{tenant\_id} \parallel \text{start} \parallel \text{end} \parallel \text{event\_count} \parallel \text{total\_cents})$$
2. Confirming that $\text{scope\_digest}$ matches the receipt field.
3. Checking that $\text{finding\_count} = 0$ and $\text{result} = \text{"pass"}$.

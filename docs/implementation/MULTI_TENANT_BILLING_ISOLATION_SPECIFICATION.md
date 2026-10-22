# Multi-Tenant Billing and Telemetry Isolation Specification (PH04_A09)

## 1. Overview & Purpose

This specification governs the implementation of tenant isolation across usage metering, billing aggregation, and telemetry pipelines in CLARA Care. It defines the technical standards, database indexing patterns, API request/response schemas, and operational guardrails required to guarantee zero cross-tenant metadata disclosure and zero clinical PHI leakage in financial records.

Engineering subagents across Phase PH04 (A01, A02, A03, A08) must adhere strictly to these isolation contracts when building organization and workspace features.

---

## 2. Multi-Tenant Architecture & Data Model

### 2.1 Partitioned Database Schema

In persistent storage (PostgreSQL), all billing and meter tables MUST partition or index records by `tenant_id`:

```sql
-- PostgreSQL DDL Pattern for Multi-Tenant Usage Metering
CREATE TABLE tenant_usage_events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(36) NOT NULL UNIQUE,
    tenant_id VARCHAR(64) NOT NULL,
    surface VARCHAR(32) NOT NULL,
    meter_kind VARCHAR(64) NOT NULL,
    quantity NUMERIC(14, 4) NOT NULL CHECK (quantity >= 0),
    idempotency_key VARCHAR(128) NOT NULL,
    tier VARCHAR(32) NOT NULL DEFAULT 'standard',
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    
    -- Invariant: Triple-key idempotency deduplication per tenant
    CONSTRAINT uq_tenant_meter_idempotency UNIQUE (tenant_id, meter_kind, idempotency_key)
);

-- Indexing optimized for scoped range aggregation
CREATE INDEX idx_tenant_usage_aggregate 
ON tenant_usage_events (tenant_id, created_at, surface, meter_kind);
```

### 2.2 Invariant Guarantees
1. **Additive Schema Only:** Table additions or column extensions must never drop existing data.
2. **Immutable Append-Only:** Meter events are write-once; historical records cannot be updated or purged without formal compliance authorization.
3. **Strict Scoping Predicate:** Every analytical or billing query MUST include:
   ```sql
   WHERE tenant_id = :authenticated_tenant_id
     AND created_at >= :start_time
     AND created_at <= :end_time
   ```

---

## 3. Allowlisted Billing Dimensions & Ingestion Contracts

### 3.1 Allowlisted Meter Dimensions

| Meter Dimension Key | Subsystem Surface | Unit Description | Unit Rate (VND) |
|---|---|---|---|
| `llm_prompt_tokens` | Chat / Research | DeepSeek / LLM input prompt tokens | 2 VND |
| `llm_completion_tokens` | Chat / Research | DeepSeek / LLM generated tokens | 6 VND |
| `asr_audio_seconds` | Scribe Audio | Processed speech-to-text audio seconds | 10 VND |
| `ocr_document_pages` | CareGuard / Vision | Extracted prescription & lab pages | 150 VND |
| `careguard_checks` | CareGuard Safety | Drug-drug interaction checks evaluated | 50 VND |
| `council_cases` | Council Multi-Agent | Deliberation cases analyzed by multi-agent board | 500 VND |
| `storage_gb_hours` | Storage / Workspace | Encrypted PHR and document storage volume | 5 VND |
| `api_requests` | API Gateway | Total authenticated gateway API calls | 1 VND |

### 3.2 Forbidden PHI / PII Key Denylist

Any usage event containing any of the following keys in `metadata_json` or metadata tags MUST be rejected at the API boundary with HTTP `422 Unprocessable Entity`:

```python
FORBIDDEN_PHI_KEYS = {
    "patient", "patient_id", "patient_name", "name", "full_name",
    "email", "phone", "phone_number", "address", "dob", "ssn", "citizen_id", "cccd",
    "query", "query_text", "prompt", "transcript", "transcription",
    "diagnosis", "diagnoses", "symptom", "symptoms", "condition", "conditions",
    "medication", "medications", "drug", "drugs", "dosage", "allergy", "allergies",
    "lab_result", "vital_signs", "notes", "clinical_notes"
}
```

---

## 4. API Endpoints & Access Control Matrix

### 4.1 Endpoints Specification

| Route Path | HTTP Method | Minimum Role | Description | Error Responses |
|---|---|---|---|---|
| `/api/v1/billing/usage` | `GET` | `org_admin` | Retrieve aggregated usage metrics and costs for the authenticated tenant's billing cycle. | `401 Unauthorized`<br>`403 Forbidden`<br>`404 Not Found` (non-enumeration) |
| `/api/v1/billing/invoices` | `GET` | `org_admin` | List historical finalized invoices for the caller's organization. | `401 Unauthorized`<br>`403 Forbidden` |
| `/api/v1/billing/invoices/{invoice_id}` | `GET` | `org_admin` | Fetch specific sealed invoice with itemized line items. | `401 Unauthorized`<br>`403 Forbidden`<br>`404 Not Found` |
| `/api/v1/billing/export` | `POST` | `org_admin` | Generate signed export CSV/JSON accompanied by a cryptographic `PrivacyAuditReceipt`. | `401 Unauthorized`<br>`403 Forbidden` |
| `/api/v1/admin/billing/global` | `GET` | `admin` | Platform-level operational aggregate; scrubbed of tenant proprietary identifiers. | `401 Unauthorized`<br>`403 Forbidden` |

### 4.2 Non-Enumeration Fail-Closed Pattern

When an authenticated user belonging to `tenant_A` attempts to access a billing resource (e.g., invoice `inv_555`) owned by `tenant_B`:
- **Strictly Forbidden:** Returning `403 Forbidden` with body `{"detail": "Invoice belongs to tenant_B"}` (violates non-enumeration; confirms resource existence and ownership).
- **Mandatory Pattern:** Returning `404 Not Found` with body `{"detail": "Invoice not found"}`.
- **Audit Logging:** Emitting a `ComplianceBoundaryEvent` with `event_type="TENANT_BOUNDARY_PROBE"`, logging the hashed user identity (`subject_digest`) and reporting the attempt to security operations.

---

## 5. Side-Channel & Timing Attack Defense

1. **Per-Tenant Rate Limiting:**
   - Every tenant is assigned an isolated token bucket (`TenantRateLimiter`).
   - Rate limit counters are stored under keys namespaced by `rl:tenant:{tenant_id}:{window}`.
   - Exhaustion of Tenant A's bucket returns `429 Too Many Requests` with headers:
     ```http
     X-RateLimit-Limit: 100
     X-RateLimit-Remaining: 0
     X-RateLimit-Reset: 1729544400
     ```
   - Headers MUST NEVER reveal global cluster capacity or peer tenant rates.

2. **Constant-Shape Responses:**
   - Empty tenants (e.g. newly onboarded organizations with zero queries) receive the exact same response schema with `has_data=False`, zero counts, and empty lists.
   - Response latency for zero-data vs high-volume tenants must be buffered or bounded to prevent timing analysis of peer tenant data volume.

---

## 6. Verification & Quality Gates

Developers and CI systems must execute:
```bash
# Execute full tenant billing boundary privacy audit suite
PYTHONPATH=services/api/src:. python3 -m pytest -v research/billing_tenant_privacy_audit/test_tenant_billing_boundary_audit.py

# Standalone hermetic audit runner
python3 research/billing_tenant_privacy_audit/run_tenant_privacy_audit.py
```
Both commands must terminate with exit code `0`.

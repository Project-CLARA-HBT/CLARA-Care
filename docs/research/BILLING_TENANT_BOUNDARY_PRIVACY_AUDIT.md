# Research Evidence & Boundary Privacy Audit: Multi-Tenant Billing and Telemetry Isolation (PH04_A09)

## 1. Executive Summary & Audit Mandate

In multi-tenant clinical AI architectures like CLARA Care, healthcare institutions (hospitals, ambulatory care clinics, academic medical centers) share computational infrastructure while remaining legally, operationally, and ethically distinct entities. 

When usage metrics (LLM token consumption, ASR audio transcription minutes, OCR prescription scanning pages, CareGuard drug-drug interaction checks, Council multi-agent deliberations) are metered for billing, financial reporting, and infrastructure capacity planning, **cross-tenant metadata disclosure** and **billing aggregation contamination** represent critical security and compliance hazards.

This research evidence and privacy audit documents:
1. **Mathematical and Architectural Formalization of Tenant Boundary Privacy**: Enforcing complete partition isolation where the probability of metadata or usage leakage across tenant boundaries is strictly zero ($P(\mathcal{L}_{A \to B}) = 0$).
2. **Threat Vectors in Multi-Tenant Billing & Telemetry**: Identification of 6 primary attack vectors (direct cross-tenant query bleed, Insecure Direct Object References in invoices, side-channel timing and rate-limiting inference, clinical PHI infiltration into financial line-items, trace context disclosure, and aggregator state corruption).
3. **Audit Methodology & Verification Suite**: Design and hermetic execution of 44 negative and boundary test vectors across 7 vulnerability domains in `research/billing_tenant_privacy_audit/`.
4. **Regulatory Conformance**: Aligning multi-tenant metering with HIPAA §164.312(a)(1) (Access Control), GDPR Article 32 (Security of Processing), and Vietnam Decree 13/2023/ND-CP (Personal Data Protection).

---

## 2. Threat Modeling: Multi-Tenant Billing & Telemetry

```
                     +---------------------------------------+
                     |         API Gateway / Router          |
                     +---------------------------------------+
                                         |
                                         | [Authentication & Tenant Context: X-Tenant-Id]
                                         v
                     +---------------------------------------+
                     |    Tenant Boundary Privacy Enforcer   |
                     |  - Non-Enumeration Scoping (404)      |
                     |  - Zero-PII/PHI Allowlist Sanitizer   |
                     |  - Isolated Token Bucket Rate Limiter |
                     +---------------------------------------+
                                    /        \
              Tenant A (Hospital Bạch Mai)    Tenant B (Hospital Chợ Rẫy)
                                   v          v
                     +---------------------------------------+
                     | Partitioned Meter Storage (Triple-Key)|
                     |  (tenant_id, meter_kind, idemp_key)  |
                     +---------------------------------------+
                                   |          |
                                   v          v
                      [Tenant A Aggregate]   [Tenant B Aggregate]
                      - Scope Digest A       - Scope Digest B
                      - Cryptographic Seal   - Cryptographic Seal
```

### 2.1 Threat Vector Matrix

| Threat Vector ID | Vulnerability Class | Mechanism / Attack Scenario | Enforced Invariant & Mitigation | Fail-Closed HTTP Code |
|---|---|---|---|---|
| **TV-BILL-01** | Cross-Tenant Aggregation Contamination | Aggregator executes un-scoped `SELECT sum(units)` or missing `WHERE tenant_id = :tid` filter, mixing peer tenant usage. | Strict tenant partitioning in storage and mandatory `tenant_id` predicate on all analytical reads. | `404 Not Found` / Rejected |
| **TV-BILL-02** | Invoice BOLA / IDOR (API1:2023) | Tenant A guesses or enumerates Tenant B's invoice identifier (`inv_12345`) to inspect peer usage and costs. | Non-enumeration object lookup: foreign tenant resource returns `404 Not Found` (never `403` with owner leak). | `404 Not Found` |
| **TV-BILL-03** | Side-Channel Rate-Limit Probing | Attacker probes shared rate limiter or worker pool to infer peer tenant query spikes and operational volume. | Isolated per-tenant token bucket rate limiters (`TenantRateLimiter`); headers emit only caller capacity. | `429 Too Many Requests` |
| **TV-BILL-04** | PHI / Clinical Leakage into Financial Line-Items | Subsystem passes clinical query text, drug names, patient names, or transcripts into billing metadata. | Recursive zero-PII/PHI validator rejecting 30+ medical keys and scanning string patterns (e.g. emails). | Schema Validation Error |
| **TV-BILL-05** | Trace Context Metadata Leakage | Platform error response or telemetry headers (`traceparent`, `X-Tenant-Id`) echo back internal peer identifiers. | Metadata scrubber removes all foreign tenant identifiers and scrubs stack traces. | `400 Bad Request` |
| **TV-BILL-06** | Billing Double-Counting Race | Concurrent retries emit duplicate meter records during network degradation. | Triple-key idempotency deduplication on `(tenant_id, meter_kind, idempotency_key)`. | Deduplicated / Cached ID |

---

## 3. Formal Invariants for Tenant Boundary Privacy

### 3.1 Invariant Definitions

1. **INV-TEN-01 (Partitioned Meter Ingestion):**
   $$\forall e \in \mathcal{E}, \quad \text{Storage}(e) \implies e.\text{tenant\_id} \in \mathcal{T}_{\text{valid}} \land e.\text{quantity} \ge 0$$
   Every recorded event must carry a non-empty, validated tenant identifier and non-negative finite quantity.

2. **INV-TEN-02 (Zero Cross-Tenant Query Bleed):**
   $$\forall t_i, t_j \in \mathcal{T}, \quad i \ne j \implies \mathcal{Q}(t_i) \cap \mathcal{E}(t_j) = \emptyset$$
   A query executed in the context of tenant $t_i$ can never select, aggregate, or touch events belonging to tenant $t_j$.

3. **INV-TEN-03 (Zero-PII / Zero-PHI Financial Metering):**
   $$\forall e \in \mathcal{E}, \quad \text{keys}(e.\text{metadata}) \cap \mathcal{K}_{\text{PHI}} = \emptyset \land \text{values}(e.\text{metadata}) \cap \mathcal{V}_{\text{PII}} = \emptyset$$
   Meter records contain strictly computational quantities (tokens, seconds, pages, requests, cents, tier) and zero clinical or patient attributes.

4. **INV-TEN-04 (Non-Enumeration Fail-Closed Object Resolution):**
   $$\forall r \in \mathcal{R}(t_j), \quad \text{Lookup}(t_i, r.\text{id}) = \text{404 Not Found} \quad (i \ne j)$$
   When tenant $t_i$ requests a resource belonging to peer tenant $t_j$, the system returns `404 Not Found` without disclosing the resource's existence or owner identity.

5. **INV-TEN-05 (Side-Channel Independence):**
   $$\frac{\partial \text{QuotaRemaining}(t_i)}{\partial \text{Usage}(t_j)} = 0 \quad (i \ne j)$$
   Exhaustion of rate limits, quotas, or concurrency tokens by tenant $t_j$ produces zero effect on tenant $t_i$'s capacity.

6. **INV-TEN-06 (Cryptographic Scope Digest Attestation):**
   $$\text{Digest}(t, \text{start}, \text{end}, N, C) = \text{SHA-256}(t \parallel \text{start} \parallel \text{end} \parallel N \parallel C)$$
   Every aggregated usage record and invoice emits a verifiable SHA-256 digest sealing boundary parameters against tampering.

---

## 4. Verification Evidence & Test Results

The audit test suite implemented in `research/billing_tenant_privacy_audit/test_tenant_billing_boundary_audit.py` was executed hermetically via `research/billing_tenant_privacy_audit/run_tenant_privacy_audit.py`:

```text
=== CLARA Care Multi-Tenant Billing Boundary Privacy Audit (PH04_A09) ===
Target suite: .../research/billing_tenant_privacy_audit/test_tenant_billing_boundary_audit.py
Executing 44 boundary isolation, non-enumeration, and zero-PII vectors...
collected 44 items

research/billing_tenant_privacy_audit/test_tenant_billing_boundary_audit.py::TestTenantMeterIsolation (7 vectors) PASSED
research/billing_tenant_privacy_audit/test_tenant_billing_boundary_audit.py::TestBillingAggregatorBoundaries (7 vectors) PASSED
research/billing_tenant_privacy_audit/test_tenant_billing_boundary_audit.py::TestCrossTenantMetadataDisclosure (7 vectors) PASSED
research/billing_tenant_privacy_audit/test_tenant_billing_boundary_audit.py::TestBillingZeroPIIInvariant (7 vectors) PASSED
research/billing_tenant_privacy_audit/test_tenant_billing_boundary_audit.py::TestSideChannelIsolation (6 vectors) PASSED
research/billing_tenant_privacy_audit/test_tenant_billing_boundary_audit.py::TestPrivacyAuditReceipts (4 vectors) PASSED
research/billing_tenant_privacy_audit/test_tenant_billing_boundary_audit.py::TestHTTPBillingTenantAPIGateway (6 vectors) PASSED

======================== 44 passed, 1 warning in 0.82s =========================
```

### 4.1 Key Audit Findings & Remediations

1. **Opaque Resource Identifiers for Invoices & Receipts:**
   - *Discovery:* Standardizing invoice IDs using structured slugs like `inv_{tenant_id}_{period}` inadvertently leaked the tenant identifier in 404 responses (`"Invoice 'inv_tenant_victim...' not found"`).
   - *Remediation:* Enforced opaque cryptographically derived identifiers (`inv_{sha256(seed)[:16]}`) so that the ID itself conveys zero tenant identity or organization metadata.
2. **Nan / Infinite Meter Value Defense:**
   - *Discovery:* Floating-point quantities must be clamped and rejected if non-finite (`NaN` or `Inf`), preventing arithmetic poison in financial billing tables.
   - *Remediation:* Integrated strict Pydantic `ge=0.0` and `math.isnan/math.isinf` validator in `TenantUsageEvent`.
3. **Triple-Key Idempotency Partitioning:**
   - *Discovery:* Reusing idempotency keys across different tenants should not cause collision or denial of service for peer tenants.
   - *Remediation:* Keyed idempotency storage explicitly by `(tenant_id, meter_kind, idempotency_key)`, matching the formal GLHS specification in `GlhsAppliedTransition`.

---

## 5. Regulatory Alignment

| Standard / Regulation | Mandatory Control Requirement | Implementation in CLARA Care Billing & Telemetry |
|---|---|---|
| **HIPAA Security Rule §164.312(a)(1)** | Implement technical policies and procedures for electronic information systems that maintain electronic protected health information to allow access only to those persons or software programs that have been granted access rights. | Partitioned tenant metering, RBAC gate (`org_admin` vs `admin`), non-enumeration 404 for cross-tenant object access. |
| **GDPR Article 32(1)(a)** | Pseudonymisation and encryption of personal data; ensuring confidentiality, integrity, availability, and resilience of processing systems. | Zero-PII/PHI billing schema invariant; SHA-256 hashed subject references in compliance events; cryptographic scope digests. |
| **Vietnam Decree 13/2023/ND-CP Article 13 & 17** | Protection of basic and sensitive personal data (health records, medical data); data minimization and purpose specification. | Strict allowlisting of financial dimensions; automated rejection of medical records, symptoms, and drug lists in billing pipelines. |

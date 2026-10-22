# Risk Register: PH04_A09 Multi-Tenant Billing Boundary Privacy Audit

## 1. Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant Enforced | Status |
|---|---|---|---|---|---|---|
| **RR-PH04-A09-01** | Cross-Tenant Aggregation Contamination | Aggregator runs queries without `tenant_id` filter, combining peer tenant meter tallies into a single bill. | Critical | Low | Partitioned storage and mandatory `tenant_id` WHERE predicates. Enforced by `test_vec_tbba_agg_01` & `test_vec_tbba_agg_07`. | Controlled |
| **RR-PH04-A09-02** | Billing Object-Level IDOR (API1:2023) | Attacker enumerates invoice IDs to view peer tenant invoices and financial volumes. | Critical | Medium | Opaque invoice IDs (`inv_{hash[:16]}`) and non-enumeration fail-closed pattern: foreign invoice returns `404 Not Found`. Enforced by `test_vec_tbba_dis_01` & `test_vec_tbba_dis_02`. | Controlled |
| **RR-PH04-A09-03** | Clinical PHI Leakage into Invoices | Subsystems submit patient queries, drug names, diagnoses, or transcripts into billing metadata. | Critical | Low | Zero-PII/PHI recursive scrubber rejecting 30+ medical keys and scanning string values for emails and patient data. Enforced by `test_vec_tbba_pii_01` through `test_vec_tbba_pii_05`. | Controlled |
| **RR-PH04-A09-04** | Billing Double-Counting on Network Retry | Intermittent network drops cause duplicate meter submission and duplicate billing. | High | Medium | Triple-key idempotency deduplication on `(tenant_id, meter_kind, idempotency_key)` returns cached ID without increment. Enforced by `test_vec_tbba_iso_02`. | Controlled |
| **RR-PH04-A09-05** | Side-Channel Rate-Limit Inference | Malicious tenant floods shared rate limiter to detect when peer tenants are active or exhaust global quota. | High | Low | Isolated per-tenant token bucket rate limiting (`TenantRateLimiter`); headers emit only caller capacity. Enforced by `test_vec_tbba_sdc_01` through `test_vec_tbba_sdc_04`. | Controlled |
| **RR-PH04-A09-06** | Trace Context Metadata Leakage | HTTP responses or error envelopes leak foreign `tenant_id` or organization names to client. | High | Low | Scrubber validates and purges foreign tenant markers from outgoing payloads. Enforced by `test_vec_tbba_dis_03` & `test_vec_tbba_dis_04`. | Controlled |
| **RR-PH04-A09-07** | Non-Finite Meter Quantities (NaN/Inf) | Poisoned numeric inputs corrupt float calculations in billing tables. | Medium | Low | Pydantic validators enforcing `ge=0.0` and finite non-negative numbers. Enforced by `test_vec_tbba_iso_04`. | Controlled |
| **RR-PH04-A09-08** | Flaky Test Suite Execution | Billing privacy audit tests fail due to external database dependencies or race conditions. | Medium | Low | Audit suite runs 100% hermetically in-memory with thread-safe locks, executing 44 vectors in < 1 second. Enforced by `test_vec_tbba_iso_05`. | Controlled |

---

## 2. Invariant & Safety Guardrails Summary

1. **Partitioned Storage:** Meter events are strictly isolated by `tenant_id`.
2. **Triple-Key Idempotency:** Deduplication is namespaced per `(tenant_id, meter_kind, idempotency_key)`.
3. **Zero-PII/PHI Invariant:** Billing records contain only allowlisted computational units (tokens, seconds, pages, requests, cents, tier).
4. **Non-Enumeration (404):** Unauthorized cross-tenant lookups return `404 Not Found` without disclosing resource existence or owner metadata.
5. **Cryptographic Attestation:** Every aggregation produces a verifiable `scope_digest` and `PrivacyAuditReceipt`.

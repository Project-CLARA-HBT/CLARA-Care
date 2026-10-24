# PH12-A09 Risk Register: LifeMap Longitudinal Data Minimization & Visibility

- **Phase ID**: PH12 (LifeMap longitudinal intelligence)
- **Agent ID**: A09
- **Role**: Docs + research evidence
- **Worktree**: `/dev/shm/clara_worktrees/PH12_A09`
- **Branch**: `phase/ph12-a09`
- **Base Commit SHA**: `36e5b95fac7e65712f0779de253d8ed18dc693d7`
- **Frozen HEAD SHA**: `36e5b95fac7e65712f0779de253d8ed18dc693d7`
- **Regulatory Frameworks**: Vietnam Law 15/2023/QH15, Decree 13/2023/ND-CP (PDPD), AI Law 134/2025/QH15
- **Status**: **PASSED & VERIFIED**

---

## 1. Executive Summary & Audit Profile

Subagent **A09** has performed the longitudinal health data minimization, history visibility boundaries, and research architecture audit for Phase PH12.

This risk register evaluates residual risks across:
1. `docs/research/LIFEMAP_LONGITUDINAL_DATA_MINIMIZATION_AND_HISTORY_VISIBILITY_AUDIT.md` (Statutory legal boundaries under Law 15/2023/QH15 and Decree 13/2023/ND-CP, three-tier assertion model, Zero-CoT redaction).
2. `docs/implementation/LIFEMAP_DATA_MINIMIZATION_AND_VISIBILITY_BOUNDARIES_SPEC.md` (Engineering specification for `ProfileScope`, `ConflictPreservationEngine`, `TemporalRetrievalIndex`, and `route_ask_query`).
3. `docs/interoperability/LIFEMAP_FHIR_PROVENANCE_AND_MINIMIZATION_BOUNDARIES.md` (FHIR R4 resource mappings, draft capture isolation, and AuditEvent minimization).
4. `artifacts/PH12/A09/test_lifemap_data_minimization_and_visibility.py` (Automated pytest suite validating 29 test vectors across authorization, routing, transitions, conflicts, and indexing).

---

## 2. Longitudinal Intelligence Threat & Risk Register

| Risk ID | Threat Description | Severity | Likelihood | Impact | Current Controls & Defenses | Residual Gap / Next Phase Recommendation |
|---|---|---|---|---|---|---|
| **RSK-LM-01** | **Cross-Profile IDOR & Patient Enumeration Oracle** | **CRITICAL** | High | Critical | • Server-resolved `ProfileScope` validates account ownership or active `FamilyAccessGrant`.<br>• Uniform HTTP 404 (`scope_forbidden`) emitted for missing and unpermitted profiles alike, preventing enumeration. | Enforce database-level Row Level Security (RLS) policies on `lifemap_events` in PostgreSQL. |
| **RSK-LM-02** | **Prescribing Privilege Escalation via Patient Assertion** | **CRITICAL** | Medium | Critical | • Law 15/2023/QH15 Art. 32/53 guardrails enforced.<br>• Patient assertions emit strictly as `MedicationStatement` in truth state `user_reported`.<br>• `MedicationRequest` is strictly reserved for credentialed physicians. | Add automated static analysis linting to ensure no client route can set `MedicationRequest` without doctor digital certificate. |
| **RSK-LM-03** | **Administrative Privilege Creep into Clinical PHI** | **HIGH** | Medium | High | • `platform_root_cannot_read_phi` invariant enforced in `profile_scope.py`.<br>• Admin roles trying to access patient health records are blocked with 404.<br>• Denied attempts log `FamilyAccessLog` with reason `break_glass_required`. | Implement multi-signature quorum requirement for clinical emergency break-glass procedures. |
| **RSK-LM-04** | **Stale Retrieval of Revoked Consent Data Sources** | **HIGH** | Medium | High | • Under PDPD Art. 17, `retrieve_revision_evidence` joins on `LifeMapSourceRevocation` anti-join.<br>• `invalidate_projection_graph` recursively cascades invalidation through derived timelines. | Expand integration testing in PH13 to benchmark cache eviction latency across multi-node clusters. |
| **RSK-LM-05** | **Destructive Overwriting of Conflicting Clinical Diagnoses** | **HIGH** | Medium | High | • `ConflictPreservationEngine` retains parallel assertions with status `CONFIRMED`, `DISPUTED`, `UNCERTAIN`.<br>• Disputes link non-destructively as `disp-<assertion_id>`. | Provide side-by-side reconciliation UX for attending clinicians in hospital consultation modules. |
| **RSK-LM-06** | **Zero-CoT & Internal Reasoning Leakage to Consumer View** | **HIGH** | Medium | High | • Model chain-of-thought, prompt templates, and raw embeddings are restricted to internal microservice tier.<br>• Consumer wording assembled from fixed strings or exact source revision text (`_consumer_copy`). | Maintain regex scanning in CI to ensure no JSON responses expose internal reasoning traces. |
| **RSK-LM-07** | **Acute Emergency Delay Due to Longitudinal Inquiries** | **CRITICAL** | Medium | Critical | • `route_ask_query` parses Vietnamese & English acute symptoms (`khong tho duoc`, `severe chest pain`).<br>• Sets `emergency=True` immediately, bypassing retrieval and short-circuiting questioning. | Regularly update emergency keyword lexicography with clinical input from Vietnamese emergency department physicians. |
| **RSK-LM-08** | **Reranker Escape & Document Injection in Temporal Index** | **HIGH** | Low | High | • `TemporalRetrievalIndex` verifies `set(ordered_ids) <= candidate_ids`.<br>• Any foreign document ID injected by an external reranker raises `RetrievalBoundaryError`. | Maintain strict sandboxing of external neural rerankers with isolated process boundaries. |

---

## 3. Defense-in-Depth Verification Matrix

1. **Gateway Tier**: Bearer token authentication, CSRF validation, tenant header verification, and uniform 404 error responses.
2. **Authorization & Scope Tier**: `ProfileScope` verifies purpose, allowed actions, data classes, and tenant confinement.
3. **Clinical Safety Tier**: Fail-closed emergency fast-path and anti-prescribing legal hard-guards under Law 15/2023/QH15.
4. **Data Lifecycle Tier**: Deterministic `TRUTH_TRANSITIONS` state machine prevents unauthorized elevation of unverified draft extractions.
5. **Conflict Preservation Tier**: `ConflictPreservationEngine` retains parallel competing assertions and patient disputes without destructive alteration.
6. **Telemetry Tier**: No-PII telemetry and transactional outbox event envelope isolation prevent downstream data leakage.

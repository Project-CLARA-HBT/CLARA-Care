# LifeMap Longitudinal Health Data Minimization & Patient History Visibility Audit

- **Phase ID**: PH12 (LifeMap longitudinal intelligence)
- **Agent ID**: A09
- **Role**: Docs + research evidence
- **Regulatory Frameworks**:
  - Law on Medical Examination and Treatment No. 15/2023/QH15 (*Luật Khám bệnh, chữa bệnh 2023*)
  - Decree 13/2023/ND-CP on Personal Data Protection (*Nghị định 13/2023/NĐ-CP về Bảo vệ Dữ liệu Cá nhân - PDPD*)
  - Draft Law on Artificial Intelligence No. 134/2025/QH15 (*Luật Trí tuệ Nhân tạo*)
  - Circular 46/2018/TT-BYT on Electronic Medical Records (*Thông tư 46/2018/TT-BYT*)
- **Baseline Commit**: `36e5b95fac7e65712f0779de253d8ed18dc693d7`
- **Status**: **VERIFIED & AUDITED**

---

## 1. Executive Summary & Statutory Context

The LifeMap subsystem within CLARA Care provides longitudinal health timeline synthesis, event projection, trend intelligence, and multi-source medical history aggregation. Because longitudinal health data encapsulates cumulative life history, diagnostic narratives, sensitive lab observations, and clinician notes, managing its visibility and storage requires strict data minimization and regulatory boundary enforcement.

This audit evaluates the architectural and programmatic controls governing longitudinal health data minimization and patient history visibility under the Vietnamese legal framework, specifically:

1. **Law on Medical Examination and Treatment No. 15/2023/QH15 (effective 01/01/2024)**:
   - **Article 8 (Medical Confidentiality)**: Strictly protects patient medical confidentiality and prohibits unlawful disclosure of medical secrets or health status without patient consent or statutory court mandate.
   - **Article 15 (Patient Rights to Information Access)**: Grants patients the affirmative legal right to access, inspect, explain, and copy their medical examination and treatment records, while establishing the sole accountability of licensed healthcare practitioners for diagnostic formulations.
   - **Article 19 (Patient Privacy & Personal Liberty)**: Protects personal privacy during examination, medical consultations, and longitudinal data storage.
   - **Articles 32 & 53 (Practitioner Licensing & Clinical Authority)**: Mandates that only licensed healthcare practitioners who have been issued valid practicing certificates (*chứng chỉ hành nghề y tế*) may diagnose disease, prescribe pharmacotherapy, or issue binding clinical orders. Software algorithms are legally classified strictly as Clinical Decision Support Systems (CDSS) and cannot autonomously diagnose or prescribe.

2. **Decree 13/2023/ND-CP on Personal Data Protection (PDPD)**:
   - **Article 2(4) & Article 28 (Sensitive Personal Data)**: Expressly classifies health data and medical history as sensitive personal data subject to mandatory impact assessments, heightened security controls, and strict purpose-bound processing.
   - **Articles 3 & 9 (Principles of Data Minimization & Purpose Limitation)**: Requires that processing be limited strictly to the minimum necessary personal data required to fulfill specified, explicit, and legitimate health management purposes.
   - **Articles 12 & 17 (Consent Primacy & Revocation)**: Requires valid, freely given, specific, and informed consent. When a patient revokes consent for a data source or sharing relationship, downstream processing and AI retrieval must immediately cease and exclude that source.
   - **Articles 14 & 16 (DSAR and Right to Erasure)**: Enforces the patient's right to obtain a structured export of their personal health record (PHR) and request complete erasure within 72 hours, reconciled against statutory medical audit retention requirements.

---

## 2. Longitudinal Visibility Boundaries & Clinical Roles

### 2.1 The Three-Tier Assertion Boundary Model

Longitudinal data points in LifeMap cannot be treated as a flat, uniform stream of assertions. The system enforces a three-tier assertion boundary:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       THREE-TIER ASSERTION BOUNDARY                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  TIER 1: LICENSED PRACTITIONER CLINICAL ORDERS & DIAGNOSES                  │
│  • Emitted by credentialed practitioners under Law 15/2023/QH15 Art. 32/53 │
│  • Immutable provenance, digital doctor signature, formal ICD-10/SNOMED     │
│  • Generates official MedicationRequest and formal DiagnosticReport         │
├─────────────────────────────────────────────────────────────────────────────┤
│  TIER 2: PATIENT SELF-REPORTED & CAREGIVER ASSERTIONS                       │
│  • Emitted by patient or authorized family caregiver under Art. 15          │
│  • Tracked in LifeMap truth states as "user_reported"                       │
│  • Maps strictly to MedicationStatement and self-reported observations      │
│  • Cannot overwrite Tier 1 clinical orders without clinician review         │
├─────────────────────────────────────────────────────────────────────────────┤
│  TIER 3: AI/OCR SUGGESTIONS & EXTRACTION DRAFTS                             │
│  • Generated by OCR, Scribe Whisper, or background document parsing         │
│  • Sandboxed in LifeMap truth states as "draft"                             │
│  • Invisible to clinical handover or FHIR exports until human confirmation  │
│  • Fail-closed: Never auto-confirmed without explicit patient/doctor action │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Truth State Transition Machine

To guarantee auditability and prevent unauthorized state escalation, `services/api/src/clara_api/lifemap/domain.py` implements a deterministic truth state transition machine:

```text
               ┌──────────────┐
               │    draft     │
               └──────┬───────┘
                      │
         ┌────────────┼────────────────────────┐
         ▼            ▼                        ▼
┌────────────────┐ ┌───────────┐     ┌──────────────────┐
│ user_reported  │ │ confirmed │     │ entered_in_error │
└────────┬───────┘ └─────┬─────┘     └──────────────────┘
         │               │
         ├───────────────┼─────────────┐
         ▼               ▼             ▼
  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
  │  disputed   │ │ superseded  │ │ invalidated │
  └─────────────┘ └─────────────┘ └─────────────┘
```

- `draft`: Unverified extraction candidate from OCR or multimodal document parsing. Cannot be surfaced in clinical summaries or exported externally.
- `user_reported`: Assertion provided directly by the patient. Visible in timeline with clear patient-origin attribution.
- `confirmed`: Fact verified by a licensed clinician or confirmed by the patient with supporting clinical documentation.
- `disputed`: Assertion contested by either patient or clinician; preserved non-destructively in parallel.
- `superseded`: Historical entry made obsolete by newer clinical data, retained for longitudinal provenance.
- `invalidated`: Entry formally revoked by consent withdrawal or source retraction.
- `entered_in_error`: Entry created due to administrative error or duplicate scan, excluded from active views.

Any attempt to jump across non-permitted state transitions (e.g., `draft -> superseded` or `invalidated -> confirmed`) raises `InvalidTransition` and is blocked immediately.

---

## 3. Data Minimization Principles for Longitudinal Health Records

LifeMap enforces five core technical mechanisms to operationalize data minimization under Decree 13/2023/ND-CP and Law 15/2023/QH15:

### 3.1 Purpose-Bound Attribute-Based Access Control (ABAC)

Every interaction with LifeMap records requires server-side evaluation through `resolve_profile_scope` (`services/api/src/clara_api/lifemap/profile_scope.py`). Client-supplied profile identifiers are treated as untrusted hints:

1. **Owner Evaluation**: If the authenticated user is the profile owner, full read/write actions are granted within standard patient rights.
2. **Delegated Access (`FamilyAccessGrant`)**: Family members or caregivers access records solely via an active, non-expired grant that explicitly binds:
   - Specific grantee user ID;
   - Target profile ID;
   - Purpose of use (e.g., `family_caregiver`, `child_health_monitoring`);
   - Allowed action set (e.g., `{"view"}`);
   - Allowed data classes (e.g., `{"medications", "allergies"}` while withholding sensitive `{"conditions"}`);
   - Valid temporal validity window (`starts_at <= now < expires_at`).
3. **Administrative Isolation (`platform_root_cannot_read_phi`)**: System and tenant administrators have **zero** ambient access to patient health data. Profile scope queries by administrator roles reject access with HTTP 404 (`scope_forbidden`) and record a denied audit entry in `FamilyAccessLog` with reason code `break_glass_required`.
4. **Anti-Enumeration Oracle Protection**: Unauthorized or non-existent profile IDs return an identical HTTP 404 (`scope_forbidden`) response, ensuring that attackers cannot probe for patient existence.

### 3.2 Dynamic Consent Revocation Filtering

Under Decree 13/2023/ND-CP Article 17, when a patient revokes consent for a data source (e.g., disconnecting an external clinic sync, EHR import, or lab provider):

1. A `LifeMapSourceRevocation` record is committed with the corresponding `source_reference_id`.
2. All subsequent queries to `retrieve_revision_evidence` in `services/api/src/clara_api/lifemap/intelligence.py` perform a SQL anti-join:
   ```sql
   AND NOT EXISTS (
       SELECT 1 FROM lifemap_source_revocations
       WHERE lifemap_source_revocations.profile_id = lifemap_events.profile_id
         AND lifemap_source_revocations.source_reference_id = lifemap_event_revisions.source_reference_id
   )
   ```
3. The invalidation graph (`invalidate_projection_graph` in `services/api/src/clara_api/lifemap/projection_invalidation.py`) cascades through dependent derived projections (e.g., summaries, timeline caches, baseline metrics), marking them stale or invalidating them transitively.

### 3.3 Zero Chain-of-Thought (Zero-CoT) & Reasoning Redaction

To prevent prompt leakage, hallucinated reasoning exposure, or accidental disclosure of clinician-only diagnostic hypotheses:

1. Internal LLM chain-of-thought traces, model tokens, raw prompt engineering templates, and vector embeddings are permanently isolated inside internal service boundaries.
2. Consumer egress APIs return bounded, verified copy assembled from fixed strings or exact source revision text (`_consumer_copy`).
3. No internal diagnostic reasoning chain or clinical probability distribution is exposed to the end-user interface without human clinician oversight.

### 3.4 No-PII Telemetry & Outbox Envelope Isolation

All system metrics, performance monitoring, and background transactional outbox jobs strictly enforce zero-PII sanitization:

- **Metrics & OpenTelemetry**: Labels capture only numeric counts, HTTP status codes, tenant UUIDs, and endpoint paths. Patient names, Citizen Identity Card numbers (CCCD), phone numbers, query strings, and drug names are completely banned from telemetry labels.
- **Transactional Outbox (`lifemap_outbox_events`)**: Outbox envelopes carry only a synthetic `event_id`, an opaque UUID `profile_public_id`, and event category strings. The asynchronous worker resolves clinical payloads inside the protected domain service; the message queue never contains ambient plaintext health records.

### 3.5 Next-Best-Question Minimization

The LifeMap questioning engine (`services/api/src/clara_api/lifemap/next_best_question.py`) adheres strictly to data minimization §6.9:

- **Minimal Information Request**: Solicits the absolute smallest number of questions (ideally 1 or 0) required to bridge critical safety gaps.
- **Emergency Non-Interference**: If an acute clinical emergency is suspected, questioning is completely short-circuited (`ask nothing`) so that life-saving emergency escalation is never delayed.
- **No Harassment / Respect for Dismissal**: Questions dismissed by the user are never repeated without a distinct clinical triggering event.
- **Mandatory Justification**: Every solicited question must provide a transparent `why` rationale explaining to the patient why the data point is necessary for their care.

---

## 4. Multi-Source Conflict Preservation Architecture

In longitudinal health histories, conflicting medical assertions frequently arise:
- Doctor A diagnoses Type 2 Diabetes; Doctor B diagnoses Impaired Fasting Glucose.
- A clinical discharge summary lists Penicillin allergy; the patient claims they tolerated Amoxicillin without reaction.

Traditional electronic medical records frequently perform destructive overwrites, erasing earlier observations or silencing patient disputes. Under Law 15/2023/QH15 Article 15 and international clinical safety standards, destructive overwriting introduces severe clinical risks.

LifeMap implements the `ConflictPreservationEngine` (`services/api/src/clara_api/lifemap/conflict_preservation.py`):

1. **Parallel Competing Assertions**: Conflicting claims are retained as parallel assertions within the same clinical event container (`PreservedClinicalAssertion`).
2. **Explicit Confidence & Status Typing**: Each assertion records its `source_author`, `recorded_at`, `confidence`, and status (`CONFIRMED`, `DISPUTED`, `UNCERTAIN`, `SUPERSEDED`).
3. **Non-Destructive Dispute Tracking**: When a patient or clinician disputes an existing assertion, the engine does not delete or alter the original assertion. Instead, it appends a linked dispute entry (`disp-<assertion_id>`) referencing the original claim with detailed `dispute_notes`.
4. **Transparent Clinician Review**: Both competing views are preserved and surfaced side-by-side in the LifeMap Conflict Provenance UI, allowing the attending physician to exercise informed clinical judgment.

---

## 5. Emergency Fast-Path & Anti-Prescribing Legal Guardrails

Under Law 15/2023/QH15, software must never pose as a substitute for licensed emergency care or licensed clinical prescribers. `services/api/src/clara_api/lifemap/intelligence.py` implements a fail-closed routing filter (`route_ask_query`):

### 5.1 Emergency Fast-Path
Queries exhibiting acute life-threatening symptoms trigger an immediate emergency disposition:
- **Vietnamese Triggers**: `"khong tho duoc"`, `"dau nguc du doi"`, `"bat tinh"`, `"co giat"`.
- **English Triggers**: `"cannot breathe"`, `"severe chest pain"`, `"unconscious"`, `"seizure"`.
- **Behavior**: Sets `emergency=True`. Diagnostic reasoning and longitudinal timeline search are bypassed, immediately surfacing emergency escalation directives (calling 115, going to nearest emergency room).

### 5.2 Legal Hard-Guard (Anti-Prescribing & Anti-Diagnosis)
Prompts demanding autonomous diagnoses or prescription orders are blocked at ingress:
- **Vietnamese Triggers**: `"chan doan cho toi"`, `"toi bi benh gi"`, `"ke don"`, `"lieu dung cho toi"`.
- **English Triggers**: `"diagnose me"`, `"what disease do i have"`, `"prescribe"`, `"my dosage"`.
- **Behavior**: Sets `blocked_reason="legal_guard"`. Returns fixed educational guidance explaining that under Vietnamese law, only licensed healthcare practitioners can formulate diagnoses and issue prescriptions.

---

## 6. Audit Verification & Codebase Anchor Traceability

The table below documents verified source anchors and invariant mappings across the CLARA Care repository:

| Statutory / Safety Requirement | Legal Basis | Implementation File | Symbol / Class | Invariant Enforcement |
|---|---|---|---|---|
| **Purpose-Bound ABAC Scope** | PDPD Art. 3, 9, 28 | `services/api/src/clara_api/lifemap/profile_scope.py` | `ProfileScope`, `resolve_profile_scope` | Resolves actor, profile, purpose, allowed actions, data classes; validates tenant isolation. |
| **Admin PHI Lockout** | Law 15/2023 Art. 8 | `services/api/src/clara_api/lifemap/profile_scope.py` | `ProfileAccessPolicy.administrative` | Blocks admin access with 404 `scope_forbidden`; logs denied break-glass attempt. |
| **Uniform Anti-Enumeration** | PDPD Art. 8, 28 | `services/api/src/clara_api/lifemap/profile_scope.py` | `resolve_profile_scope` | Emits HTTP 404 (`scope_forbidden`) for missing, unpermitted, and admin queries alike. |
| **Truth State Machine** | Law 15/2023 Art. 15 | `services/api/src/clara_api/lifemap/domain.py` | `TRUTH_TRANSITIONS`, `require_truth_transition` | Prevents arbitrary state mutation; enforces valid lifecycle paths. |
| **Non-Destructive Dispute** | Law 15/2023 Art. 15 | `services/api/src/clara_api/lifemap/conflict_preservation.py` | `ConflictPreservationEngine` | Preserves competing assertions (`DISPUTED`, `CONFIRMED`); links disputes without deletion. |
| **Emergency Fast-Path** | Law 15/2023 Art. 32 | `services/api/src/clara_api/lifemap/intelligence.py` | `route_ask_query`, `_EMERGENCY_HINTS` | Detects acute respiratory, cardiac, and neurological emergencies; skips diagnostic lookup. |
| **Legal Anti-Prescribe Guard** | Law 15/2023 Art. 32/53 | `services/api/src/clara_api/lifemap/intelligence.py` | `route_ask_query`, `_FORBIDDEN_HINTS` | Blocks autonomous prescribing and diagnosis inquiries with `legal_guard`. |
| **Revocation Anti-Join** | PDPD Art. 17 | `services/api/src/clara_api/lifemap/intelligence.py` | `retrieve_revision_evidence` | Excludes revoked source reference IDs from active query projections. |
| **Profile-Partitioned Search** | PDPD Art. 3, 28 | `services/api/src/clara_api/lifemap/temporal_index.py` | `TemporalRetrievalIndex` | Separates document dictionaries per profile partition; reranker escapes fail-closed. |
| **Personal Baseline Limits** | Law 15/2023 Art. 15 | `services/api/src/clara_api/lifemap/baselines.py` | `BaselineResult`, `_scalar` | Compares patient only against their own history; never classifies clinical normality. |
| **Question Minimization** | PDPD Art. 9 | `services/api/src/clara_api/lifemap/next_best_question.py` | `NextBestQuestionEngine` | Asks 0 or 1 question strictly to resolve safety gaps; emergency disposition short-circuits. |
| **Transitive Invalidation** | PDPD Art. 12, 17 | `services/api/src/clara_api/lifemap/projection_invalidation.py` | `invalidate_projection_graph` | Recursively cascades invalidations across derived timeline projections on dispute/revocation. |

---

## 7. Conclusion & Next-Phase Recommendations

The LifeMap longitudinal intelligence subsystem demonstrates comprehensive alignment with the Vietnamese Law on Medical Examination and Treatment No. 15/2023/QH15 and Personal Data Protection Decree No. 13/2023/ND-CP.

**Key Recommendations for Phase PH13+**:
1. **Automated Consent Re-evaluation on Reconnect**: When external wearable sync or lab connectors are re-authorized, ensure backfill jobs strictly honor historical revocation timestamps without retroactively reprocessing deleted events.
2. **PostgreSQL RLS Hardening**: Supplement application-layer `ProfileScope` checks with PostgreSQL Row-Level Security (RLS) policies on `lifemap_events` and `lifemap_event_revisions` to enforce tenant and profile boundary isolation at the database driver level.
3. **Structured DSAR Portability Package**: Ensure the ZIP export produced under DSAR compliance incorporates the complete `PreservedClinicalAssertion` provenance graph so patients can port both their confirmed records and their preserved dispute histories seamlessly.

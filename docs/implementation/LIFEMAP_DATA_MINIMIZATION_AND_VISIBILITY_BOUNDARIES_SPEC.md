# LifeMap Data Minimization & Visibility Boundaries Specification

- **Phase ID**: PH12 (LifeMap longitudinal intelligence)
- **Agent ID**: A09
- **Role**: Docs + research evidence
- **Applicable Standards**:
  - Vietnam Law on Medical Examination and Treatment No. 15/2023/QH15
  - Decree 13/2023/ND-CP on Personal Data Protection (PDPD)
  - HL7 FHIR R4 Provenance and AuditEvent Profiles
- **Baseline Commit**: `36e5b95fac7e65712f0779de253d8ed18dc693d7`
- **Status**: **VERIFIED & OPERATIONAL**

---

## 1. Architectural Component Model

The LifeMap longitudinal intelligence subsystem implements a layered defense-in-depth architecture to enforce data minimization, strict profile isolation, and clinical safety boundaries:

```text
                      ┌───────────────────────────────┐
                      │   Client Request (Web / App)  │
                      └──────────────┬────────────────┘
                                     │ (Profile ID is an untrusted hint)
                                     ▼
         ┌────────────────────────────────────────────────────────┐
         │                 FASTAPI API GATEWAY                    │
         │  • Bearer Token Extraction & Validation                │
         │  • CSRF & Session Isolation                            │
         │  • Tenant & Role Binding Verification                  │
         └───────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
         ┌────────────────────────────────────────────────────────┐
         │             PROFILE SCOPE RESOLVER (ABAC)              │
         │  • resolve_profile_scope / require_profile_scope       │
         │  • Owner Check vs. FamilyAccessGrant Validation        │
         │  • Data Class & Purpose Gating                         │
         │  • Administrative Block: platform_root_cannot_read_phi │
         │  • Uniform 404 on Unauthorized / Missing               │
         └───────────────────────────┬────────────────────────────┘
                                     │ Authorized ProfileScope
                                     ▼
   ┌─────────────────────────────────┴─────────────────────────────────┐
   │                                                                   │
   ▼                                                                   ▼
┌───────────────────────────────┐                   ┌───────────────────────────────┐
│     QUERY SAFETY ROUTER       │                   │    TEMPORAL RETRIEVAL INDEX   │
│  • route_ask_query            │                   │  • Profile-partitioned dict   │
│  • Emergency Fast-Path        │                   │  • Data class filter          │
│  • Anti-Prescribing Hard-Guard│                   │  • Reranker boundary guard    │
└──────────────┬────────────────┘                   └───────────────┬───────────────┘
               │                                                    │
               ▼                                                    ▼
┌───────────────────────────────┐                   ┌───────────────────────────────┐
│   NEXT-BEST-QUESTION ENGINE   │                   │  CONFLICT PRESERVATION ENGINE │
│  • Max 1 or 0 questions       │                   │  • Parallel clinical claims   │
│  • Emergency short-circuit    │                   │  • Non-destructive disputes   │
│  • Mandatory why justification│                   │  • Confidence score typing    │
└───────────────────────────────┘                   └───────────────┬───────────────┘
                                                                    │
                                                                    ▼
                                                    ┌───────────────────────────────┐
                                                    │    DATABASE ACCESS LAYER      │
                                                    │  • Revocation Anti-Join       │
                                                    │  • LifeMapTruthTransitions    │
                                                    │  • No-PII Telemetry & Outbox  │
                                                    └───────────────────────────────┘
```

---

## 2. ProfileScope Engine & Access Authorization

### 2.1 Scope Dataclass (`ProfileScope`)

Located in `services/api/src/clara_api/lifemap/profile_scope.py`:

```python
@dataclass(frozen=True)
class ProfileScope:
    actor: User
    profile: PhrProfile
    actor_role: str
    purpose: str
    allowed_actions: frozenset[str]
    allowed_data_classes: frozenset[str]
    grant_id: int | None = None
    valid_until: datetime | None = None
    tenant_id: str = "default"
    organization_id: str | None = None
```

### 2.2 Security Invariants of Scope Resolution

1. **Owner Exclusivity**:
   If `actor_role == "owner"`, the scope requires `profile.user_id == actor.id`. The owner is granted comprehensive actions (`view`, `create`, `confirm`, `correct`, `dispute`, `invalidate`, `resolve`, `accept`, `complete`, `share`, `export`) across all personal health data classes (`lifemap`, `medications`, `allergies`, `conditions`, `observations`, `visits`, `evidence`).

2. **Tenant Confinement**:
   If `profile.tenant_id` is set, it must strictly match `ProfileScope.tenant_id`. Cross-tenant scope requests are rejected with a `ValueError` during initialization, preventing multi-tenant data cross-contamination.

3. **Administrative Lockout (`platform_root_cannot_read_phi`)**:
   Administrative roles (`admin`, platform support) do not possess health data reading capabilities. When an administrator attempts to resolve a patient's `ProfileScope`:
   - Access is denied immediately.
   - An audit row is appended to `FamilyAccessLog` with `outcome="denied"` and `metadata_json={"reason_code": "break_glass_required"}`.
   - An HTTP 404 (`detail={"code": "scope_forbidden", "message": "Profile not found"}`) is returned to avoid revealing the existence of the record.

4. **Uniform Anti-Enumeration 404**:
   Whether a profile does not exist or the actor lacks authorization, the resolver emits an identical HTTP 404 response with code `"scope_forbidden"`. Attackers cannot determine whether a given UUID corresponds to a registered patient.

5. **Delegated Access Gating (`FamilyAccessGrant`)**:
   Non-owner users require an active `FamilyAccessGrant` row meeting all criteria:
   - `grantee_user_id == actor.id`
   - `profile_id == profile.id`
   - `status == "active"` and `revoked_at IS NULL`
   - `starts_at <= now < expires_at`
   - `purpose == requested_purpose`
   - `action IN grant.allowed_actions_json`
   - `data_class IN grant.data_classes_json`

---

## 3. Truth State Machine & Lifecycle Transitions

Health assertions transition strictly according to the deterministic state table in `services/api/src/clara_api/lifemap/domain.py`:

```python
TRUTH_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"user_reported", "confirmed", "invalidated", "entered_in_error"}),
    "user_reported": frozenset({"confirmed", "disputed", "superseded", "invalidated"}),
    "confirmed": frozenset({"disputed", "superseded", "invalidated"}),
    "disputed": frozenset({"confirmed", "superseded", "invalidated"}),
    "superseded": frozenset(),
    "invalidated": frozenset(),
    "entered_in_error": frozenset(),
}
```

### Transition Invariants
- Terminal states (`superseded`, `invalidated`, `entered_in_error`) have an empty transition set; once marked terminal, a record cannot be revived.
- Unverified capture drafts (`draft`) can never transition directly to `superseded` or `disputed`; they must first be either confirmed or user-reported.
- `require_truth_transition(current, target)` raises `InvalidTransition` if an unapproved transition is attempted.

---

## 4. Multi-Source Conflict Preservation Engine

The `ConflictPreservationEngine` in `services/api/src/clara_api/lifemap/conflict_preservation.py` prevents destructive overwriting of conflicting clinical assertions:

### 4.1 Record Assertion Protocol
When clinical notes, lab results, or patient reports provide a new observation:
```python
engine.record_assertion(
    event_id="evt-101",
    assertion_id="asst-1",
    claim_text="Hypertension Grade 1",
    source_author="Dr. Tran (Cardiology)",
    status="CONFIRMED",
    confidence=0.95,
)
```

### 4.2 Dispute Assertion Protocol
When a second opinion or patient contests a claim:
```python
engine.dispute_assertion(
    event_id="evt-101",
    assertion_id="asst-1",
    disputing_actor="Patient / Caregiver",
    dispute_reason="Blood pressure normalized after lifestyle change; 24h Holter normal",
)
```
- The original assertion `asst-1` remains in history unmodified.
- A new linked assertion `disp-asst-1` is recorded with `status="DISPUTED"` and `confidence=0.5`.
- `get_competing_assertions(event_id)` returns both entries, preserving full medical provenance for attending clinicians.

---

## 5. Temporal Retrieval Index & Isolation

The `TemporalRetrievalIndex` in `services/api/src/clara_api/lifemap/temporal_index.py` enforces retrieval boundaries:

1. **Partition Isolation**:
   ```python
   self._partitions.setdefault(document.profile_partition, {})[document.document_id] = document
   ```
   Searches operate strictly within `self._partitions.get(profile_partition, {})`. Cross-profile indexing is physically impossible.

2. **Data Class & Window Gating**:
   Candidates must pass:
   - `document.is_active`
   - `document.data_class in allowed_data_classes`
   - `episode_id is None or episode_id in document.episode_ids`
   - `start_at is None or document.effective_start >= start_at`
   - `end_at is None or document.effective_start <= end_at`

3. **Reranker Escape Prevention**:
   If an external neural reranker or LLM reranker is invoked:
   ```python
   if len(set(ordered_ids)) != len(ordered_ids) or not set(ordered_ids) <= candidate_ids:
       raise RetrievalBoundaryError("reranker_escaped_candidate_set")
   ```
   Any attempt by a reranker to introduce foreign document IDs raises `RetrievalBoundaryError`, preventing prompt injection from injecting unvetted clinical documents.

---

## 6. Query Safety Router & Regulatory Hard-Guards

The query router in `services/api/src/clara_api/lifemap/intelligence.py` inspects every incoming user query before database queries or LLM calls:

```python
def route_ask_query(query: str) -> SafetyRoute:
    folded = _fold(query)
    if any(hint in folded for hint in _EMERGENCY_HINTS):
        return SafetyRoute(intent="timeline_lookup", emergency=True)
    if any(hint in folded for hint in _FORBIDDEN_HINTS):
        return SafetyRoute(intent="explanation", blocked_reason="legal_guard")
    for intent, hints in _INTENT_HINTS:
        if any(hint in folded for hint in hints):
            return SafetyRoute(intent=intent)
    return SafetyRoute(intent="timeline_lookup")
```

### Safety Rules:
1. **Emergency Fast-Path**: Acute emergency symptoms (`"khong tho duoc"`, `"severe chest pain"`, `"bat tinh"`, `"seizure"`) immediately return `emergency=True`. Longitudinal query pipelines abort heavy retrieval and return emergency guidance.
2. **Legal Anti-Prescribing Hard-Guard**: Prescribing and diagnostic requests (`"chan doan cho toi"`, `"diagnose me"`, `"ke don"`, `"my dosage"`) return `blocked_reason="legal_guard"`.
3. **Vietnamese Text Normalization**: Folding (`_fold`) strips diacritics and normalizes cases (e.g., `"đ"` -> `"d"`, `NFKD` decomposition) to ensure evasion attempts using non-standard accents fail.

---

## 7. Next-Best-Question Minimization

In compliance with PDPD Article 9 (data minimization), the `NextBestQuestionEngine` (`services/api/src/clara_api/lifemap/next_best_question.py`) ensures:
- **Zero Question Emergency Rule**: When an episode has an active emergency disposition, questioning returns 0 questions.
- **Single Question Bound**: Returns at most 1 high-priority question that resolves an actionable clinical ambiguity.
- **Dismissal Respect**: Questions dismissed by the patient are suppressed.
- **Mandatory Rationale**: Every question presents an understandable `why` explanation to the user.

---

## 8. Outbox Payload & Telemetry Data Minimization

1. **Transactional Outbox Events**:
   Events committed to `lifemap_outbox_events` contain:
   ```json
   {
     "event_id": "outbox-uuid-4",
     "profile_public_id": "profile-uuid-4",
     "event_type": "lifemap.event.created",
     "occurred_at": "2026-10-24T12:00:00Z"
   }
   ```
   **Forbidden Fields**: Patient names, email addresses, phone numbers, raw medical notes, medication dosages, and diagnosis free-text.

2. **OpenTelemetry Labels**:
   Permitted labels: `tenant_id`, `route`, `status_code`, `action`, `intent`.
   Forbidden labels: Any user identifier, patient name, medical condition, or clinical search query.

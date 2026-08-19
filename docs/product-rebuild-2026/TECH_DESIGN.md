# CLARA Care Product Rebuild — Technical Design

**Status:** proposed implementation architecture  
**Date:** 2026-08-19  
**Repository:** `Project-CLARA-HBT/CLARA-Care`  
**Constraint:** preserve current safety/governance contracts while replacing the module-first product surface.

---

## 1. Architecture goals

The redesign needs to solve five technical problems at the same time:

1. simplify the UI without weakening server authorization;
2. converge health information in presentation while preserving domain truth/provenance;
3. make multimodal AI a shared platform capability rather than ad hoc feature code;
4. generalize the model registry so private/unofficial Gemini routes can be used safely;
5. migrate incrementally with rollback and old-client compatibility.

The recommended architecture is a **strangler rebuild** around the existing API/GLHS/LifeMap foundations, not a greenfield rewrite.

---

## 2. Current architecture observations

### Web

- Next.js App Router, React/TypeScript, Tailwind/design tokens.
- Current route count is large and domain-oriented.
- `AppShell` is still a client-heavy orchestration boundary.
- remote data is often manually loaded with `useEffect/useState`.
- Chat V2 has its own complex shell, execution-mode state and workspace concepts.
- route access and presentation have improved separation but are still spread across navigation modules.

### Mobile

- Flutter app has a redesign root and role-aware feature resolver.
- Home V3 is still a feature-card launcher.
- consumer terminology helpers exist but many strings remain screen-specific.

### API/data

- FastAPI/SQLAlchemy domain contains profile scoping, PHR, LifeMap, visits, medications, consent, public shares and GLHS adapters.
- Universal Capture already has secure artifact storage, malware-status handling, capture sessions, typed candidates, source spans, review actions and governed ingestion seams.
- PHR client still exposes whole-record PUT for a major record shape.

### ML

- `ModelTask` + versioned task contracts are a good safety abstraction.
- current resolver is deliberately DeepSeek-specific and assumes pro/flash profiles.
- model calls should be refactored around capabilities/provider adapters without throwing away task contracts.

---

## 3. Target logical architecture

```text
┌────────────────────────────────────────────────────────────┐
│                    Web / Flutter clients                    │
│ Home | Ask | Health | Care | You | Professional modes      │
└───────────────┬─────────────────────────────┬──────────────┘
                │                             │
        Typed consumer API             Upload/media API
                │                             │
┌───────────────▼─────────────────────────────▼──────────────┐
│                         API service                         │
│ Auth/Profile │ Home read model │ Health projection         │
│ Care/Visits  │ Bounded commands │ Sharing/Consent           │
│ Capture orchestration │ GLHS gateway │ Audit                │
└──────┬───────────────┬───────────────┬──────────────────────┘
       │               │               │
       │         PostgreSQL/outbox     │
       │                               │
       ▼                               ▼
┌───────────────────┐        ┌───────────────────────────────┐
│ Connected Health  │        │          ML service           │
│ FHIR / Health     │        │ Task contracts                │
│ Connect / future  │        │ Model Gateway                 │
│ HealthKit         │        │ Retrieval / verification      │
└───────────────────┘        │ Multimodal extraction         │
                             │ Provider adapters              │
                             └──────────────┬────────────────┘
                                            │
                                 approved private gateways
```

Key rule: the ML service does not own authorization. The API constructs/requests a governed context and the model receives only bounded task input.

---

## 4. Repository-level target structure

Do not require a monorepo tool migration to start. Reorganize incrementally.

### Web

```text
apps/web/
  app/
    (public)/
      page.tsx
      login/
      register/
      legal/
    (consumer)/
      layout.tsx
      home/
      ask/
      health/
        timeline/
        medications/
        results/
        measurements/
        documents/
      care/
        visits/
        prepare/
        check-symptoms/
        family/
      you/
        profile/
        sharing/
        privacy/
        integrations/
        notifications/
    (professional)/
      layout.tsx
      work/
      council/
      scribe/
      evidence/
    (admin)/
      admin/
  components/
    consumer/
    health/
    care/
    ask/
    professional/
    shared/
  lib/
    api/
    query/
    auth/
    profile/
    content/
    analytics/
    feature-flags/
    health-view-model/
  styles/
    tokens.css
    base.css
    components.css
```

Legacy routes may live as thin redirect/adapters until retired.

### Mobile

```text
apps/mobile/lib/
  app/
  navigation/
  features/
    home/
    ask/
    health/
    care/
    you/
    professional/
  data/
    api/
    repositories/
    connected_health/
  design/
    tokens/
    components/
  content/
    terminology/
    localization/
```

Do not duplicate medical safety rules in Dart. Mobile consumes the same API capability/read models.

---

## 5. Web shell redesign

### 5.1 Split `AppShell`

Target boundaries:

- `SessionBoundary`: authoritative `/auth/me`/session state and unauthenticated redirects.
- `ProfileBoundary`: active profile context and safe switch.
- `ConsumerLayout`: desktop/mobile navigation only.
- `ProfessionalLayout`: professional mode shell.
- `PreferenceProvider`: language/theme/accessibility preferences.
- `NotificationBadgeProvider`: coarse counts only, independently loaded.

Avoid one component owning all request orchestration.

### 5.2 Server state

Adopt one consistent server-state layer for the rebuilt surfaces. Recommended: TanStack Query for the client where interactive caching is required, while using Next.js server components/fetching for initial route data when it reduces client JS.

Rules:

- health truth remains server-authoritative;
- query keys always include active profile ID or a server-resolved context version where needed;
- changing profile invalidates all profile-scoped query caches immediately;
- revoked shared-profile context clears cached data before rendering new context;
- cache does not substitute for authorization.

Small UI preferences may use React context/local state. Do not put health record data in a global client store.

### 5.3 Navigation registry

Replace presentation arrays spread across role/workspace code with a typed capability registry:

```ts
type ProductDestination = {
  id: "home" | "health" | "care" | "you" | "professional";
  canonicalHref: string;
  labelKey: UITranslationKey;
  icon: IconName;
  presentationGate?: CapabilityKey;
};
```

Authorization remains in server/API route policy. `presentationGate` only controls whether a destination is useful/visible.

---

## 6. Consumer API/read-model design

### 6.1 `GET /api/v2/home`

Profile-scoped response designed to eliminate client fan-out:

```json
{
  "profile": {
    "id": "opaque",
    "display_name": "...",
    "kind": "self"
  },
  "generated_at": "...",
  "context_version": "opaque-version",
  "top_action": {
    "id": "...",
    "kind": "medication|visit|review|task|result",
    "title_key": "...",
    "params": {},
    "href": "/...",
    "severity": "normal|attention|urgent",
    "source_ids": []
  },
  "today": [],
  "recent_changes": [],
  "alerts": [],
  "trend_cards": [],
  "integration_state": {
    "last_sync_at": null,
    "has_connected_health": false
  }
}
```

Requirements:

- stable, bounded payload;
- no raw arbitrary HTML;
- messages preferably key + typed params;
- `urgent` reserved for clinically approved semantics;
- slow connected-health sources use cached canonical data and do not block response.

### 6.2 `GET /api/v2/health/summary`

Consumer health projection:

```json
{
  "current": {
    "allergies": [],
    "conditions": [],
    "medications": [],
    "important_measurements": []
  },
  "recent_results": [],
  "documents": [],
  "completeness": {
    "missing_categories": []
  },
  "conflicts": [],
  "context_version": "..."
}
```

Do not turn completeness into a competitive score. Missing categories are prompts only when relevant.

### 6.3 Timeline

`GET /api/v2/health/timeline?cursor=&from=&to=&types=`

Return normalized display events:

```json
{
  "items": [
    {
      "id": "opaque",
      "kind": "medication_change",
      "effective_at": "...",
      "recorded_at": "...",
      "title": "...",
      "summary": "...",
      "state": "confirmed|reported|unconfirmed|conflict",
      "source": {"kind": "document", "label": "..."},
      "episode_id": "opaque-or-null",
      "detail_href": "/..."
    }
  ],
  "next_cursor": "..."
}
```

The projection can unify display but must retain identifiers that resolve to underlying domain entities.

---

## 7. Bounded write design

### 7.1 Retire blind whole-record PHR writes

Current `PUT /phr/record` should remain compatibility-only while new UI uses bounded commands.

Examples:

```text
PATCH /api/v2/health/demographics
POST  /api/v2/health/allergies
PATCH /api/v2/health/allergies/{id}
POST  /api/v2/health/conditions
POST  /api/v2/health/medications/{id}/changes
POST  /api/v2/health/measurements
```

Each write carries:

- `profile_id` only if needed as requested context;
- `base_version`/ETag or resource state token;
- idempotency/command ID;
- explicit source;
- effective time;
- user intent/action;
- GLHS proposal binding when AI-derived.

### 7.2 Conflict response

Use HTTP `409` or `412` with structured conflict data:

```json
{
  "code": "state_changed",
  "current_version": "...",
  "changed_fields": ["..."],
  "safe_to_reapply": false
}
```

Client behavior:

- never discard local edit;
- fetch current record;
- show a human-readable compare/review;
- resubmit against current version only after explicit safe merge/user confirmation.

### 7.3 GLHS AI proposal envelope

Any AI proposal that consumed governed personal context uses:

```json
{
  "proposal_id": "opaque",
  "profile_id": "opaque",
  "task": "lifemap_capture|medication_update|visit_action|...",
  "base_state_version": "...",
  "policy_version": "...",
  "consent_version": "...",
  "thss_digest": "...",
  "source_artifact_ids": [],
  "candidate_schema_version": "...",
  "proposed_changes": [],
  "model_run_id": "opaque"
}
```

Commit path rechecks state/authorization/consent atomically on the real DB path.

---

## 8. Unified health projection without unsafe data merging

Create a presentation-layer resolver, not a giant merged table.

### 8.1 Medication projection

Inputs:

- medication course/current state;
- PHR medication entries;
- cabinet scan candidates;
- imported FHIR MedicationRequest/MedicationStatement equivalents when supported.

Output groups by normalized identity where confidence/policy allow, but retains source children.

Example:

```json
{
  "display_id": "medgrp_...",
  "display_name": "Amlodipine 5 mg",
  "current_state": "taking|stopped|unknown|conflict",
  "state_basis": "confirmed_course",
  "sources": [
    {"kind": "course", "state": "confirmed"},
    {"kind": "cabinet_scan", "state": "unconfirmed"}
  ],
  "needs_review": false
}
```

Never infer “taking” solely because a medicine exists in a cabinet image.

### 8.2 Conflict resolver

Rules detect conflict candidates; generative AI may explain them but does not choose truth.

Examples:

- active vs stopped medication overlap;
- incompatible allergy statements;
- duplicate imported records;
- two different units/values for the same effective time;
- corrected document vs old user-reported fact.

Persist a review task rather than silently mutating truth.

---

## 9. Multimodal Universal Capture architecture

Reuse and extend existing `lifemap_capture` infrastructure.

### 9.1 Pipeline

```text
Client capture
  -> create capture session
  -> upload artifact / text / audio reference
  -> media validation
  -> malware scan / encrypted storage
  -> deterministic preprocessing (orientation, page render, OCR if applicable)
  -> AI extraction request with only artifact + bounded context
  -> schema validation
  -> candidate normalization
  -> contradiction/duplicate checks
  -> review UI
  -> user accept/edit/reject
  -> GLHS-bound commit command
  -> outbox/invalidation
```

### 9.2 Artifact types

- `text/plain`
- `image/jpeg`, `image/png`, `image/webp` as explicitly supported
- PDF with page limit
- supported audio codecs

Reject ambiguous/unsafe files before model calls.

### 9.3 Candidate contract v2

```json
{
  "id": "opaque",
  "category": "medication|measurement|result|condition|allergy|visit|instruction|note",
  "field_path": "...",
  "value": {},
  "state": "draft",
  "confidence": null,
  "uncertainty": {
    "reason_codes": ["ocr_disagreement"],
    "missing_fields": []
  },
  "source": {
    "artifact_id": "opaque",
    "page": 1,
    "span": {"start": 0, "end": 20},
    "region": [0.1, 0.2, 0.4, 0.3]
  },
  "normalization": {
    "status": "candidate",
    "system": "rxnorm",
    "code": "..."
  },
  "requires_confirmation": true,
  "schema_version": "capture-candidate-v2"
}
```

Avoid presenting raw numerical model confidence as consumer truth. Keep it for internal routing/QA where calibrated.

### 9.4 Document prompt-injection boundary

The extraction task system prompt must explicitly state uploaded text is untrusted. Tool access for extraction should normally be zero or a tightly defined normalization tool set. Never allow document text to request another user's record, change task purpose or alter output schema.

---

## 10. Ask orchestration architecture

### 10.1 Consumer request

```json
POST /api/v2/ask
{
  "conversation_id": "...",
  "text": "...",
  "attachments": ["artifact-id"],
  "entry_context": {
    "kind": "global|result|medication|visit|timeline_period",
    "resource_id": "opaque-or-null"
  }
}
```

The client does not send `model`, `provider`, `fast/deep`, or raw retrieval mode.

### 10.2 API intent/risk planning

API/ML bounded router returns a plan enum, not arbitrary tools:

```text
GENERAL_EXPLANATION
PERSONAL_TIMELINE_QA
RESULT_EXPLANATION
MEDICATION_SAFETY
DOCUMENT_EXPLANATION
VISIT_PREP
CARE_NAVIGATION
RESEARCH_EVIDENCE
CAPTURE_PROPOSAL
REFUSE_OR_ESCALATE
```

For personal tasks, API obtains task-scoped governed context using GLHS/THSS rules before the synthesis call.

### 10.3 Answer envelope

```json
{
  "answer": {
    "main_message": "...",
    "actions": [],
    "sections": []
  },
  "personal_evidence": [
    {"id": "pe_1", "resource_id": "...", "effective_at": "...", "state": "confirmed"}
  ],
  "external_sources": [],
  "unknowns": [],
  "safety": {
    "urgency": "none|routine|soon|urgent|emergency",
    "deterministic_floor_applied": false
  },
  "write_proposals": [],
  "disclosure": {
    "used_personal_context": true,
    "data_classes": ["medications", "allergies"]
  }
}
```

Streaming can emit typed events for message text, source availability, safety outcome and proposal readiness. Do not stream internal reasoning tokens.

---

## 11. Provider-neutral Model Gateway

### 11.1 Preserve task contracts, replace provider coupling

Current good abstraction:

- `ModelTask`
- risk level
- output contract
- prompt version
- tools
- fallback policy
- human review threshold

Refactor `model_profile: pro|flash` to capabilities/routing class.

Suggested types:

```python
class ModelCapability(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    STRUCTURED_OUTPUT = "structured_output"
    TOOL_CALLING = "tool_calling"
    LONG_CONTEXT = "long_context"

class RouteClass(StrEnum):
    FAST_MULTIMODAL = "fast_multimodal"
    QUALITY_MULTIMODAL = "quality_multimodal"
    TEXT_REASONING = "text_reasoning"
    ASR = "asr"
    EMBEDDING = "embedding"
```

`TaskContract` becomes:

```python
@dataclass(frozen=True)
class TaskContract:
    task: ModelTask
    risk_level: str
    route_class: RouteClass
    required_capabilities: tuple[ModelCapability, ...]
    prompt_version: str
    output_contract: str
    safety_fallback: str
    temperature: float
    max_tokens: int
    required_tools: tuple[str, ...]
    review_policy: str
    timeout_ms: int
    shadow_only: bool = False
```

### 11.2 Adapter interface

```python
class ModelProviderAdapter(Protocol):
    provider_id: str

    def capabilities(self, route: ResolvedRoute) -> set[ModelCapability]: ...
    async def generate(self, request: ModelRequest) -> ModelResponse: ...
    async def health_probe(self, route: ResolvedRoute) -> ProbeResult: ...
```

Implement adapters such as:

- current DeepSeek adapter;
- `UnofficialGeminiGatewayAdapter`;
- ASR adapter remains separate where appropriate.

### 11.3 Private Gemini aliases

Deployment example only:

```env
CLARA_MODEL_ROUTE_FAST_MULTIMODAL_PROVIDER=unofficial_gemini_gateway
CLARA_MODEL_ROUTE_FAST_MULTIMODAL_MODEL=gemini-3.6-flash-high
CLARA_MODEL_ROUTE_QUALITY_MULTIMODAL_PROVIDER=unofficial_gemini_gateway
CLARA_MODEL_ROUTE_QUALITY_MULTIMODAL_MODEL=gemini-3.7-tiered
CLARA_UNOFFICIAL_GEMINI_BASE_URL=https://private-gateway.example/v1
CLARA_UNOFFICIAL_GEMINI_API_KEY=...
```

Names are not exposed to clients and are not assumed to be stable official vendor IDs.

### 11.4 Capability probe

At startup/deploy check:

- authenticated connectivity;
- text response;
- image input if declared;
- structured JSON adherence;
- streaming if required;
- maximum accepted image/PDF behavior as configured;
- error mapping/timeouts.

Probe payload is synthetic and contains no PHI.

If a declared capability fails, mark route unavailable and do not send live medical requests to it.

### 11.5 Routing/promotion

Each task maps to an approved route set:

```yaml
lifemap_text_draft_extraction:
  primary: fast_multimodal
  fallback: deterministic_only

result_explanation:
  primary: quality_multimodal
  fallback: no_ai_explanation

medication_safety_wording:
  primary: fast_multimodal
  authoritative_tools: [drug_interaction_engine]
  fallback: deterministic_safety_copy
```

The deterministic source/tool remains authoritative for medication interactions; the model explains results rather than inventing them.

---

## 12. Model provenance and observability

Create a PII-safe `model_run` record/event with:

- opaque run ID;
- task;
- task contract version;
- provider adapter ID;
- deployment model alias;
- gateway/model version if returned;
- route configuration hash;
- prompt version/hash;
- output schema version;
- tool versions;
- governed input context digest, not raw content;
- input modality counts/byte buckets;
- latency;
- token/media usage if available;
- completion/error code;
- safety verification outcome;
- whether output was displayed/committed/rejected.

Raw request/response content belongs only in narrowly controlled clinical/debug stores if policy explicitly permits it; do not put it in ordinary telemetry.

---

## 13. Retrieval and personal-context design

### 13.1 Two evidence classes

Keep personal and external evidence distinct throughout pipeline:

```text
Personal evidence: user's authorized record, source/time/state aware
External evidence: medical literature/guidelines/drug knowledge
```

The answer renderer labels them differently.

### 13.2 Temporal personal retrieval

For personal QA retrieval ranking must account for:

- profile scope;
- task/purpose permission;
- current/valid state;
- effective time and recorded time;
- corrections/supersession;
- confirmation/source status;
- explicit query period;
- conflict state.

Semantic similarity alone cannot decide current truth.

### 13.3 Context minimization

Build a deterministic evidence table first, then synthesize. Do not dump the entire health record into a multimodal LLM simply because context length allows it.

---

## 14. Connected Health design

### 14.1 Canonical connector envelope

```python
@dataclass
class ConnectedObservationEnvelope:
    profile_id: int
    source_system: str
    source_record_id: str
    source_device_id: str | None
    data_type: str
    effective_start: datetime
    effective_end: datetime | None
    observed_value: dict
    unit: str | None
    source_version: str | None
    ingested_at: datetime
    provenance: dict
```

Deduplication key includes source system + source record identity/version, not just timestamp/value.

### 14.2 Android Health Connect bridge

Flutter approaches:

- create a small native Kotlin platform plugin if existing Flutter libraries do not expose required/current Health Connect APIs;
- use Jetpack Health Connect APIs directly for supported data and feature availability;
- keep Medical Records/FHIR integration behind a separate experimental flag;
- request permissions per category in context;
- sync via bounded background job/WorkManager bridge where needed;
- store last sync cursor/checkpoint server-side and/or device-side safely.

Do not claim data is medically validated merely because Health Connect supplies it.

### 14.3 Future HealthKit bridge

Mirror the connector envelope and permission philosophy; do not fork downstream health semantics by platform.

---

## 15. Notification architecture

### 15.1 Server notification object

```json
{
  "id": "opaque",
  "profile_id": "opaque",
  "category": "medication|visit|review|result|safety|sync",
  "severity": "info|attention|urgent",
  "message_key": "...",
  "params": {},
  "action_href": "/...",
  "created_at": "...",
  "expires_at": "...",
  "dedupe_key": "..."
}
```

### 15.2 Intelligent bundling

AI MAY help phrase or cluster non-urgent notifications, but deterministic policy controls:

- urgent delivery;
- quiet hours exceptions;
- medication timing;
- max frequency;
- mandatory compliance/safety notices.

No AI optimization on emotional vulnerability.

---

## 16. Content architecture

### 16.1 Message-key contract

Move new backend/user-visible copy toward:

```json
{
  "message_key": "health.medication.conflict.review",
  "params": {"count": 2},
  "severity": "attention",
  "action": {"key": "common.review", "href": "/health/medications/review"}
}
```

Web/mobile localize with the same semantic catalog.

### 16.2 Medical terminology layer

Maintain:

- canonical medical label;
- preferred consumer Vietnamese label;
- English label;
- aliases/search terms;
- explanation snippet where approved.

AI can generate draft explanations, but approved high-risk terminology should be curated/versioned.

---

## 17. Design system implementation

### 17.1 Shared token source

Use a platform-neutral JSON/YAML token source, generated into:

- CSS custom properties for web;
- Dart constants/ThemeExtensions for Flutter.

Example:

```json
{
  "color": {
    "brand.primary": "...",
    "surface.canvas": "...",
    "status.attention.bg": "...",
    "state.unconfirmed.text": "..."
  },
  "space": {"1": 4, "2": 8, "3": 12},
  "radius": {"sm": 8, "md": 12, "lg": 16}
}
```

Exact color values are a design task, not hard-coded in this architecture spec.

### 17.2 Consumer components

Build/test these before mass page migration:

- `HealthPageHeader`
- `AskBar`
- `PrimaryActionCard`
- `HealthStateBadge`
- `SourceBadge`
- `TimelineItem`
- `ResultValueCard`
- `MedicationCard`
- `ReviewCandidateCard`
- `UrgencyBanner`
- `EmptyState`
- `InlineError`
- `SyncStatus`
- `PermissionExplainer`
- `BottomSheet/Modal`
- `Skeleton` patterns

---

## 18. Care navigation technical boundary

Care navigation requires its own task contract and should not be a generic chat prompt.

Pipeline:

1. identify symptom/care-navigation intent;
2. deterministic emergency/red-flag precheck;
3. bounded question selection from approved set;
4. collect structured answers;
5. deterministic/validated acuity logic;
6. model may explain result in plain language;
7. enforce minimum urgency floor;
8. provide handoff summary.

Do not let the generative model directly output arbitrary “go to emergency / stay home” without the safety floor.

---

## 19. Labs/result explanation technical boundary

Input must include only:

- exact analyte/test name;
- value/unit;
- source reference range/flag;
- date/specimen metadata if available;
- a minimum necessary subset of relevant personal context if policy permits;
- approved external evidence if needed.

Verifier checks:

- copied numeric value unchanged;
- unit unchanged;
- reference range not invented;
- no diagnosis claim unless explicitly sourced and allowed (consumer task should generally avoid it);
- source citations valid.

---

## 20. Professional mode migration

Do not redesign Council/Scribe into consumer navigation.

### Council

Keep case/adjudication domain and safety contracts; rename consumer-facing professional label to something like “Hội chẩn chuyên môn” in Vietnamese. Integrate Ask and evidence in the case context rather than requiring clinicians to bounce through global navigation.

### Scribe

Preserve consent-before-microphone and draft-vs-signed distinction. Move toward a single flow:

```text
Consent -> Capture -> Draft note -> Review edits -> Clinician attestation -> Export/share
```

No “AI finalized” language.

---

## 21. Data migration strategy

Prefer additive migrations.

Potential additions:

- `model_runs` (PII-safe provenance metadata);
- `health_projection_conflicts` if current domain lacks a generic review queue;
- `connected_health_sources` / sync checkpoints;
- `derived_summaries` with input digest/revision IDs;
- `notification_preferences` normalized by category;
- bounded version columns/ETags for PHR subresources if not already available.

Avoid destructive migration until old clients/routes are retired.

---

## 22. Caching and invalidation

### API

- cache only derived read models, not authorization decisions;
- key by profile + state/policy version where relevant;
- invalidate from outbox/domain events;
- derived AI summaries carry source revision digest.

### Client

- query cache scoped by profile;
- clear/invalidate on profile switch, logout, grant revoke, consent change and accepted write;
- do not persist sensitive query cache to insecure browser storage.

---

## 23. Security threat model additions

### Unofficial model gateway

Threats:

- endpoint compromise;
- unexpected route/model change;
- logging by gateway;
- schema drift;
- inconsistent multimodal behavior;
- credential leakage.

Controls:

- server-only credentials;
- explicit allowlist;
- TLS;
- synthetic capability probes;
- route/version audit metadata;
- per-task disable switches;
- minimum-necessary context;
- no client-selected endpoint/model;
- documented gateway retention policy before production PHI use;
- shadow/canary promotion.

### Multimodal uploads

Threats:

- malware;
- decompression bombs/oversized PDFs;
- prompt injection;
- hidden text/layers;
- malicious filenames;
- cross-profile artifact ID probing;
- OCR-induced medication error.

Controls:

- MIME sniff + allowlist;
- bounded size/pages/resolution;
- malware scanner fail closed;
- sanitized filenames;
- opaque IDs;
- short-lived access tokens;
- content-as-data isolation;
- review before commit;
- exact source highlighting;
- deterministic critical-field validation.

---

## 24. Testing architecture

### Web

- Vitest/unit for view models and components;
- Playwright for core journeys;
- axe automated checks;
- visual regression at desktop/tablet/mobile;
- route/legacy redirect matrix;
- bundle budget.

### API

- contract tests for `/v2` endpoints;
- profile/RBAC/consent adversarial tests;
- PostgreSQL concurrency tests for bounded writes;
- GLHS read/commit TOCTOU tests;
- capture artifact security tests;
- integration tests for outbox invalidation.

### ML

Per-task evaluation bundles:

```text
evaluation/product_ai/<task>/
  README.md
  dataset_manifest.json
  cases.jsonl
  scorer.py
  locked_thresholds.json
  run.py
  reports/
```

Required benchmark dimensions:

- groundedness;
- stale-state use;
- temporal correctness;
- disclosure safety;
- extraction accuracy;
- structured-output validity;
- Vietnamese comprehension/terminology;
- emergency under/over-triage;
- prompt injection resistance;
- latency/cost.

### Gateway contract tests

Run synthetic tests against each configured provider alias in CI/deploy environments that have secrets, never in public PR logs with credentials/content.

---

## 25. Deployment and rollout architecture

Feature flags recommended:

```text
consumer_shell_v2
consumer_home_v2
consumer_health_v2
consumer_care_v2
consumer_ask_simple_composer
universal_capture_v2
model_gateway_v2
model_route_gemini_fast
model_route_gemini_quality
health_connect_sync
health_connect_medical_records_experimental
phr_bounded_writes_v2
care_navigation_v1
```

Rollout order:

1. internal synthetic/test accounts;
2. staff/dogfood;
3. 5% eligible consumer traffic;
4. 25%;
5. 50%;
6. 100% only after gates.

Model route rollout is independent of UI rollout. A UI can ship using existing approved model routes, then new Gemini aliases can be promoted per task after evaluation.

---

## 26. Observability dashboards

Create dashboards for:

### Product

- route/action completion;
- Home errors;
- capture funnel;
- Ask latency/error;
- connected sync success;
- share/revoke flow errors.

### Safety

- emergency floor triggers;
- medication safety blocks;
- stale proposal rejects;
- consent/policy rejects;
- cross-profile test alarms;
- unconfirmed candidate commit attempts.

### Model

- route availability/probe result;
- p50/p95 latency;
- schema invalid rate;
- fallback/abstention rate;
- verifier failure rate;
- task-level eval version in production;
- gateway alias/version drift.

No dashboard should display raw PHI by default.

---

## 27. Key architectural decisions

### ADR-A — Product IA over module IA
Keep domain modules internally; expose consumer jobs externally.

### ADR-B — Presentation convergence, not database collapse
A unified Health UI is a projection across current domain models with provenance.

### ADR-C — Task policy is independent of provider
ModelTask/task contracts remain the stable safety boundary; provider aliases are deployment implementation.

### ADR-D — Review-first multimodal writes
Every AI-extracted consequential fact is a proposal until accepted/authorized.

### ADR-E — Deterministic safety floor
Emergency routing and authoritative medication interaction checks cannot be downgraded by generative text.

### ADR-F — Bounded writes with optimistic concurrency
Replace whole-record UI writes with resource/command updates and GLHS/base-version checks.

### ADR-G — Connected health is provenance-rich input
Wearable/Health Connect data is a source, not automatically clinical truth.

### ADR-H — No raw AI configuration for consumers
Consumers express intent; internal routing selects approved route/tool based on task risk and capabilities.

---

## 28. Definition of technically complete

The rebuild is technically complete only when:

- new consumer route groups are canonical;
- legacy routes redirect safely;
- AppShell monolith is no longer the central controller for all authenticated experiences;
- Home uses a bounded read model;
- Health renders a source/state-aware unified projection;
- PHR consumer edits use bounded optimistic-concurrency writes;
- Ask consumer composer has no internal mode controls;
- multimodal upload -> extraction -> review -> GLHS-bound commit works end to end;
- provider-neutral model gateway supports existing approved route(s) and private Gemini aliases behind flags;
- capability probing/evaluation/rollback exists;
- Health Connect connector has permission-aware sync for approved P1 data types;
- role/profile/consent/accessibility/security/model evaluation gates are green;
- production can disable any new AI route without losing access to core health data.


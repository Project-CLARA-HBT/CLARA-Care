# CLARA Care Product Rebuild — Requirements

**Status:** normative requirements  
**Date:** 2026-08-19  
**Applies to:** web, mobile, API, ML/AI services, interoperability, content system, analytics and rollout  
**Normative words:** MUST / MUST NOT / SHOULD / MAY have RFC-style intent.  
**Priorities:** P0 = rebuild release gate; P1 = near-term follow-on; P2 = optional/later.  
**Safety rule:** any requirement that conflicts with server-side authorization, consent, GLHS, audit, provenance or medication safety is invalid; safety controls remain authoritative.

---

## 1. Product-level requirements

### PRD-001 — One-product mental model — P0
The consumer product MUST present CLARA as one health companion rather than a suite of independent named modules.

**Acceptance:** an ordinary-user usability participant can find Ask, medications, results, health history, visits and privacy without knowing internal feature names.

### PRD-002 — Top-level consumer IA — P0
Authenticated ordinary-user navigation MUST contain no more than Home, Health, Care, You and one persistent Ask CLARA action.

### PRD-003 — Professional separation — P0
Clinical, research and administrative tools MUST NOT appear in ordinary consumer navigation merely because the account has a privileged role. A deliberate professional-mode transition MUST separate work context from personal context.

### PRD-004 — Preserve direct links — P0
Simplifying navigation MUST NOT remove authorized deep-link access to supported legacy or professional routes during migration.

### PRD-005 — No fabricated activity — P0
The UI MUST NOT generate synthetic tasks, results, alerts, measurements, trends or recent activity to avoid empty states.

### PRD-006 — Progressive disclosure — P0
Every primary consumer surface MUST place the main message and primary action before technical detail, history, configuration or provenance detail.

### PRD-007 — Actionable empty states — P0
Empty states MUST explain what the user can do next and MUST NOT imply health reassurance from absence of data.

### PRD-008 — Consumer terminology — P0
Internal architecture terms such as RAG, pipeline, model tier, THSS, GLHS, commit, candidate and confidence score MUST NOT appear as unexplained primary consumer copy.

### PRD-009 — Vietnamese-first parity — P0
All P0 consumer flows MUST have complete Vietnamese and English copy. New user-facing strings MUST use message/catalog keys rather than inline language branching where practical.

### PRD-010 — No dark-pattern health engagement — P0
The product MUST NOT use shame, fear, arbitrary streak loss, escalating notification pressure or vulnerability-based manipulation to increase engagement.

---

## 2. Home requirements

### HOME-001 — Daily answer — P0
Home MUST answer “what matters now?” with a single prioritized next action when one exists.

### HOME-002 — Global Ask entry — P0
Home MUST expose Ask CLARA above secondary feature discovery and support text plus visible attachment/voice/camera affordances based on platform capability.

### HOME-003 — Recent changes — P0
Home MUST provide a “new/changed” region backed by real source data: results, documents, medication changes, confirmed timeline updates or connected measurements.

### HOME-004 — Today schedule — P0
Home MUST surface due medications/reminders, visits and accepted care tasks without requiring users to open separate modules.

### HOME-005 — Alert ordering — P0
Critical safety alerts MUST outrank engagement, tips, summaries and low-priority tasks.

### HOME-006 — No generic wellness filler — P0
Home MUST NOT use generic wellness tips as primary content merely to fill the page. Educational content MAY appear contextually when sourced and relevant.

### HOME-007 — Profile clarity — P0
When family/profile context can change, Home MUST clearly show the active person and prevent accidental mixing of profiles.

### HOME-008 — Loading/error integrity — P0
Home errors MUST distinguish “data unavailable” from “no problem detected”. Failed requests MUST NOT become reassuring empty states.

### HOME-009 — Personalization source — P1
Home SHOULD explain why a personalized card appeared when the reason is non-obvious.

### HOME-010 — Notification handoff — P1
Tapping a notification MUST deep-link to the exact item/action that generated it and retain profile context safely.

---

## 3. Ask CLARA requirements

### ASK-001 — Simple consumer composer — P0
The ordinary-user composer MUST expose text, send, and supported camera/file/voice controls; it MUST NOT expose Fast/Deep/Research or retrieval-stack configuration as normal controls.

### ASK-002 — Intent routing — P0
The backend MUST route requests by bounded task intent and risk contract rather than requiring the user to choose a model or execution mode.

### ASK-003 — Personal-context consent — P0
Use of personal health context MUST be governed by server-authoritative task/purpose/consent policy. UI hints or toggles MUST NOT override policy.

### ASK-004 — Context disclosure — P0
For personal answers, the UI MUST provide a discoverable summary of the data classes/sources actually used.

### ASK-005 — Main-message-first answer — P0
A consumer answer MUST lead with the main answer, followed by actions, sources, unknowns/uncertainty and escalation guidance when relevant.

### ASK-006 — Grounded personal claims — P0
Any factual claim about the user's record MUST trace to exact authorized record/source identifiers and effective time.

### ASK-007 — External citations — P0
External evidence claims that require sourcing MUST link to the retrieved source identifiers actually used; fabricated citations are a release blocker.

### ASK-008 — Unsupported claim handling — P0
Unsupported material claims MUST be removed, qualified, or cause an abstention according to task contract.

### ASK-009 — Unknowns — P0
The answer MUST distinguish unavailable/missing user information from negative findings.

### ASK-010 — No hidden-reasoning display — P0
Raw chain-of-thought, provider diagnostics and hidden system prompts MUST NOT be shown to users.

### ASK-011 — Cancellation — P0
Streaming/generation MUST be cancellable without losing the user's submitted prompt or attached source metadata.

### ASK-012 — Retry provenance — P0
If a request is retried, the system MUST retain truthful provenance for each attempted route and MUST NOT report a model/provider that did not produce the displayed answer.

### ASK-013 — Personal write proposal — P0
When an answer identifies record-worthy information, it MAY create reviewable proposals but MUST NOT directly create confirmed health truth.

### ASK-014 — Ask a period/item — P0
Users MUST be able to invoke Ask CLARA from a timeline period, result, medication, document or visit with scope clearly visible.

### ASK-015 — Explain simpler — P1
Users SHOULD be able to request a simpler explanation without changing the underlying sourced facts.

### ASK-016 — Professional detail — P1
Authorized professional users MAY switch answer presentation to professional detail, but consumer users MUST NOT be forced to understand the mode system.

### ASK-017 — Conversation history — P0
Conversation history MUST identify whether a turn used personal context and MUST invalidate/recompute cached personal derivatives when governance policy requires it.

### ASK-018 — Search/history privacy — P0
Conversation search MUST be profile-scoped and MUST NOT leak text/snippets from revoked or inaccessible contexts.

### ASK-019 — Emergency path — P0
Emergency/red-flag classification MUST have a deterministic or independently validated safety floor that an LLM cannot downgrade.

### ASK-020 — Safe outage — P0
If LLM service is unavailable, users MUST retain access to their record and deterministic safety functions; the UI MUST state that AI explanation is temporarily unavailable.

---

## 4. Multimodal capture requirements

### CAP-001 — Unified entry — P0
Users MUST be able to add health information from text, camera/image, PDF/document, voice/audio and manual entry from one coherent “Add health information” flow.

### CAP-002 — Source preservation — P0
Every derived candidate MUST preserve the source artifact identifier, checksum, modality and source span/page/region where available.

### CAP-003 — Secure upload boundary — P0
Uploads MUST enforce allowlisted MIME/type detection, size/page limits, malware scanning or explicit fail-closed behavior, encrypted storage and bounded access URLs/tokens.

### CAP-004 — Prompt-injection isolation — P0
Text inside uploaded documents/images MUST be treated as untrusted data, not executable instructions. Document content MUST NOT override system/task policies.

### CAP-005 — Schema-bound extraction — P0
Model extraction MUST return a versioned typed schema. Invalid or partial payloads MUST NOT be coerced into record commits.

### CAP-006 — Review before commit — P0
AI-extracted health information MUST enter a review state. The user MUST be able to accept, edit or reject each consequential candidate.

### CAP-007 — Exact evidence highlight — P1
For image/PDF extraction, the UI SHOULD highlight the source page/region/span corresponding to each candidate.

### CAP-008 — OCR/VLM disagreement — P0
When OCR and multimodal model outputs materially disagree, the UI MUST flag uncertainty rather than silently choosing a value.

### CAP-009 — Medication identity — P0
Medication identity, strength, route or dosing extracted from labels MUST require confirmation unless an independently validated, policy-approved source allows otherwise.

### CAP-010 — No medical-image diagnosis — P0
Uploaded diagnostic images (radiology, pathology, etc.) MUST NOT be interpreted diagnostically under this release scope. The product MAY extract visible text/metadata and direct users to professional interpretation.

### CAP-011 — Audio transcript review — P0
Voice health logging MUST provide reviewable transcript/extracted facts; ASR uncertainty MUST not silently become confirmed truth.

### CAP-012 — User draft durability — P0
Failure of OCR/VLM/ASR MUST NOT delete the original user-entered text, image/document reference or local draft.

### CAP-013 — Duplicate detection — P1
Capture SHOULD detect probable duplicate documents/events and offer merge/link/reject review without automatically destroying either source.

### CAP-014 — Import privacy — P0
Artifacts MUST inherit the same profile/purpose access controls as the derived health information.

### CAP-015 — Artifact retention — P0
Retention/deletion policies MUST be explicit and auditable; deleting a source MUST define what happens to derived facts and provenance according to policy.

---

## 5. Health record requirements

### HEALTH-001 — Unified consumer projection — P0
The UI MUST provide one Health area that projects PHR, LifeMap, medications, results, measurements, visits and documents without falsely merging their backend semantics.

### HEALTH-002 — State badge — P0
Record items MUST visibly distinguish confirmed, user-reported, imported, device-sourced, document-extracted/unconfirmed, stopped/resolved and conflicting states where relevant.

### HEALTH-003 — Source detail — P0
Users MUST be able to inspect source and effective/recorded time for consequential facts.

### HEALTH-004 — Correction history — P0
Corrected facts MUST retain history/provenance. Default UI MAY show only current state but MUST allow history inspection.

### HEALTH-005 — Timeline filters — P0
Timeline MUST support at least medication, symptom/condition, visit, result, measurement and document filters.

### HEALTH-006 — Timeline time navigation — P0
Timeline MUST support recent and broader date ranges without loading the full record into the browser at once.

### HEALTH-007 — Episode grouping — P1
The UI SHOULD group related longitudinal events into episodes while allowing the user to inspect underlying events and sources.

### HEALTH-008 — Current-state distinction — P0
The UI MUST distinguish “current” from “historical” and MUST NOT infer current medication/condition status merely from the most recent free-text mention.

### HEALTH-009 — Conflict surface — P0
When sources disagree on a consequential current fact, the UI MUST surface a review state rather than silently suppressing one source.

### HEALTH-010 — Search — P1
Users SHOULD have natural-language and structured search over their authorized record.

### HEALTH-011 — No whole-record overwrite — P0
Consumer section edits MUST NOT require whole-record blind PUT semantics. New write APIs MUST use bounded commands or PATCH with version/ETag preconditions.

### HEALTH-012 — Conflict recovery — P0
On write conflict, the UI MUST preserve the user's edit and show a human-readable reconciliation flow.

### HEALTH-013 — Export — P0
Users MUST be able to export supported health data in a human-readable format; FHIR export SHOULD be available where current backend contracts support it.

### HEALTH-014 — Delete/correct — P0
Users MUST have discoverable correction/deletion/data-rights workflows consistent with retention and audit requirements.

---

## 6. Medication requirements

### MED-001 — One consumer medication hub — P0
Consumers MUST see one Medication area even if backend sources include PHR entries, medication courses and scanned cabinet items.

### MED-002 — Provenance-preserving reconciliation — P0
The hub MUST NOT represent scanned/unconfirmed items as active medications unless confirmed by policy/user/source.

### MED-003 — Current schedule — P0
Current medication cards SHOULD show normalized name, user-understandable dose/schedule, status, source and next reminder where available.

### MED-004 — Interaction check — P0
Interaction checking MUST remain fail-closed according to existing medication safety policy and MUST identify the source/version of interaction knowledge internally.

### MED-005 — Allergy context — P0
Medication safety MUST use confirmed/allowed allergy context according to task policy and clearly state when allergy information is unknown or incomplete.

### MED-006 — Duplicate therapy review — P1
Potential duplicates SHOULD be surfaced as “needs review”, not as a definitive prescribing judgment.

### MED-007 — Camera add — P0
Users MUST be able to add a medicine by camera/image through the unified capture flow.

### MED-008 — Reminder controls — P1
Medication reminders SHOULD support time, recurrence, snooze, pause and per-medication enable/disable.

### MED-009 — Refill/expiry — P1
The product SHOULD support refill/expiry reminders only when an actual date/quantity source exists; it MUST NOT invent estimates silently.

### MED-010 — Stop/change history — P0
Starting, stopping and changing medication MUST create longitudinal state changes rather than destructive replacement.

---

## 7. Lab/result requirements

### LAB-001 — Result basics first — P0
Result detail MUST show value, unit, lab-provided reference range when present, date/time and source before AI explanation.

### LAB-002 — No invented reference range — P0
CLARA MUST NOT generate a “normal range” when the authoritative result lacks one, unless a separately cited external range is explicitly labeled as external and clinically appropriate.

### LAB-003 — Trend comparability — P0
Trend charts MUST only combine values that are meaningfully comparable in analyte/unit/method context or clearly flag conversions/limitations.

### LAB-004 — Plain explanation — P0
AI explanation MUST state what the test generally measures, what the observed value means in source context, and what remains unknown; it MUST NOT convert a result into a diagnosis.

### LAB-005 — Abnormal flag caution — P0
Out-of-range flags MUST be described as reasons for interpretation/review, not proof of disease.

### LAB-006 — Ask clinician questions — P1
Result detail SHOULD offer questions the user may discuss with a clinician, grounded to confirmed data.

---

## 8. Care/visit requirements

### CARE-001 — Unified care area — P0
Care MUST consolidate upcoming visits, preparation, after-visit actions, symptom/care navigation and family/caregiver coordination.

### CARE-002 — Visit preparation — P0
Users MUST be able to generate a visit-prep summary from authorized confirmed/current data plus user-selected goals/questions.

### CARE-003 — Summary provenance — P0
Visit-prep summaries MUST preserve input revision/source IDs and invalidate or mark stale when source facts change.

### CARE-004 — User goals — P0
The user MUST be able to add/edit “what I want to ask/discuss” independently of AI suggestions.

### CARE-005 — After-visit extraction — P1
Uploaded visit documents/notes MAY produce reviewable medication changes, follow-up tasks and instructions.

### CARE-006 — No invented appointments — P0
Visit screens MUST not display inferred appointment dates/times without an actual source.

### CARE-007 — Care navigation outcome — P0
Symptom/care navigation MUST primarily return an urgency/care-setting recommendation and next action, not a ranked disease list.

### CARE-008 — Emergency floor — P0
Red-flag/emergency outcomes MUST not be downgraded by generative wording or model uncertainty.

### CARE-009 — Explain recommendation — P0
Care navigation MUST state the key user-provided facts that drove urgency in plain language.

### CARE-010 — Handoff summary — P1
Users SHOULD be able to generate a concise handoff summary for a clinician without exposing hidden AI reasoning.

### CARE-011 — Location/service routing — P2
If local care-directory integrations are added, recommendations MUST distinguish availability/location facts from clinical urgency logic.

---

## 9. Family/caregiver requirements

### FAMILY-001 — Granular grants — P0
Sharing MUST be scoped by person/profile, data class, purpose, recipient and duration where the backend supports those dimensions.

### FAMILY-002 — Preview — P0
Before granting access, users MUST see a plain-language preview of categories to be shared.

### FAMILY-003 — Revocation — P0
Revocation MUST take effect server-side and invalidate derived/cache access according to policy.

### FAMILY-004 — Access log — P1
Users SHOULD be able to see who accessed shared information and when if audit semantics support it.

### FAMILY-005 — Caregiver digest — P1
AI caregiver summaries MUST be generated only after authorization filtering; the model MUST never receive withheld categories.

### FAMILY-006 — Profile boundary — P0
Semantic retrieval MUST NOT cross family profiles unless explicit authorized scope includes that profile.

---

## 10. Onboarding requirements

### ONB-001 — Goal-first onboarding — P0
Onboarding MUST begin with what the user wants help with, not a long medical form.

### ONB-002 — Skippable — P0
Non-essential onboarding fields MUST be skippable.

### ONB-003 — Progressive profile — P0
CLARA SHOULD ask for missing information when it becomes relevant to a task, with “why we ask” context.

### ONB-004 — First value event — P0
A new user MUST be able to ask a general health question or scan/explain a document before completing full profile setup.

### ONB-005 — Permission timing — P0
Camera, microphone, notification and connected-health permissions MUST be requested in context, not all at first launch.

### ONB-006 — Important information — P1
Users SHOULD be invited to add medications, allergies and emergency information with explicit optionality and state labels.

---

## 11. Connected health and interoperability requirements

### INT-001 — Canonical ingestion envelope — P0
All external health data sources MUST enter through a canonical ingestion envelope that preserves subject/profile, source, source record ID, observed/effective time, ingestion time, units, provenance and version.

### INT-002 — Android Health Connect — P1
The Android app SHOULD support Health Connect for selected activity, sleep, vitals and body measurement types after explicit per-category permission.

### INT-003 — Health Connect permission recheck — P1
The app MUST re-evaluate Health Connect permissions before relevant synchronization because users can revoke access independently.

### INT-004 — Health Connect pause — P1
Users SHOULD have a CLARA-side sync on/off control plus a path to system Health Connect permission management.

### INT-005 — Health Connect PHR experimental gate — P1
FHIR Medical Records support in Health Connect MUST remain feature-gated while the Android API/Play policy is experimental/evolving and MUST check feature availability at runtime.

### INT-006 — FHIR versions — P0
FHIR import/export MUST validate declared version/profile/structure and MUST reject cross-subject or unsupported resources rather than partially ingest them invisibly.

### INT-007 — Source separation — P0
Records from different provider/device sources MUST retain source identity even when normalized to a common display concept.

### INT-008 — Apple Health/HealthKit adapter — P2
An iOS implementation SHOULD use the same canonical ingestion and provenance contract if/when iOS delivery is added.

### INT-009 — Device-derived interpretation — P1
AI may explain deterministic trends from connected data but MUST distinguish device measurement from clinical diagnosis.

### INT-010 — Missingness/device change — P1
Trend analysis SHOULD detect material missingness/source-device changes and qualify interpretations accordingly.

---

## 12. AI/model-platform requirements

### AI-001 — Task-first routing — P0
The model platform MUST separate task contracts from provider/model transport.

### AI-002 — Provider-neutral gateway — P0
`services/ml` MUST expose provider-neutral route resolution with adapter interfaces; medical request code MUST not instantiate arbitrary provider clients directly.

### AI-003 — User-provided aliases — P0
`gemini-3.6-flash-high` and `gemini-3.7-tiered` MUST be treated as deployment aliases from an unofficial/private gateway, not hard-coded official model identities.

### AI-004 — Capability declaration — P0
Each route MUST declare capabilities such as text, image, PDF/document, structured output, tool calling and context limits where known.

### AI-005 — Capability probe — P0
Unofficial gateway routes MUST be capability-probed during deployment/health checks. A failed capability MUST disable affected tasks or invoke an explicitly approved safe fallback.

### AI-006 — No request-owned model — P0
Client requests MUST NOT choose arbitrary provider/model aliases for medical tasks.

### AI-007 — Task contract — P0
Every generative/extraction task MUST declare risk level, allowed capability tiers, prompt contract/version, output schema/version, timeout, safety fallback, required tools and review policy.

### AI-008 — High-risk no silent fallback — P0
For medium/high/critical tasks, provider/model fallback MUST be explicit in task policy and provenance; silent fallback to a different behavior is forbidden.

### AI-009 — Structured validation — P0
Structured outputs MUST be schema validated before downstream use.

### AI-010 — Grounding — P0
Tasks making personal-state claims MUST receive a bounded governed context, not unrestricted database retrieval or full-history dumping.

### AI-011 — THSS/GLHS binding — P0
Any persistent proposal derived from AI-consumed health state MUST carry the exact governed snapshot/base-state binding required by GLHS and be rejected when authorization/consent/state policy no longer permits commit.

### AI-012 — Provenance — P0
AI run provenance MUST include task ID, route/provider class, deployment alias, model/gateway version if available, prompt version, contract/schema version, tool versions, governed context digest/version and safety outcome without logging raw PII to analytics.

### AI-013 — Raw PII telemetry prohibition — P0
Product analytics/operational telemetry MUST NOT log raw prompts, clinical document text, record values or model responses by default.

### AI-014 — Benchmark before promotion — P0
A new unofficial model route MUST pass task-specific locked evaluations before becoming authoritative for any P0 task.

### AI-015 — Shadow/canary — P0
Medium/high-risk new routes MUST support shadow and canary stages before full promotion.

### AI-016 — Deterministic fallback — P0
Where a deterministic fallback exists, it MUST be truthful about reduced capability and MUST preserve user access to source data.

### AI-017 — Cost/latency budget — P1
Each task contract SHOULD define p95 latency and maximum expected token/media cost budgets; routing MAY optimize within safety-equivalent approved routes.

### AI-018 — Prompt injection — P0
Retrieved/uploaded content MUST be data-isolated; external text MUST NOT modify authorization, tool permissions, system instructions or output contract.

### AI-019 — Tool allowlist — P0
Tool use MUST be allowlisted per task and server-authorized independently of model output.

### AI-020 — No autonomous treatment action — P0
Models MUST NOT prescribe, change medication, book urgent treatment or commit health truth autonomously under the consumer release scope.

### AI-021 — Abstention — P0
Tasks MUST define when the system must abstain because of insufficient data, conflicting sources, unsupported modality, unavailable evidence or unsafe ambiguity.

### AI-022 — Version pinning — P0
Unofficial route aliases SHOULD resolve to deployment-pinned gateway versions when possible; unexpected model behavior/version change MUST trigger evaluation/rollback controls.

### AI-023 — Quality comparison — P0
The initial Gemini aliases MUST be compared against the currently approved route(s) per task; “newer” or “larger” is not sufficient evidence for promotion.

### AI-024 — Multimodal privacy — P0
Image/PDF/audio tasks MUST apply the same minimum-necessary context policy as text tasks and MUST NOT attach unrelated record history merely because the model supports large multimodal context.

### AI-025 — No diagnostic image vision — P0
The vision route contract MUST explicitly prohibit diagnostic interpretation of radiology/pathology/dermatology images unless a separate validated intended-use program is approved.

---

## 13. Copy, health literacy and localization requirements

### COPY-001 — Main message — P0
Consequential health content MUST identify one main message before supporting details.

### COPY-002 — Clear action — P0
When action is needed, copy MUST state what the user should do next and when.

### COPY-003 — Familiar language — P0
Consumer copy MUST prefer familiar Vietnamese/English wording over technical medical/system jargon.

### COPY-004 — Term expansion — P0
Necessary medical terms SHOULD be explained inline on first use.

### COPY-005 — Uncertainty wording — P0
Uncertainty MUST be described in words tied to missing/conflicting evidence; arbitrary LLM “confidence %” MUST NOT be presented as medical certainty.

### COPY-006 — Risk numbers — P0
When risk numbers are shown, the source, denominator/time horizon and interpretation MUST be clear. Natural-frequency formats SHOULD be preferred where suitable.

### COPY-007 — No false reassurance — P0
“Nothing found” or “no data” MUST NOT be worded as “everything is normal”.

### COPY-008 — Status vocabulary — P0
The product MUST define a controlled vocabulary for confirmed, reported, extracted, imported, device-sourced, conflicting, stale and unknown states.

### COPY-009 — Backend copy contract — P1
User-facing backend messages SHOULD migrate from raw Vietnamese strings to message key + typed parameters + severity/action metadata.

### COPY-010 — CCI gate — P1
High-traffic patient-facing safety/education pages SHOULD score >=90 on the CDC Clear Communication Index using an internal review workflow.

### COPY-011 — Bilingual semantic parity — P0
Translations MUST preserve risk/action semantics; translation MUST NOT soften or strengthen urgency.

### COPY-012 — Error wording — P0
Errors MUST state what failed, what remains safe/available and what the user can do next without exposing stack/provider details.

---

## 14. Accessibility requirements

### A11Y-001 — WCAG — P0
Web consumer P0 flows MUST meet WCAG 2.2 AA.

### A11Y-002 — Touch targets — P0
Primary interactive controls SHOULD be at least 44x44 CSS px on touch layouts unless an equivalent spacing solution safely exceeds WCAG minimum target requirements.

### A11Y-003 — Keyboard — P0
All web functions MUST be usable by keyboard, including dialogs, attachment review, timeline filters and sharing flows.

### A11Y-004 — Focus — P0
Focus MUST be visible, restored after modal/overlay close and never obscured by sticky UI.

### A11Y-005 — Charts — P0
Health charts MUST provide textual equivalents/summaries and accessible labels for data points or meaningful aggregated descriptions.

### A11Y-006 — Color independence — P0
Urgency, confirmation and conflict MUST NOT rely on color alone.

### A11Y-007 — Zoom/text scaling — P0
Web MUST remain functional at 200% zoom; Flutter layouts MUST support platform text scaling without clipping essential actions.

### A11Y-008 — Reduced motion — P0
Non-essential motion MUST honor reduced-motion preferences.

### A11Y-009 — Audio alternatives — P0
Audio capture/status MUST have visual alternatives; generated audio features, if any, MUST have text equivalents.

### A11Y-010 — Authentication — P0
Authentication MUST permit password managers/paste and SHOULD support accessible passwordless/passkey options when infrastructure permits.

---

## 15. Design-system requirements

### DS-001 — Semantic tokens — P0
Web and mobile MUST derive from a documented semantic token set for color, typography, spacing, radius, elevation, focus, motion and health-state statuses.

### DS-002 — No neon/cyber default — P0
Consumer UI MUST NOT use cyber-grid, terminal, neon-glow or “AI engine” visual metaphors as the default brand language.

### DS-003 — Status color reservation — P0
Red/orange/green MUST be reserved for meaningful status, not decoration.

### DS-004 — Component primitives — P0
Button, input, field, card/surface, modal/sheet, tabs, status badge, source badge, list row, empty state, loading state and error state MUST be shared primitives rather than page-specific copies.

### DS-005 — One primary action — P0
Each major card/surface SHOULD expose one visually dominant next action.

### DS-006 — Responsive parity — P0
Web layouts MUST have defined desktop/tablet/mobile behavior; information priority MUST remain the same even when visual arrangement changes.

### DS-007 — Dark mode — P1
Dark mode MAY remain supported but MUST meet the same contrast/status semantics and MUST NOT be the defining health-product aesthetic.

---

## 16. Frontend architecture requirements

### FE-001 — Shell decomposition — P0
`AppShell` responsibilities MUST be decomposed into auth/session boundary, profile context, navigation presentation, preferences and route layouts rather than one monolithic client controller.

### FE-002 — Server-state library — P0
Remote health/server state SHOULD be managed through a consistent query/cache layer rather than ad hoc duplicated `useEffect/useState` fetch orchestration.

### FE-003 — UI-state isolation — P0
Local presentation state MUST remain distinct from server-authoritative health state.

### FE-004 — Route groups — P0
Next.js routes SHOULD be organized by public, consumer, professional and admin layout boundaries to reduce accidental shell mixing.

### FE-005 — Authorization independence — P0
Navigation visibility MUST remain separate from server/API authorization. Hiding a link MUST never be treated as access control.

### FE-006 — Typed API client — P0
New P0 endpoints MUST have typed request/response contracts and defensive validation at trust boundaries.

### FE-007 — Error boundary — P0
Major route groups MUST have user-safe loading/error boundaries that do not leak provider/backend diagnostics.

### FE-008 — URL-addressable state — P1
Meaningful filters/selected record/visit context SHOULD be URL-addressable where safe, enabling refresh/deep link without exposing PHI in query strings.

### FE-009 — No PHI URL leakage — P0
PHI/medical free text MUST NOT be placed in URLs, analytics route labels or public share identifiers.

### FE-010 — Bundle budgets — P0
The existing bundle budget check MUST remain and be updated for the new baseline; multimodal libraries MUST be lazy loaded where feasible.

### FE-011 — Consumer/pro shell split — P0
Professional telemetry/settings MUST not be loaded into ordinary consumer routes unless needed.

### FE-012 — Mobile parity contract — P0
Critical domain behavior MUST be shared through API contracts and product requirements, not reimplemented with divergent safety rules in Flutter.

---

## 17. API/data requirements

### API-001 — Home read model — P0
Create a profile-scoped `/v2/home` read model or equivalent that returns prioritized actions, recent changes, schedule items, alerts and sync state without requiring many client fan-out requests.

### API-002 — Pagination — P0
Timeline/results/documents/conversations MUST support stable pagination/cursors.

### API-003 — Bounded writes — P0
Health record updates MUST use bounded resource/command endpoints; whole-record replacement MUST be retired for new consumer editing.

### API-004 — Optimistic concurrency — P0
Writable health resources MUST support explicit base version/ETag/state token so concurrent edits cannot silently overwrite unrelated changes.

### API-005 — Idempotency — P0
Create/commit commands that can be retried MUST support idempotency keys/command IDs.

### API-006 — Profile scoping — P0
Every health endpoint MUST resolve profile scope server-side; client profile IDs are requests, not authorization proof.

### API-007 — Purpose — P0
Sensitive data access MUST carry/enforce purpose where governance policy requires it.

### API-008 — Provenance projection — P0
Read models MUST provide enough provenance/state metadata for the UI to label source and confirmation state accurately.

### API-009 — Message metadata — P1
Backend alerts/tasks SHOULD include message key, typed params, severity, action target and provenance instead of only raw localized prose.

### API-010 — Cache invalidation — P0
Longitudinal writes MUST emit/outbox events sufficient to invalidate Home, timeline summaries, AI-derived summaries and relevant caches.

### API-011 — Derived-view staleness — P0
Derived summaries MUST carry input version/revision sets or a digest so clients can show/recompute stale content.

### API-012 — Public share scope — P0
Public/shared links MUST retain narrow capability scopes, expiry/revocation and audit semantics and MUST not widen during route migration.

---

## 18. Security/privacy requirements

### SEC-001 — Minimum necessary — P0
AI/task context MUST include only data necessary for the declared task/purpose.

### SEC-002 — Consent before capture — P0
Microphone/camera/connected-health access MUST require appropriate user action and platform permission; hidden background capture is forbidden.

### SEC-003 — Secrets — P0
Unofficial Gemini/API credentials MUST remain server-side; they MUST never ship in web/mobile bundles.

### SEC-004 — Gateway allowlist — P0
Private model gateway URLs MUST be deployment allowlisted and validated; request input MUST not provide arbitrary endpoints.

### SEC-005 — Transport — P0
Sensitive data MUST use authenticated encrypted transport; public share paths MUST never expose raw sequential record IDs.

### SEC-006 — Artifact access — P0
Uploaded artifact access URLs/tokens MUST be short-lived, profile-bound and non-guessable.

### SEC-007 — Audit — P0
Sensitive reads/writes/shares/AI persistent proposals MUST produce the existing required audit evidence without logging excessive content.

### SEC-008 — Session/device management — P1
Users SHOULD be able to view and revoke active sessions/devices.

### SEC-009 — AI privacy control — P0
Privacy settings MUST explain which AI uses can be disabled and what functionality is lost; turning off optional AI MUST not block access to stored records.

### SEC-010 — Prompt injection tests — P0
CI/release evaluation MUST include malicious uploaded/retrieved instructions attempting to exfiltrate data, change tools or cross profiles.

### SEC-011 — Cross-profile isolation — P0
Cross-profile leakage in retrieval, cache, summaries or AI context is a release blocker.

### SEC-012 — Revocation TOCTOU — P0
Authorization/consent changes between AI read and persistent commit MUST be rechecked atomically according to GLHS policy.

---

## 19. Performance/reliability requirements

### PERF-001 — Core Web Vitals — P0
Production target at p75: LCP <=2.5s, INP <=200ms, CLS <=0.1 for primary consumer routes, measured on representative supported devices/networks.

### PERF-002 — Home API — P0
Home read-model p95 server latency target SHOULD be <=500ms excluding cold external integrations; slow optional integrations MUST not block core Home response.

### PERF-003 — Ask perceived latency — P0
Ask MUST show immediate submission state and meaningful streaming/progress without exposing fake “analysis” stages.

### PERF-004 — Upload progress — P0
Large document upload MUST show progress and allow cancellation/retry.

### PERF-005 — AI timeout — P0
Every AI task MUST have a bounded timeout and user-safe failure mode.

### PERF-006 — Circuit isolation — P0
Failure of the unofficial Gemini gateway MUST not cascade into auth, record browsing, deterministic medication safety or core care tasks.

### PERF-007 — Offline critical info — P1
Mobile SHOULD support secure device-local access to an explicitly selected emergency card/critical summary when offline, with clear last-updated state.

### PERF-008 — Sync recovery — P1
Connected-health sync MUST be resumable/idempotent and surface last successful sync plus errors without duplicating records.

---

## 20. Analytics and experimentation requirements

### ANA-001 — Consent/no-PII — P0
Product analytics MUST preserve existing consent/no-PII principles.

### ANA-002 — Event taxonomy — P0
Track coarse events for Home action selection, Ask modality, capture review outcome, visit prep completion, connected-source setup, sharing flow completion and errors; do not include health text/value payloads.

### ANA-003 — Funnel metrics — P0
Define funnels for first value, document-to-confirmed-record, question-to-useful-answer, visit preparation and medication add/review.

### ANA-004 — Safety metrics separate — P0
Safety outcomes MUST be measured separately from engagement. A higher click rate MUST never justify lower safety thresholds.

### ANA-005 — Experiment exclusions — P0
High-risk emergency/safety wording, access control and medication safety MUST NOT be A/B optimized for engagement without explicit clinical/safety review.

### ANA-006 — Feature flags — P0
All major rebuild surfaces and new model routes MUST be independently flaggable for rollback/canary.

---

## 21. Testing/evaluation requirements

### TEST-001 — Unit/contract tests — P0
New components, route contracts, API schemas and task contracts MUST have unit/contract tests.

### TEST-002 — Consumer E2E — P0
E2E MUST cover ordinary-user Home -> Ask, Home -> medication, scan/upload -> review -> save, Health -> result explanation, Care -> visit prep, sharing/revocation and error states.

### TEST-003 — Role E2E — P0
E2E MUST verify consumer/professional/admin mode separation and authorization behavior.

### TEST-004 — Accessibility automation — P0
Automated axe/accessibility smoke MUST cover all top-level consumer routes at desktop and mobile viewports, supplemented by keyboard/manual tests.

### TEST-005 — Visual regression — P0
Critical responsive surfaces MUST have stable visual regression baselines with synthetic/no-PII fixtures.

### TEST-006 — Model locked sets — P0
Each AI task MUST have a frozen evaluation set and versioned scoring code before route promotion.

### TEST-007 — Vietnamese evaluation — P0
AI/copy evaluation MUST include Vietnamese colloquial phrasing, typos, medication names, negation, temporal expressions and health-literacy variants.

### TEST-008 — Multimodal evaluation — P0
Document/image evaluation MUST include blur, rotation, glare, low contrast, handwriting where supported, multi-page PDFs, tables, conflicting OCR and malicious embedded instructions.

### TEST-009 — Longitudinal evaluation — P0
Personal-state QA MUST test stale facts, corrected facts, conflicting sources, time ordering and revoked snapshot reuse.

### TEST-010 — Emergency evaluation — P0
Care navigation MUST test under-triage and over-triage separately with a release gate weighted toward preventing dangerous under-triage.

### TEST-011 — Disclosure evaluation — P0
Cross-profile, wrong-purpose, revoked-consent and prohibited-data disclosure tests MUST pass before rollout.

### TEST-012 — Write safety — P0
Concurrent state/consent/policy change tests MUST exercise the real database commit path, not only mocks.

### TEST-013 — Model drift — P0
Unofficial gateway changes MUST be detectable through capability probes and scheduled evaluation; unexpected material regression MUST trigger route disable/rollback.

### TEST-014 — Content review — P1
High-risk consumer copy MUST have a reproducible health-literacy/clinical-safety review checklist.

---

## 22. Migration and compatibility requirements

### MIG-001 — Strangler migration — P0
The rebuild MUST use compatibility redirects/adapters and incremental route replacement rather than a flag-day deletion of working safety-critical code.

### MIG-002 — Legacy URL map — P0
Every currently supported route MUST be classified as canonical, redirect, professional-only, admin-only or retirement candidate before removal.

### MIG-003 — Data migration safety — P0
Presentation convergence MUST not collapse distinct clinical database entities merely to simplify UI.

### MIG-004 — Rollback — P0
Each rollout phase MUST have a tested rollback path that does not require reversing irreversible user-data transformations.

### MIG-005 — Feature flags — P0
New shell, Home, Health projection, Ask composer, multimodal extraction and model adapters MUST be separately deployable/disableable.

### MIG-006 — Old client compatibility — P0
API changes needed by the rebuild MUST preserve currently supported web/mobile clients until an explicit minimum-client/version migration gate is reached.

### MIG-007 — Deep links — P0
Legacy notifications, bookmarks and public links MUST continue to resolve safely through redirect/adaptation during migration.

---

## 23. Release acceptance gates

The P0 rebuild MUST NOT be promoted to 100% consumer traffic until all gates below are true:

1. Consumer IA has no unresolved route/feature loss for authorized users.
2. Home/Ask/Health/Care/You E2E passes on defined web viewports and supported mobile devices.
3. WCAG 2.2 AA automated + manual critical-flow checks pass.
4. No raw PII appears in analytics/model-route telemetry tests.
5. Cross-profile and revoked-consent adversarial tests pass.
6. New PHR bounded writes pass PostgreSQL concurrency tests with no silent lost update.
7. Multimodal extraction cannot directly confirm/commit health truth without review/policy.
8. Model routes are capability-probed, versioned, benchmarked and rollbackable.
9. Emergency/care-navigation safety set passes predefined under-triage threshold.
10. Medication safety regression suite remains green.
11. GLHS stale-state/authorization write protections remain green on real DB paths.
12. No fabricated fallback activity or reassuring error state exists.
13. Core Web Vitals/bundle budgets meet release thresholds or have an approved documented exception.
14. Vietnamese and English copy parity checks pass.
15. A canary release shows no material rise in error, abandonment, safety or support metrics before expansion.


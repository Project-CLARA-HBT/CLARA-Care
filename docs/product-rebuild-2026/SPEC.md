# CLARA Care — Consumer-First Product Rebuild Specification

**Status:** implementation source of truth  
**Prepared:** 2026-08-19  
**Repository reviewed:** `Project-CLARA-HBT/CLARA-Care`  
**Product baseline:** `main` at `81c024d74ea9201b31e22b5c02b1b6f852c0ce9e`; `codex/commitloop-phase-a` is 204 commits ahead but the reviewed delta is research/evaluation-focused, so the active web/mobile product surfaces are effectively based on the modernized product code already merged to `main`. Open PR #119 is research-document synchronization and does not define this product redesign.  
**Primary audience:** ordinary health consumers in Vietnam first; clinicians/researchers/admins remain supported through role-scoped professional modes.  
**Languages:** Vietnamese-first, English complete parity.  
**Implementation posture:** deep product reset, not another visual reskin. Preserve clinical safety, GLHS, consent, RBAC, provenance, audit, fail-closed medication safety, and compatibility boundaries.

---

## 1. Executive product decision

CLARA Care should stop presenting itself as a collection of named AI/health modules and become a **single longitudinal health companion**.

The product-level promise is:

> **CLARA helps you understand what is happening with your health, keep your information organized, prepare for care, and know the safest next step — using your permitted health context and showing what it knows, what it does not know, and where information came from.**

Ordinary users should not need to know what “LifeMap”, “CareGuard”, “Self-Med”, “Council”, “RAG”, “Deep mode”, “personal mode”, “THSS”, “GLHS”, “pipeline”, or model tiers mean. Those remain internal architecture/domain names where useful.

The rebuild must optimize for four consumer jobs:

1. **Understand:** “What does this mean for me?”
2. **Remember:** “What happened, when, and what am I taking/doing now?”
3. **Prepare:** “What should I bring up at my appointment or do next?”
4. **Act safely:** “Can this wait, should I contact a clinician, or is this urgent?”

AI is an interaction layer across these jobs, not a destination users must configure.

---

## 2. Code review findings that drive this rebuild

### 2.1 What is already strong and must be preserved

The repository already contains valuable foundations that should not be discarded:

- server-authoritative RBAC and profile scoping;
- consent gates, audit, data-rights flows, public-share boundaries and CSRF controls;
- GLHS foundations and governed read/write concepts;
- LifeMap longitudinal events, episodes, tasks, source references, revisions and outbox infrastructure;
- PHR provenance/verification concepts;
- medication normalization and DrugBank-backed safety behavior;
- explicit draft/review flows for universal capture;
- Chat streaming, citations/evidence infrastructure and research workflows;
- Council/Scribe clinical workflows;
- web and Flutter mobile clients;
- Vietnamese/English localization infrastructure;
- E2E/accessibility/route-matrix/bundle testing introduced in the previous modernization.

The rebuild is therefore **presentation/domain-convergence work plus AI/platform modernization**, not a rewrite of every safety primitive.

### 2.2 Remaining product/UX debt in current product code

#### A. The mental model is still module-first

Even after workspace modernization, consumer navigation still exposes `/today`, `/chat`, `/lifemap`, `/medicines`, `/phr`, with visits/family/community/consent as secondary destinations. Mobile Home similarly renders a grid of feature/module cards including Chat, CareGuard, multiple medication cabinets, Council, Scribe, consent, and PHR depending on role/flags.

**Impact:** users must learn the product architecture before getting value.

#### B. Chat still exposes internal AI configuration

The current Chat composer exposes Fast/Deep/Research execution modes, retrieval-source depth, a personal-context toggle, and professional output controls. These are useful debug/power-user mechanisms but inappropriate as primary controls for ordinary users.

**Impact:** users are asked to route the AI themselves rather than describe their goal.

#### C. The shell remains orchestration-heavy

`AppShell` still owns substantial authentication hydration, role, profile, language, theme, workspace, navigation, onboarding, notifications, profile switching, focus management and layout behavior in one client component.

**Impact:** regression risk, redundant fetches, high coupling, and difficulty creating truly context-aware surfaces.

#### D. Public positioning still speaks in system/module language

The landing experience still promotes Council, Self-Med, CareGuard and Scribe and contains system-oriented terms such as “engine”, “system core” and clinical context framing.

**Impact:** the product feels like a technical demonstration rather than a trusted personal health product.

#### E. “Today” is task-centric but not yet a complete daily health home

The current Today page centers LifeMap tasks plus four quick actions. It lacks a single coherent snapshot of recent changes, medications/reminders, upcoming care, new results/documents, connected-device trends, and an ambient Ask CLARA entry.

#### F. Health information remains split across conceptual silos

PHR, LifeMap, medication courses, cabinet scans, visits and evidence are intentionally distinct backend models, but the consumer UI exposes too much of that distinction. The current PHR client still has a whole-record `PUT /api/v1/phr/record`, which creates a concurrency hazard for section-level editing.

#### G. Universal Capture is a strong hidden capability

The API already has secure capture sessions, source artifacts, malware scanning, candidate extraction, provenance, confidence, explicit review and GLHS ingestion seams. This should become a flagship **Add anything** consumer workflow rather than remain a specialized feature.

#### H. The LLM registry is safety-conscious but provider-specific

The current model registry has excellent task contracts and fail-closed concepts but is deliberately DeepSeek-specific. The requested unofficial Gemini routes cannot be cleanly added without separating **task policy** from **provider transport/model aliases**.

---

## 3. Market and user-need analysis

### 3.1 Market signals used for prioritization

The rebuild is informed by current consumer-health patterns, not feature novelty alone:

- EY's 2026 consumer health research reports growing use of AI in health decisions while clinicians remain the most trusted source. It also highlights the gap between consumer health tracking and clinician use of wearable data. Product implication: AI must support interpretation and care preparation without pretending to replace professional judgment.
- Deloitte's 2026 healthcare outlook recommends integrated digital platforms rather than disconnected point tools. Product implication: CLARA should converge records, monitoring, medication, care navigation and AI around one longitudinal context.
- MyChart's current consumer feature set establishes expectations around test results, medications/refills, health summaries, appointments, clinical notes, family access, record sharing and access transparency.
- Apple Health establishes expectations for consolidated health/device data, medication tracking, granular sharing and record aggregation.
- Android Health Connect now supports health/fitness data and experimental FHIR-based medical records with granular permissions. Product implication: the Android app should treat Health Connect as a first-class integration, with feature availability and permission-aware behavior.
- Ada demonstrates demand for simple-language symptom assessment and care navigation rather than raw diagnosis output.
- WCAG 2.2 and the CDC Clear Communication Index provide practical standards for accessible interaction and plain-language health communication.

### 3.2 Product gaps CLARA should fill

CLARA already has deeper longitudinal/governance infrastructure than many simple chat products. Its differentiated product opportunity is to combine:

1. **personal health memory** — longitudinal, corrected, source-aware health history;
2. **multimodal capture** — turn photos, PDFs, text and voice into reviewable health information;
3. **grounded explanation** — answer across current permitted personal state plus cited external evidence;
4. **care preparation** — transform history into useful visit questions, summaries and next actions;
5. **safe care navigation** — urgency guidance and appropriate escalation without autonomous diagnosis/treatment;
6. **consumer-controlled sharing** — family/clinician sharing with purpose, scope, expiry and access history;
7. **interoperability** — Health Connect/HealthKit/FHIR imports without erasing provenance;
8. **co-versioned governance** — keep CLARA's GLHS safety advantage invisible to users but enforce it underneath every AI-assisted write.

### 3.3 Features to deprioritize as primary consumer navigation

These capabilities may remain, but must not compete for first-level consumer attention:

- named “Council” module;
- named “CareGuard” module;
- named “Self-Med” module;
- research execution modes;
- source-stack configuration;
- system dashboards;
- raw confidence values;
- graph/RAG terminology;
- AI model selector;
- diagnostic-style AI scores without validated intended use;
- social/community features unless evidence proves retention/safety value.

---

## 4. Target information architecture

### 4.1 Consumer navigation

Desktop primary navigation: **4 destinations + global Ask action**.

1. **Hôm nay / Home** — what matters now.
2. **Sức khỏe / Health** — unified record, timeline, medicines, results, measurements, documents.
3. **Chăm sóc / Care** — appointments, visit preparation, care plan, symptom/care navigation, family/caregiver coordination.
4. **Bạn / You** — profile, sharing, privacy, integrations, notifications, accessibility.
5. **Ask CLARA** — persistent action/omnibox, not a separate navigation burden.

Mobile bottom navigation:

- Hôm nay
- Sức khỏe
- **Ask** (center action)
- Chăm sóc
- Bạn

No ordinary-user workspace selector is shown. A user who also has professional permissions gets a clearly separated **“Công việc chuyên môn”** entry under profile/account; professional navigation is not mixed with personal health navigation.

### 4.2 Professional modes

#### Clinician mode

- Work home
- Patient/case context
- Ask CLARA
- Multidisciplinary review (current Council domain)
- Clinical note assistant (current Scribe domain)
- Evidence

#### Research mode

- Ask / Research workspace
- Evidence/source library
- saved research threads
- export/reproducibility controls

#### Admin mode

Remain separate from the consumer shell. Do not force admin telemetry and operational screens into consumer IA.

### 4.3 Route migration concept

Canonical consumer routes:

```text
/home
/ask
/health
/health/timeline
/health/medications
/health/results
/health/measurements
/health/documents
/health/history
/care
/care/visits
/care/visits/:id
/care/prepare
/care/check-symptoms
/care/family
/you
/you/profile
/you/sharing
/you/privacy
/you/integrations
/you/notifications
```

Legacy routes remain as redirects/deep-link adapters until traffic and parity gates allow retirement:

```text
/today                -> /home
/chat                 -> /ask
/lifemap              -> /health/timeline
/phr                  -> /health
/medicines            -> /health/medications
/visits               -> /care/visits
/family               -> /care/family
/account/consent      -> /you/privacy
```

Professional routes may keep technical names internally but should use user-facing labels.

---

## 5. Core experience specifications

## 5.1 Home — “Hôm nay”

### Goal

Answer in under five seconds: **What needs my attention today?**

### Layout priority

1. greeting + active profile;
2. single “Ask CLARA” entry with text/voice/camera/file affordances;
3. one highest-priority next action;
4. “Mới thay đổi” — new results, new documents, medication changes, recent measurements or accepted timeline updates;
5. “Hôm nay” — medication reminders, appointments, tasks, check-ins;
6. lightweight trend snapshot if sufficient data exists;
7. optional “Chuẩn bị cho lần khám tới” card;
8. calm empty state when nothing is due.

### Rules

- never fabricate activity to make Home look populated;
- never show ten equally weighted cards;
- no “dashboard confidence” or pseudo-clinical score;
- no generic guilt-based streaks;
- reminders can be snoozed, adjusted or disabled;
- important safety alerts outrank engagement content;
- derived AI content must carry a visible source/state indicator when it can influence understanding.

## 5.2 Ask CLARA — one multimodal entry

### Consumer composer

Primary controls only:

- text input;
- microphone;
- camera;
- attach image/PDF/document;
- send.

No Fast/Deep/Research selector for ordinary users.

Optional secondary action: “Dùng hồ sơ sức khỏe của tôi” with a plain explanation of what data classes will be used; default behavior follows task/purpose consent and THSS policy.

### Automatic intent routing

CLARA internally decides whether the request is primarily:

- general health explanation;
- personal timeline lookup;
- document/label understanding;
- medication question;
- lab/result explanation;
- visit preparation;
- care navigation;
- research/evidence lookup;
- record capture/update proposal;
- prohibited/high-risk request requiring bounded response/escalation.

A user can ask “Tại sao?” to see a plain-language explanation of what sources/context were used. Internal chain-of-thought is never shown.

### Answer structure

Default answer order:

1. **Điều quan trọng nhất** — concise answer/main message.
2. **Bạn có thể làm gì tiếp theo** — one to three safe actions.
3. **Dựa trên đâu** — sources/personal facts actually used.
4. **Điều CLARA chưa biết hoặc chưa chắc** — uncertainty/missing inputs.
5. **Khi nào cần hỗ trợ y tế** — only when relevant.
6. expandable technical/professional detail for authorized professional users.

### Personal record writeback

If the answer detects information worth saving, show an explicit review card:

> “CLARA thấy 2 thông tin có thể thêm vào hồ sơ của bạn.”

Each proposal shows exact source, interpreted value, date/time, status and edit controls. Nothing becomes confirmed truth merely because an LLM extracted it.

## 5.3 Unified Health — “Sức khỏe”

### Health overview

Sections:

- Điều quan trọng / health summary
- Dòng thời gian
- Thuốc
- Kết quả & xét nghiệm
- Chỉ số đo
- Dị ứng & tình trạng sức khỏe
- Tiêm chủng / procedures where data exists
- Tài liệu

Backend entities remain separate; the UI creates a **consumer projection** with clear state badges:

- “Đã xác nhận”
- “Bạn đã ghi”
- “Từ tài liệu — chờ xác nhận”
- “Từ thiết bị”
- “Đã ngừng”
- “Có thông tin mâu thuẫn”

### Timeline

The timeline is the consumer expression of LifeMap/GLHS longitudinal state.

Must support:

- time zoom: recent / month / year / all;
- filter by medication, symptom, visit, result, measurement, document;
- correction history without overwhelming default view;
- exact source and provenance on demand;
- grouped episodes;
- “what changed?” comparison;
- Ask CLARA scoped to a period or episode.

### Results/labs

For a result:

- value, unit and lab-provided reference range first;
- previous values/trend if comparable;
- specimen/date/source;
- plain-language explanation;
- explicit statement that a flag outside a range is not itself a diagnosis;
- contextual questions to ask a clinician;
- no invented normal range if source lacks one;
- no diagnostic interpretation of images under this product scope.

### Medications

One consumer medication experience must reconcile, without erasing provenance:

- current medication list;
- prescribed/recorded courses;
- scanned cabinet/label candidates;
- supplements if supported;
- schedule/reminders;
- interaction and duplicate review;
- refill/expiry reminders where data exists;
- start/stop history.

A scanned item is never silently displayed as “currently taking”.

## 5.4 Add anything — Universal Capture

Prominent entry from Home and Health:

> **Thêm thông tin sức khỏe**

Methods:

- Chụp ảnh
- Tải tài liệu/PDF
- Quét thuốc
- Ghi âm
- Nhập bằng lời
- Nhập thủ công
- Kết nối nguồn dữ liệu

### Review-first flow

1. capture/upload;
2. preprocessing/security scan;
3. multimodal extraction;
4. review candidates in a single human-friendly sheet;
5. user edits/confirms/rejects;
6. governed commit with exact snapshot/version binding;
7. source remains attached.

For PDFs/images show page/region highlight for each extracted candidate where practical.

## 5.5 Care — “Chăm sóc”

### Visits

- upcoming/past visits;
- visit details;
- checklist/document preparation;
- “Prepare with CLARA” summary;
- questions generated from confirmed record + user goals;
- after-visit summary and action extraction from documents/notes;
- reminders with user control.

### Care navigation / symptom check

This is not an autonomous diagnosis surface. It should:

- ask a bounded set of safety-relevant questions;
- detect emergency red flags deterministically where possible;
- provide an urgency/care-setting recommendation such as emergency, urgent/same-day, routine appointment, pharmacist, self-care/support;
- state why the recommendation was made in plain language;
- offer a handoff summary users can show a clinician;
- never downgrade an emergency because the LLM sounds reassuring;
- avoid disease probability lists as the main output for consumers.

### Family/caregiver

- manage people/grants from one place;
- grant by data class/purpose and duration;
- preview exactly what will be shared;
- access history;
- revoke immediately;
- caregiver digest only from pre-filtered authorized context.

## 5.6 You — account, privacy and integrations

Sections:

- personal details;
- emergency card;
- language/accessibility;
- notifications/reminders;
- connected data sources;
- family/sharing;
- privacy & AI;
- consent;
- download/export/delete data;
- active sessions/devices;
- “Who accessed my information?” where audit data permits.

### AI transparency panel

Use non-technical language:

- what types of information AI may use;
- whether a request used personal data;
- external model/gateway disclosure at a policy-appropriate level;
- retention/caching policy;
- how to turn specific uses off;
- how to correct information.

Do not expose secrets, raw prompts, hidden reasoning or sensitive telemetry.

---

## 6. AI feature portfolio

AI features are prioritized by consumer value and reversibility.

### P0 — ship as core rebuild capabilities

1. **Ask My Health** — grounded questions across authorized current longitudinal state.
2. **Multimodal document/label capture** — image/PDF/text/voice to reviewable structured candidates.
3. **Visit preparation** — concise longitudinal summary + user-selected questions.
4. **Plain-language result explanation** — grounded to exact result metadata/reference range.
5. **Medication understanding** — label recognition, normalized candidates, interaction explanation and source-aware safety checks.
6. **“What changed?” summaries** — deterministic diff plus LLM wording.
7. **Contradiction/duplicate/missing-info assistant** — surfaces review needs, never chooses truth autonomously.
8. **Next-best-question wording** — deterministic eligibility, AI phrasing/ranking within allowed set.
9. **After-visit/document action extraction** — reviewable tasks and medication changes.
10. **Caregiver digest** — consent-filtered summary with exact sources.

### P1 — add after P0 quality gates

- weekly/monthly health digest;
- personalized evidence explanation;
- connected-health trend explanation;
- natural-language search over the record;
- contextual preventive-care reminders based on deterministic rules/guidelines;
- intelligent notification bundling;
- health literacy “explain simpler / explain more” modes;
- multilingual document explanation while preserving original text;
- offline/on-device PII preprocessing where practical.

### Shadow/pilot only

- personal anomaly detection;
- pattern relationship explorer;
- low-risk wellness forecasting;
- learned question ranking;
- trial matching.

### Out of production scope without a separate clinical program

- autonomous diagnosis;
- medication prescribing/dosing changes;
- disease/deterioration prediction presented to consumers;
- treatment-effect prediction;
- autonomous care agents that act on behalf of the user;
- medical-image diagnosis;
- unreviewed LLM writeback to the health record;
- continuous self-learning model behavior in production.

---

## 7. Gemini multimodal integration policy

The user-provided model names **`gemini-3.6-flash-high`** and **`gemini-3.7-tiered`** are treated as **private/unofficial deployment aliases**, not as public vendor contracts. CLARA must not hard-code assumptions about an official API, SLA, version lifetime or regulatory status.

### 7.1 Capability profiles

The product asks for capabilities, never model names:

- `FAST_TEXT_MULTIMODAL`
- `QUALITY_TEXT_MULTIMODAL`
- `DOCUMENT_VISION`
- `STRUCTURED_EXTRACTION`
- `GROUNDED_SYNTHESIS`

Deployment configuration maps those capabilities to private aliases.

Suggested initial mapping, subject to benchmark evidence:

- `gemini-3.6-flash-high`: latency-sensitive extraction, classification, rewriting, OCR post-processing, low-risk summaries, reranking.
- `gemini-3.7-tiered`: complex multimodal document understanding and higher-quality grounded synthesis.

Both mappings must be overrideable and capability-probed. If the private gateway does not support a needed modality/structured-output behavior, the task fails closed or uses its explicitly approved deterministic fallback.

### 7.2 Safety rules

- no request parameter may choose arbitrary provider/model;
- task contract remains authoritative;
- no silent cross-model fallback for high-risk tasks;
- model alias, gateway build, prompt contract, schema version, input snapshot digest and tool versions must be recorded in PII-safe provenance;
- raw clinical prompts/responses are not sent to analytics;
- shadow/canary evaluation precedes promotion for medium/high-risk tasks;
- external/unofficial routes must be easy to disable globally and by task;
- timeout/unavailability must degrade to a safe non-AI experience, not block access to the record.

---

## 8. Content and language system

### 8.1 Voice

CLARA should sound:

- calm;
- clear;
- respectful;
- specific;
- non-alarmist;
- non-patronizing;
- honest about uncertainty;
- action-oriented.

### 8.2 Vietnamese-first rules

Prefer common Vietnamese before specialist terms.

Examples:

| Avoid as primary copy | Prefer |
|---|---|
| PHR | Hồ sơ sức khỏe |
| LifeMap | Dòng thời gian sức khỏe |
| CareGuard | Kiểm tra an toàn thuốc |
| Self-Med | Thuốc của tôi |
| Council | Hội chẩn chuyên môn |
| Scribe | Ghi chú buổi khám |
| Evidence | Nguồn tham khảo / Nguồn đã dùng |
| Clinical context | Thông tin sức khỏe được dùng |
| Confidence 83% | CLARA còn chưa chắc về… / Cần xác nhận… |
| Pipeline failed | Chưa thể kiểm tra thông tin này lúc này |
| Commit | Lưu thay đổi |
| Candidate | Thông tin CLARA nhận ra |

Specialist term can follow in parentheses when useful.

### 8.3 Health-content template

Every consequential health message should be reviewable against CDC Clear Communication principles:

- main message visible first;
- one clear action if action is needed;
- familiar words;
- short sentences;
- numbers explained in context;
- risk expressed with words plus numbers only when the number is meaningful and sourced;
- uncertainty explicit;
- no false precision;
- urgent actions visually distinct but not panic-inducing.

Target internal Clear Communication Index score: **>= 90** for high-traffic patient education/safety surfaces.

---

## 9. Visual and interaction direction

### 9.1 Design character

“Modern medical” means:

- light, calm surfaces;
- generous spacing;
- strong typography hierarchy;
- restrained brand accent;
- status colors reserved for meaning;
- no cyber/neon/terminal metaphors;
- minimal glassmorphism;
- meaningful charts only;
- real content over decorative metrics;
- one dominant action per surface.

### 9.2 Design tokens

Create shared semantic tokens for web/mobile:

- canvas/surface/elevated/interactive;
- text primary/secondary/muted/inverse;
- brand;
- informational/success/warning/danger;
- focus;
- source/provenance states;
- confirmed/unconfirmed/conflict states;
- spacing/radius/elevation/type scale/motion.

Status color must never be the sole signal.

### 9.3 Accessibility

Minimum product target: WCAG 2.2 AA.

CLARA-specific stronger defaults:

- interactive touch target >= 44x44 CSS px when layout permits;
- keyboard-complete web flows;
- visible focus and no obscured focus;
- screen-reader labels for medical values, trends and charts;
- 200% text zoom without loss of function;
- reduced motion support;
- high-contrast compatible tokens;
- accessible authentication;
- captions/transcripts for audio workflows;
- large-text mode on mobile;
- never encode urgency only through color.

---

## 10. Onboarding redesign

Onboarding should provide value before demanding profile completeness.

### Step 1 — What do you want help with?

Choose any:

- Hiểu kết quả hoặc giấy tờ y tế
- Theo dõi thuốc
- Ghi lại sức khỏe theo thời gian
- Chuẩn bị đi khám
- Hỏi về sức khỏe
- Theo dõi chỉ số từ thiết bị

### Step 2 — Add only useful context

Offer, do not require:

- medication list;
- allergies;
- important conditions;
- emergency contact;
- first document scan/import.

### Step 3 — Connect data (optional)

- Android Health Connect where available;
- Apple Health/HealthKit when iOS app exists/support is added;
- FHIR/provider connection when configured.

### Step 4 — Notification preferences

Explain categories before asking permissions.

Onboarding can be skipped. Missing information should result in “CLARA does not know this yet,” not a blocked app.

---

## 11. Interoperability and connected health product scope

### Android

Prioritize Health Connect integration for:

- steps/activity;
- sleep;
- heart rate/resting heart rate;
- blood pressure where available;
- oxygen saturation;
- body measurements;
- other explicitly supported data types;
- experimental medical-record/FHIR support only behind a capability flag and Play-policy readiness gate.

Permissions are requested progressively by user intent, never as a blanket onboarding permission dump.

### iOS

Plan a HealthKit/Health Records adapter with the same canonical ingestion envelope and provenance semantics. Do not make iOS parity a blocker for the Android-first rebuild if the current app delivery is Android-focused.

### FHIR

Use FHIR as an interoperability boundary, not the consumer UI mental model. Preserve source organization, resource identity, version, effective time and provenance. Imported records must not silently overwrite user-entered or previously confirmed state.

---

## 12. Trust model visible to users

For any important answer or stored fact, users should be able to discover:

- **Where did this come from?**
- **When was it true/recorded?**
- **Has it been confirmed?**
- **Did CLARA infer anything?**
- **Can I correct it?**
- **Who can see it?**

The UI does not expose GLHS protocol details, but GLHS must enforce the binding between the state disclosed to AI and any subsequent write proposal.

---

## 13. Success metrics

### Usability

- median time from Home to desired action;
- task completion rate by top jobs;
- first-session activation: user gets one meaningful result without setup burden;
- navigation backtracking rate;
- attachment/capture completion rate;
- candidate-review correction rate;
- visit-prep completion.

### Trust/comprehension

- user can identify whether content came from own record vs external source;
- user can identify uncertainty/unknowns;
- user can identify appropriate next action;
- health-copy comprehension testing;
- CCI score >=90 for selected patient-facing education/safety content.

### AI quality

- claim-level groundedness/citation precision;
- temporal accuracy;
- prohibited disclosure rate;
- stale-state use rate;
- multimodal extraction field accuracy;
- candidate acceptance/edit/reject rates;
- unsafe over-escalation and under-escalation separately;
- abstention appropriateness;
- Vietnamese terminology/readability quality;
- latency p50/p95 by task.

### Reliability/performance

- Web Core Vitals target: p75 LCP <=2.5s, INP <=200ms, CLS <=0.1 on supported production traffic;
- no fabricated fallback data;
- graceful non-AI path during model outage;
- no loss of user-entered draft during AI failure;
- write conflict/lost-update rate effectively zero under accepted concurrency contract.

---

## 14. Non-goals

This rebuild does **not** require:

- deleting the GLHS/research program;
- renaming backend domain classes solely for aesthetics;
- merging clinically distinct medication entities into one database table;
- removing professional/research/admin capabilities;
- introducing diagnosis/prescribing autonomy;
- turning every screen into chat;
- forcing wearable/device integration;
- requiring personal context for general health questions;
- claiming unofficial Gemini endpoints are official or clinically validated.

---

## 15. Source and evidence references

Reviewed 2026-08-19:

- CLARA-Care repository product code and existing UI modernization/LifeMap AI specifications.
- EY, *Global/US Consumer Health Survey 2026*: https://www.ey.com/en_us/insights/health/ey-us-consumer-health-survey-2026
- Deloitte, *2026 US health care outlook*: https://www.deloitte.com/us/en/insights/industry/health-care/life-sciences-and-health-care-industry-outlooks/2026-us-health-care-executive-outlook.html
- Epic MyChart, current feature overview: https://www.mychart.org/Features
- Apple Health / Health Records and privacy documentation: https://support.apple.com/guide/iphone/view-health-records-iph2b3a37ddd/26/ios/26 and https://www.apple.com/uk/legal/privacy/data/en/health-app/
- Android Health Connect: https://developer.android.com/health-and-fitness/health-connect
- Android Health Connect Medical Records: https://developer.android.com/health-and-fitness/health-connect/medical-records
- Ada Health care navigation: https://about.ada.com/health-plans/
- W3C WCAG 2.2: https://www.w3.org/TR/WCAG22/
- CDC Clear Communication Index: https://www.cdc.gov/ccindex/tool/index.html


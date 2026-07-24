# CLARA Wearable and Health Data Integration

## Implementation Task List

Status: ready for estimation and assignment  
Version: 1.0  
Date: 2026-07-25  
Technical design:
[Wearable and Health Data Integration Technical Design](clara-wearable-health-integration-technical-design-2026-07-25.md)  
Parent specification:
[CLARA Viet Nam Personal Health Assistant](clara-vietnam-personal-health-assistant-unified-spec-2026-07-25.md)

## 1. Execution rules

- A task is done only when its acceptance criteria and tests pass.
- Vendor approval tasks are real blockers; engineering must not replace them with
  fake production responses.
- New connector paths are read-only by default.
- Every schema and endpoint is profile-scoped, consent-aware and auditable.
- Synthetic records are restricted to automated tests and labeled test tenants.
- Real E2E requires consenting test accounts and physical devices.
- No wearable value can enter CLARA Chat/Research context before provenance,
  freshness and safety gates are active.
- Feature flags default off in production until the rollout gate approves them.

Priority:

- **P0:** required for the first safe connector release;
- **P1:** required before broad rollout;
- **P2:** later optimization or watch-native expansion.

Size:

- **S:** up to two focused engineering days;
- **M:** approximately three to five engineering days;
- **L:** approximately one to two engineering weeks;
- **XL:** must be decomposed after discovery.

Estimates exclude vendor review time.

## 2. Dependency map

```text
Governance/vendor gates (WH-001..009)
        |
        v
Canonical contracts and persistence (WH-020..031)
        |
        +--------------------+
        v                    v
Mobile connector shell   Backend ingestion/control plane
(WH-040..047)            (WH-060..071)
        |                    |
        +----------+---------+
                   v
       Health Connect + Huawei adapters
       (WH-080..099)
                   |
                   v
       LifeMap/Today projection and UX
       (WH-120..135)
                   |
                   v
       Harness shadow -> gated release
       (WH-140..150)

Fitbit cloud (WH-100..111) depends on backend control plane and vendor app approval.
Wear OS (WH-180..) remains deferred until a watch-native use case is approved.
```

## 3. Workstream A — Product, policy and vendor readiness

### WH-001 — Freeze first-release user outcomes

- Priority/size: P0 / S
- Owner: Product + Clinical
- Dependencies: none
- Deliverable: approved list of Getting Started goals and data needed by each.
- Acceptance:
  - each requested data type maps to a visible user benefit;
  - the first release includes no speculative permission;
  - use of wearable data is classified as wellness, education or regulated
    functionality in the intended-use registry.

### WH-002 — Data-type and purpose matrix

- Priority/size: P0 / M
- Owner: Product + Privacy + Clinical
- Dependencies: WH-001
- Deliverable: versioned provider/data type/purpose/retention matrix.
- Acceptance:
  - includes steps, activity, sleep, heart rate, weight and gated clinical
    measurements;
  - names allowed UI, LifeMap and AI-context uses separately;
  - states read direction, history window and expiry.

### WH-003 — Health Connect policy package

- Priority/size: P0 / M
- Owner: Android + Privacy
- Dependencies: WH-002
- Deliverable: Google Play Health apps declaration, Data Safety answers and
  permission rationales.
- Acceptance:
  - every permission matches the manifest and visible feature;
  - public and in-app privacy-policy text match;
  - approval evidence is recorded before production flag enablement.

### WH-004 — Huawei developer access

- Priority/size: P0 / M
- Owner: Platform Partnerships
- Dependencies: WH-002
- Deliverable: verified Huawei organization, app identity, signing fingerprints
  and scope applications.
- Acceptance:
  - Vietnam availability confirmed;
  - basic versus enterprise-only data types documented;
  - production and non-production application IDs are separated;
  - credentials are stored in the approved secret manager.

### WH-005 — Huawei capability spike

- Priority/size: P0 / M
- Owner: Android
- Dependencies: WH-004
- Deliverable: tested capability matrix across Huawei and non-Huawei phones.
- Acceptance:
  - confirms supported HMS Core/Huawei Health/Android versions;
  - records background restrictions and user remediation;
  - confirms at least one real Huawei wearable path;
  - unsupported types remain explicitly disabled.

### WH-006 — Fitbit developer access

- Priority/size: P1 / S
- Owner: Platform Partnerships
- Dependencies: WH-002
- Deliverable: Fitbit application, scopes, redirect URIs and review status.
- Acceptance:
  - user OAuth flow is approved;
  - client credentials are not represented as user authorization;
  - rate limits and permitted retention are documented.

### WH-007 — Privacy and cross-border assessment

- Priority/size: P0 / M
- Owner: Privacy/Legal
- Dependencies: WH-002
- Deliverable: data-flow assessment and retention/deletion decision.
- Acceptance:
  - covers device-to-CLARA and vendor-cloud-to-CLARA flows;
  - defines token and raw-payload handling;
  - documents processors, regions and user disclosures;
  - unresolved legal use remains feature-flagged off.

### WH-008 — Clinical safety intended-use review

- Priority/size: P0 / M
- Owner: Clinical Governance
- Dependencies: WH-001, WH-002
- Deliverable: release classes and prohibited inferences by metric.
- Acceptance:
  - no consumer wearable is described as diagnostic by default;
  - escalation and corroboration rules exist;
  - high-risk metrics cannot enter recommendations before approval.

### WH-009 — Real-device test inventory

- Priority/size: P0 / S
- Owner: QA
- Dependencies: none
- Deliverable: device/account matrix and custody plan.
- Acceptance:
  - includes Android 14+, pre-14 Health Connect, Huawei/non-Huawei phone, Huawei
    wearable and a compatible Wear OS source;
  - Fitbit account/device exists before Fitbit E2E;
  - accounts contain consented non-synthetic test data.

## 4. Workstream B — Canonical contract and database

### WH-020 — Canonical connector schemas

- Priority/size: P0 / M
- Owner: Backend
- Dependencies: WH-002
- Target: `services/api/src/clara_api/connected_health/schemas.py`
- Acceptance:
  - Pydantic models cover connector, consent, batch, observation, tombstone and
    aggregate;
  - schema versions reject unknown breaking formats;
  - provider IDs are opaque strings;
  - impossible units/times fail with safe structured errors.

### WH-021 — Provider adapter contract

- Priority/size: P0 / S
- Owner: Backend + Mobile
- Dependencies: WH-020
- Deliverable: shared provider capability/import/state contract.
- Acceptance:
  - Health Connect, Huawei and Fitbit can implement it without provider fields
    leaking into generic service logic;
  - supported data types and limitations are discoverable.

### WH-022 — Connector persistence migration

- Priority/size: P0 / L
- Owner: Backend
- Dependencies: WH-020
- Targets: `services/api/alembic/versions/`, `db/models.py`
- Acceptance:
  - creates account, consent, cursor, batch, observation, version, aggregate,
    contribution, OAuth transaction and audit tables;
  - foreign keys include profile/user scope;
  - unique provider identity and idempotency constraints exist;
  - upgrade/downgrade and SQLite/PostgreSQL test paths pass.

### WH-023 — Token envelope encryption

- Priority/size: P0 / M
- Owner: Security + Backend
- Dependencies: WH-022
- Acceptance:
  - data encryption key is separate from database;
  - token plaintext never appears in ORM repr, logs, errors, audit or responses;
  - key rotation path is tested;
  - failure closes access rather than storing plaintext.

### WH-024 — Unit and type normalization

- Priority/size: P0 / M
- Owner: Backend + Clinical Data
- Dependencies: WH-020
- Target: `connected_health/normalization.py`
- Acceptance:
  - canonical UCUM-compatible units are documented;
  - originals remain auditable;
  - conversions are deterministic and property-tested;
  - incompatible dimensions are rejected.

### WH-025 — Idempotency and record versioning

- Priority/size: P0 / M
- Owner: Backend
- Dependencies: WH-022
- Acceptance:
  - repeated batches do not duplicate records;
  - changed upstream records create traceable versions;
  - provider tombstones stop projection;
  - cursor advances only after durable commit.

### WH-026 — Deduplication engine

- Priority/size: P0 / L
- Owner: Backend + Data
- Dependencies: WH-024, WH-025
- Acceptance:
  - exact provider IDs deduplicate deterministically;
  - fallback similarity never deletes cross-origin records;
  - overlapping daily steps do not sum by default;
  - decisions preserve contributing provenance.

### WH-027 — Aggregate projector

- Priority/size: P0 / L
- Owner: Backend + Data
- Dependencies: WH-026
- Acceptance:
  - daily aggregates list origin, coverage and contributions;
  - source preference changes recompute deterministically;
  - partial-day coverage is visible;
  - source changes cannot silently create a health trend.

### WH-028 — Connector audit service

- Priority/size: P0 / M
- Owner: Backend + Compliance
- Dependencies: WH-022
- Acceptance:
  - authorization, sync, purpose use, pause, revoke, delete and projection are
    auditable;
  - raw health values and secrets are excluded from standard audit summaries.

### WH-029 — DSAR export and delete integration

- Priority/size: P0 / M
- Owner: Backend + Compliance
- Dependencies: WH-022, WH-028
- Targets: existing compliance DSAR modules/tests.
- Acceptance:
  - export includes connector data and provenance for the correct profile;
  - delete removes observations, projections, aggregates and tokens;
  - cross-profile data is never exported/deleted.

### WH-030 — Retention worker

- Priority/size: P1 / M
- Owner: Backend
- Dependencies: WH-007, WH-022
- Acceptance:
  - raw replay payloads expire under policy;
  - canonical data follows disclosed retention;
  - deletion jobs are resumable and audited.

### WH-031 — Canonical contract test kit

- Priority/size: P0 / M
- Owner: QA + Backend
- Dependencies: WH-020, WH-024
- Acceptance:
  - reusable fixtures cover every provider and record type;
  - property tests cover time, units, pagination, tombstones and malformed data;
  - fixtures are visibly non-production.

## 5. Workstream C — Mobile connector framework and Getting Started

### WH-040 — Flutter connector domain layer

- Priority/size: P0 / M
- Owner: Mobile
- Dependencies: WH-021
- Targets: `apps/mobile/lib/core/connected_health/`
- Acceptance:
  - capability, consent, status, import and safe-error interfaces exist;
  - no provider SDK object escapes into screens;
  - unit tests cover unavailable/partial/revoked states.

### WH-041 — Native method-channel contract

- Priority/size: P0 / M
- Owner: Mobile/Android
- Dependencies: WH-021, WH-040
- Targets: Flutter Android host and Dart bridge.
- Acceptance:
  - versioned calls support capabilities, permissions, bounded read and cursor;
  - payload size is bounded/paged;
  - native exceptions map to stable safe error codes.

### WH-042 — Capability detection

- Priority/size: P0 / S
- Owner: Mobile/Android
- Dependencies: WH-041
- Acceptance:
  - detects Health Connect SDK/install/update state;
  - detects Huawei Health/HMS support;
  - hides unsupported connectors without implying device failure;
  - capability results include remediation.

### WH-043 — Getting Started health-source step

- Priority/size: P0 / L
- Owner: Mobile + Product Design
- Dependencies: WH-001, WH-040, WH-042
- Targets: onboarding flow under `apps/mobile/lib/experience/`.
- Acceptance:
  - connection is optional;
  - source choice is capability-aware;
  - purpose and requested types appear before platform consent;
  - "Để sau" and partial permission paths land correctly on Hôm nay;
  - light/dark mode and accessibility tests pass.

### WH-044 — Connected Health management screen

- Priority/size: P0 / L
- Owner: Mobile
- Dependencies: WH-040
- Acceptance:
  - shows source/account/device, categories, status, freshness and errors;
  - supports sync, pause, resume, disconnect and imported-data deletion;
  - destructive deletion requires explicit confirmation;
  - stale/permission-revoked is not shown as healthy.

### WH-045 — Import coordinator

- Priority/size: P0 / L
- Owner: Mobile
- Dependencies: WH-041, WH-060
- Acceptance:
  - reads pages, uploads idempotent batches and resumes after interruption;
  - respects Wi-Fi/battery configuration without losing cursor;
  - checks consent and permissions before each run;
  - no raw values enter analytics/crash logs.

### WH-046 — Mobile secure state

- Priority/size: P0 / M
- Owner: Mobile + Security
- Dependencies: WH-040
- Acceptance:
  - connector IDs and cursors use secure storage where appropriate;
  - vendor client secrets are absent from the app;
  - logout/profile switch cancels in-flight wrong-profile imports.

### WH-047 — Mobile accessibility and copy QA

- Priority/size: P1 / M
- Owner: Design QA
- Dependencies: WH-043, WH-044
- Acceptance:
  - Vietnamese copy explains connection without technical jargon;
  - screen-reader labels, focus order, contrast, text scaling and touch targets
    pass;
  - denial/revocation copy is neutral and actionable.

## 6. Workstream D — Backend connector control plane

### WH-060 — Connector API router

- Priority/size: P0 / L
- Owner: Backend
- Dependencies: WH-020, WH-022, WH-028
- Target: `services/api/src/clara_api/api/v1/endpoints/connected_health.py`
- Acceptance:
  - capabilities/list/create/import/sync/pause/resume/disconnect/delete endpoints
    match the technical design;
  - every operation enforces user/profile ownership;
  - errors use the existing safe envelope and correlation ID.

### WH-061 — Import transaction service

- Priority/size: P0 / L
- Owner: Backend
- Dependencies: WH-024, WH-025, WH-026
- Acceptance:
  - validates, normalizes and persists a page atomically;
  - records accepted/rejected/upserted/tombstoned counts;
  - never advances cursor on failed commit;
  - retry is idempotent.

### WH-062 — Outbox and projection workers

- Priority/size: P0 / L
- Owner: Backend/Platform
- Dependencies: WH-027, WH-061
- Acceptance:
  - import commit and outbox record are atomic;
  - workers are profile/consent aware;
  - retries cannot duplicate projections;
  - dead-letter items are observable and replayable.

### WH-063 — Connector state machine

- Priority/size: P0 / M
- Owner: Backend
- Dependencies: WH-022, WH-060
- Acceptance:
  - only valid transitions are accepted;
  - freshness and `needs_reauth` derive from real evidence;
  - outage cannot convert to a healthy/no-data state.

### WH-064 — Consent enforcement middleware

- Priority/size: P0 / M
- Owner: Backend + Privacy
- Dependencies: WH-002, WH-022
- Acceptance:
  - verifies data type, provider, profile and purpose;
  - revocation blocks new reads/context within the target SLO;
  - mid-job revocation stops remaining pages.

### WH-065 — Imported-data deletion workflow

- Priority/size: P0 / L
- Owner: Backend + Compliance
- Dependencies: WH-029, WH-062
- Acceptance:
  - removes source rows, aggregates, LifeMap projections and cached context;
  - preserves the minimum audit tombstone;
  - is resumable and user-visible;
  - disconnect without delete preserves data exactly as disclosed.

### WH-066 — Source preference API

- Priority/size: P1 / M
- Owner: Backend
- Dependencies: WH-027, WH-060
- Acceptance:
  - preference is scoped by profile and metric;
  - invalid/unavailable origins fail safely;
  - affected aggregates recompute and record the policy version.

### WH-067 — Rate, size and abuse controls

- Priority/size: P0 / M
- Owner: Security + Backend
- Dependencies: WH-060
- Acceptance:
  - page, batch, history and request limits exist;
  - decompression/payload bombs are rejected;
  - legitimate retry does not trigger duplicate processing.

### WH-068 — Connector observability

- Priority/size: P0 / M
- Owner: Platform
- Dependencies: WH-061, WH-063
- Acceptance:
  - dashboards cover auth, cursor age, batch outcomes, duplicates and freshness;
  - labels contain no user ID, token or raw health value;
  - alert runbooks link to safe diagnostics.

### WH-069 — Feature flags and kill switches

- Priority/size: P0 / S
- Owner: Platform
- Dependencies: WH-060
- Acceptance:
  - separate UI/read/projection/context flags exist by provider;
  - disabling reads preserves revoke/delete controls;
  - configuration is tested in off, shadow and release states.

### WH-070 — OpenAPI/client integration

- Priority/size: P0 / M
- Owner: Backend + Mobile
- Dependencies: WH-060
- Acceptance:
  - API schema includes all status/error variants;
  - mobile client integration has contract tests;
  - incompatible schema returns upgrade-required, not data loss.

### WH-071 — Connector control-plane E2E

- Priority/size: P0 / M
- Owner: QA
- Dependencies: WH-060..070
- Acceptance:
  - create, partial import, replay, pause, revoke and delete pass;
  - cross-profile access fails;
  - no production route returns fixture data.

## 7. Workstream E — Health Connect

### WH-080 — Add Health Connect dependency and manifest

- Priority/size: P0 / M
- Owner: Android
- Dependencies: WH-003, WH-041
- Acceptance:
  - supported stable SDK version is pinned after compatibility review;
  - package query, rationale/onboarding activities and only approved permissions
    are declared;
  - Android 14+ and pre-14 variants build.

### WH-081 — Health Connect permission adapter

- Priority/size: P0 / M
- Owner: Android
- Dependencies: WH-080
- Acceptance:
  - requests approved read permissions incrementally;
  - partial/denied/revoked states are returned accurately;
  - permissions are checked before every read.

### WH-082 — Health Connect read adapter

- Priority/size: P0 / L
- Owner: Android
- Dependencies: WH-081, WH-024
- Acceptance:
  - first-release types map to the canonical contract;
  - data origin, device, recording method, IDs and zone offsets survive;
  - pages are bounded;
  - malformed individual records do not discard a whole safe batch.

### WH-083 — Health Connect incremental changes

- Priority/size: P0 / L
- Owner: Android
- Dependencies: WH-082
- Acceptance:
  - change token/cursor is durable;
  - upserts and deletes synchronize;
  - expired/invalid token triggers bounded reconciliation, not full silent reset.

### WH-084 — Health Connect cumulative aggregates

- Priority/size: P0 / M
- Owner: Android + Data
- Dependencies: WH-082
- Acceptance:
  - steps use the supported aggregate API;
  - intervals and zone offsets are correct;
  - overlapping origins do not double count.

### WH-085 — Health Connect history/background access

- Priority/size: P1 / M
- Owner: Android + Product
- Dependencies: WH-081, WH-083
- Acceptance:
  - history beyond 30 days is requested only after a visible user choice;
  - background permission is separate and capability-checked;
  - foreground-only operation remains fully usable.

### WH-086 — Health Connect platform tests

- Priority/size: P0 / L
- Owner: QA/Android
- Dependencies: WH-082..085, WH-009
- Acceptance:
  - framework and app versions pass;
  - install/update unavailable paths pass;
  - manual/automatic/overlapping/revoked records pass;
  - real-device import reaches LifeMap with provenance.

### WH-087 — Play review release gate

- Priority/size: P0 / S
- Owner: Release + Privacy
- Dependencies: WH-003, WH-086
- Acceptance:
  - published manifest matches approved declaration;
  - store listing and privacy policy are current;
  - production flag remains off until approval evidence is recorded.

## 8. Workstream F — Huawei Health

### WH-090 — Huawei build configuration

- Priority/size: P0 / M
- Owner: Android
- Dependencies: WH-004, WH-005, WH-041
- Acceptance:
  - HMS dependencies and repository configuration are pinned;
  - signing/app identity works in the intended flavor;
  - GMS-only build/test path remains operational.

### WH-091 — Huawei capability and authorization adapter

- Priority/size: P0 / L
- Owner: Android
- Dependencies: WH-090
- Acceptance:
  - reports installed/version/country/scope support;
  - requests only approved types;
  - partial/denied/revoked/enterprise-required states are distinct.

### WH-092 — Huawei read adapter

- Priority/size: P0 / L
- Owner: Android
- Dependencies: WH-091, WH-024
- Acceptance:
  - approved first-release types map to canonical records;
  - Huawei IDs, device, source, observed times and API version survive;
  - pages and rate limits are respected.

### WH-093 — Huawei incremental synchronization

- Priority/size: P0 / L
- Owner: Android
- Dependencies: WH-092
- Acceptance:
  - cursor/watermark strategy is documented by data type;
  - retry is idempotent;
  - background restrictions become `partial` or `stale`, not normal/no-data.

### WH-094 — Huawei/Health Connect overlap policy

- Priority/size: P0 / L
- Owner: Data + Backend
- Dependencies: WH-026, WH-027, WH-092
- Acceptance:
  - identical Huawei-origin records exposed through both paths remain traceable;
  - selected primary origin prevents double-counted daily totals;
  - source selection is visible and testable.

### WH-095 — Huawei remediation UX

- Priority/size: P1 / M
- Owner: Mobile
- Dependencies: WH-043, WH-091
- Acceptance:
  - guides installation/update/background settings only when applicable;
  - never implies unsupported enterprise data can be enabled by the user;
  - remediation works in light/dark mode and Vietnamese.

### WH-096 — Huawei real-device E2E

- Priority/size: P0 / L
- Owner: QA/Android
- Dependencies: WH-009, WH-092..095
- Acceptance:
  - Huawei phone and non-Huawei Android phone pass;
  - at least one Huawei wearable contributes real records;
  - revoke, stale background, duplicate-origin and deletion scenarios pass.

### WH-097 — Huawei production gate

- Priority/size: P0 / S
- Owner: Release
- Dependencies: WH-004, WH-008, WH-096
- Acceptance:
  - approved scopes, signing and country availability are reverified;
  - unsupported types are server-disabled;
  - production flag has named owner and rollback.

## 9. Workstream G — Fitbit cloud

### WH-100 — Fitbit OAuth transaction service

- Priority/size: P1 / L
- Owner: Backend + Security
- Dependencies: WH-006, WH-023, WH-060
- Acceptance:
  - signed state, expiry, one-time callback and PKCE when supported are enforced;
  - redirect URI is allow-listed;
  - code/token values never enter logs.

### WH-101 — Fitbit token lifecycle

- Priority/size: P1 / M
- Owner: Backend
- Dependencies: WH-100
- Acceptance:
  - refresh, expiry, revoke and `needs_reauth` work;
  - concurrent refresh is locked/idempotent;
  - encrypted token rotation passes.

### WH-102 — Fitbit provider client

- Priority/size: P1 / L
- Owner: Backend
- Dependencies: WH-101, WH-024
- Acceptance:
  - approved endpoints/scopes map to canonical types;
  - pagination and rate-limit headers are respected;
  - provider timestamps and device/origin are preserved where available.

### WH-103 — Fitbit sync scheduler

- Priority/size: P1 / M
- Owner: Backend/Platform
- Dependencies: WH-102, WH-062
- Acceptance:
  - bounded backfill and incremental schedule exist;
  - retries use jitter/backoff;
  - stale status is visible during vendor outage.

### WH-104 — Fitbit mobile authorization UX

- Priority/size: P1 / M
- Owner: Mobile
- Dependencies: WH-043, WH-100
- Acceptance:
  - uses system browser/deep link safely;
  - cancellation and wrong-account recovery work;
  - consent clearly names Fitbit cloud.

### WH-105 — Fitbit E2E and revocation

- Priority/size: P1 / L
- Owner: QA
- Dependencies: WH-009, WH-101..104
- Acceptance:
  - real account authorization, backfill, refresh, revoke, reconnect and delete
    pass;
  - client credentials alone cannot access user records;
  - rate-limit tests do not lose cursor.

### WH-106 — Fitbit production gate

- Priority/size: P1 / S
- Owner: Release
- Dependencies: WH-006, WH-008, WH-105
- Acceptance:
  - vendor status, scopes and privacy disclosures are approved;
  - direct connection is not redundantly promoted when Health Connect already
    covers the user's selected Fitbit data.

## 10. Workstream H — LifeMap, Today and user control

### WH-120 — Wearable LifeMap projection

- Priority/size: P0 / L
- Owner: Backend + Mobile
- Dependencies: WH-027, WH-062
- Acceptance:
  - trends display metric, source, coverage and freshness;
  - manual versus automatic recording is distinguishable;
  - corrections/source preference are supported;
  - no inferred diagnosis appears as confirmed.

### WH-121 — Connected source status on Hôm nay

- Priority/size: P0 / M
- Owner: Mobile
- Dependencies: WH-044, WH-120
- Acceptance:
  - stale/partial/revoked states are visible without alarming language;
  - connection errors do not become health alerts;
  - empty data has a useful honest state.

### WH-122 — First neutral insight

- Priority/size: P0 / M
- Owner: Product + Data + Mobile
- Dependencies: WH-008, WH-120
- Acceptance:
  - shows coverage/change summary, not diagnosis;
  - insufficient data produces no recommendation;
  - output links to source and selected interval.

### WH-123 — Source preference UI

- Priority/size: P1 / M
- Owner: Mobile
- Dependencies: WH-066
- Acceptance:
  - user can inspect and select the primary origin by metric;
  - change previews affected trends;
  - recomputation status and provenance remain visible.

### WH-124 — Pause/disconnect/delete UX E2E

- Priority/size: P0 / M
- Owner: Mobile + QA
- Dependencies: WH-044, WH-065
- Acceptance:
  - distinctions are understandable in user testing;
  - revoke stops new reads;
  - deletion removes data from UI/context and is auditable;
  - cancelled deletion causes no partial invisible state.

### WH-125 — Family/profile safety

- Priority/size: P0 / M
- Owner: Backend + Mobile + QA
- Dependencies: WH-045, WH-060
- Acceptance:
  - a device import targets only the selected authorized profile;
  - profile switching cannot redirect in-flight batches;
  - caregiver grants are checked independently from device permission.

## 11. Workstream I — Medical-answer harness

### WH-140 — Wearable context artifact

- Priority/size: P0 / L
- Owner: ML/Backend + Clinical Data
- Dependencies: WH-008, WH-027, WH-120
- Acceptance:
  - artifact contains metric, interval, source, coverage, freshness, recording
    method, quality and baseline comparison;
  - raw full time series is excluded;
  - source switches and missingness are explicit.

### WH-141 — Purpose-limited context retrieval

- Priority/size: P0 / M
- Owner: ML/Backend
- Dependencies: WH-064, WH-140
- Acceptance:
  - retrieves only question-relevant approved metrics;
  - revoked/stale/disallowed data is excluded;
  - every used artifact is written to the Decision Ledger.

### WH-142 — Deterministic trend/anomaly characterization

- Priority/size: P0 / L
- Owner: ML/Data
- Dependencies: WH-027, WH-140
- Acceptance:
  - characterizes change before LLM rendering;
  - handles coverage, source change and personal baseline;
  - thresholds are versioned and cannot independently diagnose.

### WH-143 — Wearable safety critic

- Priority/size: P0 / L
- Owner: ML + Clinical
- Dependencies: WH-008, WH-141, WH-142
- Acceptance:
  - blocks absence-as-normal, stale decisive use and source-switch artifacts;
  - requires symptom/clinical corroboration for material action;
  - prevents medicine changes from wearable data alone.

### WH-144 — Harness shadow evaluation

- Priority/size: P0 / L
- Owner: Evaluation + Clinical
- Dependencies: WH-143
- Acceptance:
  - compares no-wearable baseline, wearable-context candidate and expert rubric;
  - includes sparse, conflicting and misleading wearable scenarios;
  - no user-facing recommendation is released during shadow.

### WH-145 — Consumer pilot gate

- Priority/size: P0 / M
- Owner: Clinical Governance + Product
- Dependencies: WH-144
- Acceptance:
  - usefulness improves on the approved rubric;
  - critical safety is non-inferior;
  - subgroup/device bias review passes;
  - stop rules and incident owner exist.

### WH-146 — Research-mode provenance

- Priority/size: P1 / M
- Owner: Research + Backend
- Dependencies: WH-140
- Acceptance:
  - Research can reference user-authorized aggregate artifacts without treating
    consumer sensors as clinical measurements;
  - exports preserve source, device, interval and limitations;
  - raw data is excluded unless the user explicitly authorizes the research
    purpose.

## 12. Workstream J — Quality, security and release

### WH-160 — Threat model

- Priority/size: P0 / M
- Owner: Security
- Dependencies: WH-021, WH-023
- Acceptance:
  - covers malicious device payload, token theft, callback CSRF, replay,
    cross-profile access, log leakage and deletion bypass;
  - mitigations map to test cases.

### WH-161 — Property and fuzz tests

- Priority/size: P0 / L
- Owner: QA/Backend
- Dependencies: WH-031, WH-061
- Acceptance:
  - fuzzes malformed values, units, intervals, pages and cursor transitions;
  - no input can bypass profile/consent checks or create non-finite values.

### WH-162 — Performance and battery test

- Priority/size: P1 / M
- Owner: Mobile/Platform
- Dependencies: WH-045, WH-082, WH-092
- Acceptance:
  - initial/import incremental budgets are approved;
  - background work respects OS scheduling;
  - no continuous polling or unbounded sensor access exists.

### WH-163 — Connector incident runbooks

- Priority/size: P0 / M
- Owner: Platform + Support
- Dependencies: WH-068
- Deliverables:
  - vendor outage;
  - token/secret exposure;
  - schema drift;
  - duplicate aggregate;
  - revocation/deletion delay;
  - incorrect wearable-derived recommendation.
- Acceptance:
  - each runbook names detection, containment, user communication, rollback and
    post-incident evidence.

### WH-164 — Production smoke suite

- Priority/size: P0 / M
- Owner: QA/Release
- Dependencies: released provider gate
- Acceptance:
  - capability, connect, real import, freshness, LifeMap, pause, revoke and delete
    pass against production configuration;
  - no fake data endpoint is enabled.

### WH-165 — Rollback drill

- Priority/size: P0 / S
- Owner: Platform/Release
- Dependencies: WH-069, WH-163
- Acceptance:
  - provider reads and projections can be disabled independently;
  - revoke/delete remain operational;
  - ongoing imports stop safely without cursor corruption.

### WH-166 — Release evidence packet

- Priority/size: P0 / M
- Owner: Release Manager
- Dependencies: all P0 tasks for selected providers
- Acceptance:
  - includes vendor approvals, policy declarations, test reports, threat model,
    clinical review, E2E evidence, dashboards and rollback drill;
  - every parent FR-CON requirement has a passing evidence link;
  - release has explicit Product, Privacy, Security and Clinical sign-off.

## 13. Deferred Workstream K — Wear OS companion

### WH-180 — Watch-native outcome discovery

- Priority/size: P2 / M
- Owner: Product + Clinical
- Dependencies: consumer connector outcome data
- Acceptance:
  - identifies a problem that cannot be solved adequately through Health Connect;
  - defines target users, metric, frequency and action;
  - documents why watch collection provides net benefit.

### WH-181 — Wear OS intended use and battery budget

- Priority/size: P2 / M
- Dependencies: WH-180
- Acceptance:
  - selects Passive, Measure or Exercise client correctly;
  - establishes collection, latency and battery budgets;
  - receives clinical/privacy approval.

### WH-182 — Wear OS module

- Priority/size: P2 / XL
- Dependencies: WH-181
- Acceptance:
  - task is decomposed into watch UX, Health Services adapter, phone sync,
    offline behavior, device tests and release gates before implementation.

## 14. Milestones

### M0 — Gates and contracts ready

Required: WH-001..009, WH-020, WH-021, WH-031.

Exit:

- provider/data-type/purpose matrix approved;
- vendor access risks known;
- canonical contract frozen for MVP.

### M1 — Control plane and UX shell

Required: WH-022..030, WH-040..047, WH-060..071.

Exit:

- connector can be represented, consented, imported, paused, revoked and deleted;
- all operations pass profile isolation and no-fake-data checks.

### M2 — Health Connect internal release

Required: WH-080..087, WH-120..125.

Exit:

- real-device records reach LifeMap with correct provenance;
- overlapping steps and source changes do not create false trends;
- production flag awaits or has Play approval.

### M3 — Huawei Health internal release

Required: WH-090..097 and M1/M2 shared components.

Exit:

- real Huawei wearable path passes on Huawei and non-Huawei phones;
- background restrictions and overlap with Health Connect degrade honestly.

### M4 — Harness shadow

Required: WH-140..145, WH-160..166.

Exit:

- connected data improves approved user outcomes without worse critical safety;
- release evidence and rollback are complete.

### M5 — Fitbit optional release

Required: WH-100..106.

Exit:

- real OAuth, sync, refresh, revoke and delete pass;
- connector adds coverage not already adequately served through Health Connect.

## 15. Parent-requirement traceability

| Requirement | Primary tasks |
|---|---|
| FR-CON-001..003 | WH-002, WH-040..044 |
| FR-CON-004 | WH-002, WH-003, WH-080, WH-090 |
| FR-CON-005 | WH-020, WH-024, WH-082, WH-092, WH-102 |
| FR-CON-006 | WH-025, WH-045, WH-061, WH-083, WH-093, WH-103 |
| FR-CON-007..008 | WH-026, WH-027, WH-084, WH-094 |
| FR-CON-009 | WH-029, WH-064, WH-065, WH-124 |
| FR-CON-010 | WH-044, WH-063, WH-068, WH-095, WH-121 |
| FR-CON-011..012 | WH-008, WH-140..145 |
| FR-CON-013 | WH-003, WH-080, WH-087 |
| FR-CON-014 | WH-004, WH-005, WH-091, WH-097 |
| FR-CON-015 | WH-006, WH-100..106 |
| FR-CON-016 | WH-180..182 |

## 16. First implementation slice

Start in this order:

1. WH-001, WH-002, WH-004, WH-005 and WH-009;
2. WH-020, WH-021, WH-022 and WH-031;
3. WH-040, WH-041, WH-060 and WH-064;
4. WH-003, WH-080, WH-081 and WH-082;
5. WH-024..029, WH-045, WH-061..063;
6. WH-043, WH-044, WH-083, WH-084;
7. WH-086, WH-120..125;
8. WH-090..097;
9. WH-140..145 and release controls;
10. Fitbit only after its external gate and coverage decision.

This sequence produces a safe vertical Health Connect slice while Huawei vendor
access proceeds in parallel, without prematurely building Fitbit or Wear OS.


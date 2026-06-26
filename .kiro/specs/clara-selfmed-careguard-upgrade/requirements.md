# Requirements Document

## Introduction

This feature upgrades CLARA-Care's **Self-Medication (Tủ thuốc)**,
**Drug-Drug Interaction (DDI)**, and **CareGuard** capabilities from their
current working-prototype state to **fully functional, production-grade**
quality. It is **additive, feature-flagged, and back-compatible**: with every
new flag off the system behaves byte-for-byte as it does today, and every
existing medical-safety guardrail is preserved — no prescribing, no definitive
diagnosis, no personal-dosage output, the DDI **severity floor** (external
sources may only *raise* a curated severity, never lower it, and an openFDA-only
signal never overrides a curated Vietnamese message), and the **emergency
fast-path** that routes critical symptoms straight to seeking urgent care.

The work closes concrete gaps found in the current implementation:

- The medicine cabinet stores **brand and manufacturer inside a `[meta]` prefix
  packed into the free-text `note` column** (`_encode_item_note` /
  `_decode_item_note` in `endpoints/careguard.py`) instead of first-class
  columns; expiry, dosage form, and quantity are only partially editable from
  the web UI and have no reminders.
- The DDI rule matcher (`_detect_ddi_alerts` in `agents/careguard.py`) performs
  a **linear `issubset` scan over every rule**. That is fine for the ~100
  curated Vietnamese rules but does not scale to the **flag-gated DrugBank merge
  layer** (`CAREGUARD_DRUGBANK_ENABLED`), whose manifest declares ~1.43M rules;
  the bulk DrugBank shards are **license-restricted and provisioned out of band**
  via `scripts/data/drugbank_ingest.py`, so the system must provision, verify,
  and index them safely.
- The **severity floor** and the **openFDA-cannot-override-curated-message**
  invariants are enforced in code comments (INV-2/INV-3) but are not pinned by
  property tests.
- Offline / degraded behavior exists server-side (`fallback_used`,
  local-rules-only path) but there is **no client-side offline fallback** and no
  cached last-known DDI result on web or mobile.
- **Mobile parity** is partial: `careguard_screen.dart` runs a DDI check with
  the two-medicine guard, but the cabinet (CRUD, OCR import, timeline) lives
  only on web.
- **Observability** is limited to coarse product events
  (`trackCareguardViewed`, `trackCareguardDdiChecked`) and a `ddi_aggregation`
  analytics event; there are no per-source availability, fallback-rate,
  normalization-confidence, or latency metrics.
- **Test coverage** is uneven: API cabinet endpoints and the ML proxy are
  covered, but the ML DDI agent, the DrugBank merge precedence, the severity
  floor, and the End_User projection lack property-level tests.

CLARA-Care remains **decision-support software over self-declared data — not a
medical device, not an EMR/EHR, and not a prescriber.** Nothing here changes
that positioning. All user-facing copy is Vietnamese-first.

## Glossary

- **SelfMed / Tủ thuốc**: The personal medicine cabinet — the per-user list of medicines (`MedicineCabinet` + `MedicineItem`) plus its web surfaces under `apps/web/app/selfmed/*`.
- **DDI (Drug-Drug Interaction)**: A clinically relevant interaction between two or more distinct medicines.
- **CareGuard**: The medication-safety analysis feature (`apps/web/app/careguard`, `services/api/.../endpoints/careguard.py`, `services/ml/.../agents/careguard.py`) that runs DDI checks, allergy conflicts, and risk classification.
- **CareGuard_ML**: The deterministic ML agent `run_careguard_analyze` that resolves DDI rules, merges sources, classifies risk, and localizes messages.
- **CareGuard_API**: The API layer that owns cabinet CRUD, OCR scan/import, the `auto-ddi-check` orchestration, consent gating, and the ML proxy.
- **CareGuard_Web / CareGuard_Mobile**: The Next.js and Flutter clients.
- **Curated rules**: The hand-authored Vietnamese DDI rules in `careguard_ddi_rules.v1.json` (the authoritative, highest-precedence layer).
- **DrugBank layer**: The flag-gated (`CAREGUARD_DRUGBANK_ENABLED`) additive DDI/dictionary shards under `nlp/seed_data/drugbank/`, derived from the licensed DrugBank database by `scripts/data/drugbank_ingest.py`. **Lower precedence** than curated rules.
- **External sources**: RxNav/RxNorm and openFDA, consulted only when `EXTERNAL_DDI_ENABLED` is on and ≥2 distinct medicines are present.
- **Severity floor**: The invariant that merging a source's signal may only *raise* the severity of a medication pair, never lower it; and that an openFDA-only signal (severity inferred from free text, capped at `high`) never replaces a curated rule's Vietnamese message or downgrades it.
- **Emergency fast-path**: The behavior that critical symptoms (e.g. severe bleeding, chest pain) escalate the risk level and produce a "seek urgent care now" recommendation without diagnostic reasoning.
- **Severity rank**: `low(1) < medium(2) < high(3) < critical(4)`.
- **DDI user view**: The End_User projection (`toDdiUserView` in `lib/careguard.ts`) exposing only risk level, alerts, recommendations, and reference sources — dropping runtime `mode`, `fallback` flags, and `source_errors`.
- **Normalization**: Mapping a raw/brand medicine name to a canonical ingredient via the VN drug dictionary / `VnDrugMapping` (db → candidate → fallback) before rule matching.
- **Two-medicine guard**: A DDI check must not run for fewer than two *distinct* medicines (`requiresTwoMedicines` / `_minimumDdiMedicines`).
- **Feature flag**: A configuration switch enabling new behavior while defaulting to a state that preserves current behavior.

## Requirements

### Requirement 1: Production-Grade Medicine Cabinet CRUD and Structured Persistence

**User Story:** As a user, I want to add, view, edit, and delete the medicines in my cabinet with proper fields for brand, manufacturer, dosage, form, quantity, and expiry, so that my medicine list is accurate and durable.

#### Acceptance Criteria

1. THE SelfMed_System SHALL allow an authenticated user to create, read, update, and delete medicine-cabinet items scoped to their own cabinet.
2. WHERE `SELFMED_CABINET_STRUCTURED_FIELDS_ENABLED` is on, THE SelfMed_System SHALL persist `brand_name`, `manufacturer`, `dosage_form`, and `expires_on` as first-class structured fields rather than encoded inside the free-text `note`.
3. WHERE `SELFMED_CABINET_STRUCTURED_FIELDS_ENABLED` is off, THE SelfMed_System SHALL behave exactly as today, including the existing `[meta]` note encoding, so reads of pre-existing items are unchanged.
4. WHEN reading an item written under the legacy `[meta]` note encoding, THE SelfMed_System SHALL decode brand and manufacturer into the structured response fields without data loss.
5. WHEN a user attempts to add a medicine whose normalized name already exists in their cabinet, THE SelfMed_System SHALL reject the duplicate with a clear Vietnamese message and SHALL NOT create a second row.
6. THE SelfMed_System SHALL reject mutating requests from a user who is not the owner of the targeted cabinet item with an authorization error.
7. THE SelfMed_System SHALL validate quantity as a positive integer and SHALL reject malformed dosage or expiry input with a descriptive, PII-free error.

### Requirement 2: Robust Medicine Normalization and OCR Import

**User Story:** As a user, I want medicines I type or scan from a prescription to be matched to the right canonical drug, so that interaction checks are accurate.

#### Acceptance Criteria

1. THE SelfMed_System SHALL normalize each medicine name through the dictionary path (db match → candidate match → alias fallback) and SHALL record the normalization source and confidence on the item response.
2. WHEN an OCR scan produces a low-confidence detection (below the configured threshold), THE SelfMed_System SHALL require explicit per-item confirmation before that detection can be imported into the cabinet.
3. THE SelfMed_System SHALL bound OCR input size and reject oversized payloads with a descriptive error.
4. WHEN OCR text contains known noisy character substitutions, THE SelfMed_System SHALL apply deterministic correction before normalization.
5. WHERE a medicine cannot be confidently normalized, THE SelfMed_System SHALL retain the user-entered name as a fallback and SHALL mark it as "needs review" rather than dropping it.
6. THE SelfMed_System SHALL surface the normalization status (matched / needs review / manual) to the user in the cabinet UI.

### Requirement 3: DDI Check Correctness, Two-Medicine Guard, and End_User Projection

**User Story:** As a user, I want a clear, Vietnamese, non-technical interaction result whenever I have at least two medicines, so that I understand the risk and what to do next.

#### Acceptance Criteria

1. WHEN a user has fewer than two distinct medicines, THE CareGuard_System SHALL NOT run the DDI analysis and SHALL prompt the user to add at least two medicines.
2. WHEN a user has at least two distinct medicines, THE CareGuard_System SHALL detect all curated interaction pairs whose medications are a subset of the user's normalized medicine set.
3. THE CareGuard_System SHALL classify the overall result into a coarse risk level (low, medium, high, critical) derived from the detected alerts, critical symptoms, and lab flags.
4. THE CareGuard_System SHALL render to the End_User only the risk level, alerts, recommendations, and reference sources, and SHALL NOT surface runtime mode, fallback flags, connector identifiers, HTTP status detail, or `source_errors`.
5. THE CareGuard_System SHALL present alert messages and recommendations in Vietnamese, mapping recognized English passthrough interaction copy to its canonical Vietnamese equivalent.
6. WHERE no interaction is detected, THE CareGuard_System SHALL state clearly that no significant interaction was found while still advising clinician review.

### Requirement 4: DDI Severity Model, Severity Floor, and Source Merge

**User Story:** As a safety stakeholder, I want the most severe credible signal to win and curated Vietnamese guidance to be protected, so that interaction severity is never silently downgraded.

#### Acceptance Criteria

1. THE CareGuard_System SHALL merge interaction signals per medication pair, taking the maximum severity across curated, DrugBank, RxNav, and openFDA sources.
2. THE CareGuard_System SHALL NOT lower the severity of a medication pair below the highest severity asserted by any contributing source (the severity floor).
3. WHERE an openFDA-only signal exists for a pair (severity inferred from free text and capped at `high`), THE CareGuard_System SHALL NOT replace the curated Vietnamese message for that pair and SHALL NOT create a standalone alert for a pair that no curated or RxNav source raised.
4. THE CareGuard_System SHALL cap any severity inferred from free-text drug-label text at `high` and SHALL NOT infer `critical` from free text.
5. THE CareGuard_System SHALL record, per alert, the contributing source set for traceability without exposing it in the End_User projection.
6. THE CareGuard_System SHALL order alerts by descending severity.

### Requirement 5: Flag-Gated DrugBank Merge Layer — Provisioning, Integrity, and Scale

**User Story:** As an operator, I want to enable the licensed DrugBank interaction layer safely and at scale, so that coverage improves without breaking curated guidance or performance.

#### Acceptance Criteria

1. WHERE `CAREGUARD_DRUGBANK_ENABLED` is off, THE CareGuard_System SHALL NOT read the DrugBank directory and SHALL behave byte-for-byte identically to the curated-only path.
2. WHERE `CAREGUARD_DRUGBANK_ENABLED` is on, THE CareGuard_System SHALL merge DrugBank rules as a **lower-precedence** layer such that a curated rule always wins on a conflicting medication pair (both its severity and Vietnamese message preserved) and DrugBank only contributes pairs the curated set does not cover.
3. THE CareGuard_System SHALL load DrugBank shards from the manifest, cache them keyed by manifest mtime, and SHALL degrade to the curated-only path if the manifest or any shard is missing or unparseable.
4. WHERE `CAREGUARD_DDI_INDEX_ENABLED` is on, THE CareGuard_System SHALL match interaction pairs using a pair-indexed lookup whose result set is identical to the linear matcher, so that enabling the large DrugBank layer does not degrade per-check latency beyond the configured budget.
5. THE provisioning tooling SHALL record a manifest with version, source, license, generation timestamp, and per-shard counts, and THE CareGuard_System SHALL expose the active DDI rule-set version label in analysis metadata.
6. THE bulk DrugBank data SHALL be provisioned out of band (operator-run ingest from the licensed source) and SHALL NOT be required for the curated-only default to function.

### Requirement 6: Offline and Degraded-Mode Fallback

**User Story:** As a user, I want the interaction checker to keep working with local rules when external services or the network are unavailable, so that I always get a safe baseline answer.

#### Acceptance Criteria

1. WHEN external DDI sources are disabled, unavailable, or time out, THE CareGuard_System SHALL still return a result computed from the local curated (and, if enabled, DrugBank) rules.
2. THE CareGuard_System SHALL record internally whether a fallback/degraded path was used, without surfacing that flag in the End_User projection.
3. WHERE `CAREGUARD_OFFLINE_FALLBACK_ENABLED` is on and the client cannot reach the API, THE CareGuard_Web and CareGuard_Mobile SHALL display the last successfully retrieved DDI result labeled as "offline / không phải thời gian thực".
4. WHEN the local store of curated rules cannot be read, THE CareGuard_System SHALL fail closed for the affected analysis with a safe Vietnamese message and SHALL NOT emit a fabricated all-clear result.
5. THE CareGuard_System SHALL keep external-source latency bounded by the configured timeout and SHALL NOT let a slow external source block the local result beyond that budget.

### Requirement 7: Medical-Safety Guardrails Preservation

**User Story:** As a regulator, I want the upgrade to keep every clinical safety boundary intact, so that the product never crosses into prescribing or diagnosis.

#### Acceptance Criteria

1. THE CareGuard_System SHALL NOT output a prescription, a definitive diagnosis, or a personalized dosage instruction.
2. THE CareGuard_System SHALL preserve the emergency fast-path: a recognized critical symptom SHALL escalate the risk level and produce a "seek urgent care now" recommendation without diagnostic reasoning.
3. THE CareGuard_System SHALL continue to require acceptance of the medical disclaimer / consent before serving cabinet or interaction features.
4. THE CareGuard_System SHALL attach a "review with a licensed clinician" directive to interaction results, and SHALL hedge any output derived from self-declared PHR data.
5. THE CareGuard_System SHALL strip dosage units, counts, and route/form tokens during normalization so that dosage figures are never echoed back as advice.

### Requirement 8: Mobile Parity

**User Story:** As a mobile user, I want the same medicine-cabinet and interaction experience I have on the web, so that I can manage my medicines on my phone.

#### Acceptance Criteria

1. THE CareGuard_Mobile SHALL preserve the existing two-medicine guard and the Vietnamese End_User DDI projection.
2. WHERE `CAREGUARD_MOBILE_CABINET_ENABLED` is on, THE CareGuard_Mobile SHALL allow listing, adding, and deleting cabinet items against the same API as the web client.
3. WHERE `CAREGUARD_MOBILE_CABINET_ENABLED` is off, THE CareGuard_Mobile SHALL behave exactly as today (manual-entry DDI check only).
4. THE CareGuard_Mobile SHALL not surface runtime mode, fallback flags, or `source_errors` to the user.
5. THE CareGuard_Mobile SHALL gate cabinet and interaction features behind the same consent requirement as the web client.

### Requirement 9: Observability and Analytics (No-PII)

**User Story:** As an operator, I want metrics on interaction-check volume, source availability, fallback rate, and normalization quality, so that I can monitor and improve the feature.

#### Acceptance Criteria

1. THE CareGuard_System SHALL emit named product events for cabinet views, DDI checks, and imports carrying only coarse, non-PII aggregate signals (e.g. risk level, alert count, medicine count, surface).
2. THE CareGuard_System SHALL NOT include drug names, brands, free-text notes, or any user identifier value in telemetry payloads.
3. WHERE `CAREGUARD_OBSERVABILITY_ENABLED` is on, THE CareGuard_System SHALL record per-source usage, fallback rate, normalization confidence, active rule-set version, and per-check latency as no-PII metrics.
4. THE CareGuard_System SHALL suppress telemetry transmission when consent or credentials are absent.
5. THE CareGuard_System SHALL expose aggregate CareGuard metrics only to authorized admin roles.

### Requirement 10: Expiry Tracking and Reminders

**User Story:** As a user, I want to see which medicines are expired or expiring soon, so that I do not take unsafe medicine.

#### Acceptance Criteria

1. THE SelfMed_System SHALL compute, from `expires_on`, which cabinet items are expired and which expire within a configured window.
2. THE SelfMed_System SHALL surface expired and expiring-soon counts in the cabinet summary.
3. WHERE `SELFMED_EXPIRY_REMINDERS_ENABLED` is on, THE SelfMed_System SHALL persist and expose per-item expiry reminder state.
4. WHERE `SELFMED_EXPIRY_REMINDERS_ENABLED` is off, THE SelfMed_System SHALL behave exactly as today (read-only expiry display, no reminder persistence).
5. THE SelfMed_System SHALL treat a missing or unparseable `expires_on` as "no expiry data" without error.

### Requirement 11: Reliability, Test Coverage, and Quality Gates

**User Story:** As a maintainer, I want the upgraded paths covered by property and regression tests, so that the safety invariants cannot silently regress.

#### Acceptance Criteria

1. THE feature SHALL include property tests pinning the severity floor, the openFDA-message-protection invariant, the DrugBank merge precedence, the two-medicine guard, and the End_User projection's exclusion of technical fields.
2. THE feature SHALL include a flags-off regression test asserting that with every new flag off, the cabinet API, the ML analysis payload, and the response envelope are byte-equivalent to baseline.
3. THE feature SHALL include a test asserting the pair-indexed matcher returns the same alert set as the linear matcher over the same rule set.
4. THE feature SHALL include a no-PII guard test asserting CareGuard telemetry and metrics payloads contain no drug names or identifiers.
5. THE feature SHALL verify that a deletion of a cabinet item removes only the owner's targeted row and leaves other users' data untouched.

### Requirement 12: Guardrails, Back-Compatibility, and Privacy Preservation

**User Story:** As a platform operator, I want the upgrade to default safely and never regress existing behavior, so that adoption carries no clinical or operational risk.

#### Acceptance Criteria

1. THE CareGuard_System SHALL gate all new enforcing behavior behind feature flags whose defaults preserve current behavior.
2. WHERE all new flags are off, THE CareGuard_System SHALL behave equivalently to the pre-feature system.
3. THE CareGuard_System SHALL NOT introduce PII into any telemetry, log, or analytics surface.
4. THE CareGuard_System SHALL enforce RBAC/owner-scoping on cabinet, dictionary-admin, and metrics surfaces.
5. THE CareGuard_System SHALL preserve CSRF protection on cookie-authenticated mutating endpoints.
6. THE CareGuard_System SHALL preserve the existing consent gate, cross-border transfer guard, and PHR-reconciliation behavior on the `auto-ddi-check` path.

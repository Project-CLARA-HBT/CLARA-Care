# Requirements Document

Clara Scribe — Enterprise.

## Introduction

Clara Scribe is the ambient clinical-documentation surface of CLARA Care: a clinician
speaks (or uploads audio of) a patient encounter and Scribe produces a structured,
editable, signable clinical note (SOAP and other templates) with coding and
medication-safety assistance. The current implementation is a **batch** flow —
`POST /v1/scribe/transcribe` (audio → transcript via the DeepSeek/Whisper audio
endpoint) and `POST /v1/scribe/soap` (transcript → SOAP), persisted as
`ScribeSession` rows (transcript, soap_json, insights_json, status) with doctor-only
RBAC CRUD in `services/api/.../scribe.py`.

This spec brings Clara Scribe to **enterprise grade**, informed by the ambient-AI-scribe
market (Nuance DAX, Abridge, Suki, Freed, Heidi) and Vietnamese clinical reality
(PhoWhisper / Google STT V2 Chirp-3 for Vietnamese ASR; code-switching where Vietnamese
speech embeds English drug names). Scope: real-time/streaming transcription, speaker
diarization, explicit consent capture, encounter management, multi-template generation,
ICD-10 + medication coding assistance (reusing the RAG drug lexicon), a review→sign→export
workflow with a full audit trail, PII/safety guardrails, and analytics — all behind
feature flags defaulting to the current batch behavior, with property-tested correctness.

### Goals
- Reduce clinician documentation time per encounter while keeping the clinician the
  final author (assistive, never autonomous).
- Vietnamese-first, code-switching-aware transcription and note generation.
- Verifiable correctness: a signed note is immutable + audit-trailed; no note content
  is silently lost or fabricated.

### Non-Goals
- Autonomous diagnosis or prescribing (Scribe drafts; a licensed clinician signs).
- Full bidirectional EHR write-back in v1 (export-only; FHIR `DocumentReference` is a
  forward-looking interface, not a live integration commitment).

## Glossary
- **Encounter**: a single patient visit Scribe documents (patient ref, visit type, time).
- **Session**: the Scribe working unit for an encounter (`ScribeSession`); holds audio
  refs, transcript, generated note(s), status, audit.
- **ASR**: Automatic Speech Recognition (audio → text).
- **Diarization**: attributing transcript segments to distinct speakers (e.g.
  `clinician` vs `patient`).
- **Ambient mode**: passive real-time capture of the spoken encounter.
- **Template**: a note structure (SOAP, H&P, progress note, referral, VN bệnh án).
- **Note**: a generated, structured clinical document instance of a template.
- **Sign/Finalize**: clinician action that locks a note version as the official record.
- **Code-switching**: Vietnamese speech containing English tokens (drug/procedure names).
- **Degraded ASR**: a transcript segment the ASR could not produce with confidence; it
  is flagged, never silently dropped or hallucinated.

---

## Requirements

## Requirement 1: Streaming (ambient) transcription
**User Story:** As a clinician, I want the encounter transcribed live as I speak, so that I can see and trust the transcript forming in real time instead of waiting for a batch result.

#### Acceptance Criteria
1. WHEN `RAG_SCRIBE_STREAMING_ENABLED` is false THE Scribe service SHALL behave exactly as the current batch flow (`/v1/scribe/transcribe` + `/v1/scribe/soap`), so the legacy path is unchanged.
2. WHERE `RAG_SCRIBE_STREAMING_ENABLED` is true THE system SHALL expose a streaming transcription endpoint that accepts incremental audio and emits transcript segments over Server-Sent Events using the established event contract (`event: <type>` + `data: <json>`), reusing the chat-stream SSE conventions.
3. WHILE a streaming session is active THE endpoint SHALL emit at least the event types `partial` (interim text), `segment` (a finalized transcript segment), and a terminal `done` or `error` event.
4. WHEN an audio chunk cannot be transcribed THE system SHALL emit a `segment` flagged `degraded=true` (or omit it) and SHALL NOT emit fabricated text for that chunk.
5. IF the streaming ASR provider is unavailable THE system SHALL fall back to the batch transcription path and emit a terminal `error` event whose payload names the failure class (no raw provider internals).
6. THE streaming endpoint SHALL require the same authentication and clinician RBAC as the existing scribe routes.

## Requirement 2: Vietnamese-first ASR with code-switching + provider abstraction
**User Story:** As a Vietnamese clinician, I want accurate transcription of Vietnamese speech that contains English drug names, so that the note captures medications correctly.

#### Acceptance Criteria
1. THE ASR layer SHALL be an injectable provider seam (interface) with at least two implementations: the existing DeepSeek/Whisper audio client and one Vietnamese-capable provider (e.g. Google STT V2 Chirp-3 or a self-hosted PhoWhisper), selected by configuration without code changes at call sites.
2. WHERE Vietnamese is the configured/detected language THE ASR layer SHALL request Vietnamese transcription and SHALL preserve embedded English tokens (drug/procedure names) verbatim rather than transliterating them.
3. WHEN the configured ASR provider returns an error or empty result THE layer SHALL try the configured fallback provider before surfacing a failure.
4. THE ASR layer SHALL be import-safe (constructing it opens no socket) and SHALL never raise on provider failure — it returns an explicit empty/degraded result the caller handles.
5. THE selected provider, language, and degraded-segment count SHALL be recorded on the session metadata for observability.

## Requirement 3: Speaker diarization
**User Story:** As a clinician, I want the transcript to distinguish who said what (me vs the patient), so that the note attributes history to the patient and plan to me.

#### Acceptance Criteria
1. WHERE diarization is available from the ASR provider THE system SHALL attach a `speaker` label to each transcript segment from a bounded label set (e.g. `clinician`, `patient`, `other`).
2. WHEN diarization is unavailable THE system SHALL still produce a valid transcript with `speaker` set to `unknown`, and note generation SHALL proceed unaffected.
3. THE clinician SHALL be able to re-assign a segment's speaker label, and the change SHALL persist on the session.
4. Diarization labels SHALL never alter, drop, or reorder the underlying transcript text (a diarization pass is additive metadata only).

## Requirement 4: Consent capture (compliance)
**User Story:** As a compliance officer, I want explicit patient consent recorded before any encounter is recorded or transcribed, so that recording is lawful and auditable.

#### Acceptance Criteria
1. WHERE `RAG_SCRIBE_CONSENT_REQUIRED` is true THE system SHALL reject any transcription/streaming request for a session that has no recorded consent, returning a clear, non-PII error.
2. WHEN consent is captured THE system SHALL persist a consent record (method, captured_by, timestamp, scope) on the session and SHALL include it in the audit trail.
3. THE consent record SHALL be immutable once written; revocation SHALL be a new audit event, not an edit of the original record.
4. IF consent is revoked THE system SHALL stop further transcription for that session and SHALL flag the session accordingly.

## Requirement 5: Encounter + session management
**User Story:** As a clinician, I want each note tied to a structured encounter (patient, visit type, time), so that notes are organized and retrievable.

#### Acceptance Criteria
1. THE system SHALL allow creating a session bound to an encounter context (a patient reference, visit type, and encounter datetime), in addition to the current free-form session.
2. THE patient reference SHALL be stored as a non-PII opaque identifier or a redactable field consistent with the existing PII policy (no raw patient identifiers in analytics/telemetry).
3. THE system SHALL list a clinician's sessions filterable by status and SHALL paginate results (bounded page size).
4. Creating, reading, updating, listing, and deleting sessions SHALL remain clinician-RBAC-gated and owner-scoped (a clinician sees only their own sessions) exactly as today.

## Requirement 6: Multi-template note generation
**User Story:** As a clinician, I want to generate the note in the structure my specialty/workflow needs (SOAP, H&P, progress note, referral letter, Vietnamese bệnh án), so that the output fits how I document.

#### Acceptance Criteria
1. THE note generator SHALL support a configurable set of templates including at least SOAP (current), and SHALL be extensible to add a template without changing the generation call site.
2. WHEN a template is requested THE generated note SHALL contain exactly the sections that template declares, each section being a string (possibly empty) — no missing or extra top-level sections.
3. THE generator SHALL be deterministic in structure: for the same template the output object SHALL always have the same section keys regardless of transcript content.
4. WHEN the transcript is empty or unusable THE generator SHALL return the template's sections as empty strings (not fabricated clinical content) and flag the note as `insufficient_input`.
5. THE generated note SHALL never include content contradicting the transcript's medications/allergies where those are explicitly stated (no invented drugs/allergies).

## Requirement 7: Coding + medication-safety assistance
**User Story:** As a clinician, I want suggested diagnosis codes and medication checks derived from the note, so that coding and safety review are faster.

#### Acceptance Criteria
1. WHERE coding assistance is enabled THE system SHALL produce a list of suggested ICD-10 (and/or Vietnamese ICD) codes for the note, each with the text span that justified it; suggestions SHALL be advisory and clearly marked as requiring clinician confirmation.
2. THE medication extraction SHALL reuse the existing RAG drug lexicon / entity normalization to map mentioned drugs to normalized identifiers (RxCUI) where known, degrading gracefully to surface text when unknown.
3. WHERE extracted medications form a known interaction THE system SHALL surface the interaction via the existing CareGuard/DDI path as an advisory insight, never blocking note generation.
4. Coding and medication suggestions SHALL be additive metadata on the note and SHALL never modify the note's clinical text.
5. No suggestion SHALL be presented as a confirmed diagnosis or prescription (assistive-only guardrail).

## Requirement 8: Review → sign → finalize workflow with audit trail
**User Story:** As a clinician, I want to edit, sign, and finalize a note with a complete history of changes, so that the official record is trustworthy and defensible.

#### Acceptance Criteria
1. THE session SHALL have an explicit status lifecycle with allowed transitions only: `draft → in_review → signed → exported`, plus `amended` from `signed`; an invalid transition SHALL be rejected.
2. WHEN a note is `signed` THE signed note version SHALL be immutable; any subsequent change SHALL create a new `amended` version, preserving the signed version.
3. THE system SHALL record an append-only audit entry (actor, action, timestamp, from_status, to_status) for every status transition and every consent/diarization-override/edit event.
4. THE audit trail SHALL be readable by the owning clinician and SHALL never be editable or deletable via the API.
5. WHEN a clinician edits the transcript or note THE prior content SHALL remain recoverable (versioned), so no edit silently destroys earlier content.

## Requirement 9: Export
**User Story:** As a clinician, I want to export a finalized note (Markdown/DOCX/PDF, and a FHIR DocumentReference shape), so that it can leave the system for the record/EHR.

#### Acceptance Criteria
1. THE system SHALL export a note as Markdown and SHALL reuse the existing workspace DOCX export path for DOCX output.
2. THE export SHALL include the note's template sections, the encounter context, the signing clinician and sign timestamp, and required source/medical attribution.
3. WHERE FHIR export is enabled THE system SHALL produce a `DocumentReference`-shaped JSON for the signed note (interface only; no live EHR write in v1).
4. Exporting SHALL be permitted only for `signed`/`exported` notes; exporting a `draft` SHALL be rejected.

## Requirement 10: PII, safety, and observability
**User Story:** As a security/compliance owner, I want Scribe to redact PII from analytics, never autonomously prescribe, and emit safe telemetry, so that the feature is compliant and observable.

#### Acceptance Criteria
1. Analytics/telemetry emitted by Scribe SHALL contain no raw PII (patient names, identifiers, free-text transcript); only coarse, consented signals (counts, durations, status) consistent with the existing analytics PII guard.
2. THE Scribe generation prompts SHALL carry the same legal/medical guardrail as other CLARA surfaces (assistive, no autonomous prescribing/diagnosis); a guardrail violation SHALL degrade to a safe response.
3. THE system SHALL emit flow/telemetry events for the scribe pipeline stages (consent, transcription, diarization, note generation, coding, sign) reusing the existing flow-event mechanism so the process is observable in the UI.
4. Per-encounter time-saved, edit rate, and degraded-segment rate SHALL be derivable from persisted, non-PII session metadata for the analytics dashboard.

## Requirement 11: Feature-flagged, backward-compatible rollout
**User Story:** As an operator, I want every new Scribe capability behind a flag defaulting to today's behavior, so that I can roll out safely and roll back instantly.

#### Acceptance Criteria
1. Every new capability (streaming, diarization, consent-required, new templates, coding, sign-workflow, export, FHIR) SHALL be gated by an independent feature flag defaulting to off / legacy behavior.
2. WHEN all Scribe flags are off THE observable behavior SHALL be byte-for-byte the current batch transcribe + SOAP + CRUD behavior.
3. Flipping any flag off at runtime SHALL restore the prior behavior without data loss (existing sessions remain readable).

---

## Verification expectations (enterprise-grade)
- Property-based tests for the correctness invariants: template section-completeness (R6.2/6.3), transcript-preservation under diarization (R3.4), audit append-only + signed-immutability (R8.2/8.3), no-fabricated-text on degraded ASR (R1.4/2/6.4), and status-transition legality (R8.1).
- Unit + integration tests for ML (ASR seam, generator, coding), API (routes, RBAC, persistence, audit), and Web (streaming client, review/sign UI).
- All existing scribe tests SHALL continue to pass; the legacy path SHALL stay green with flags off.

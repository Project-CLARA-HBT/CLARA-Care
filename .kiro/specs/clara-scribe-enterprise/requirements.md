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

A second, deep-research-driven wave (informed by Nuance DAX, Abridge, Suki, Nabla,
Ambience, Heidi, Freed and clinical-documentation science) extends this baseline with
**transcript grounding / anti-hallucination verification** (every clinically significant
statement is traceable to a transcript span, ungrounded statements are flagged or
omitted), **structured clinical data extraction** (problems, medications, allergies,
vitals as provenance-linked structured metadata), **conservative coding-assist expansion**
(E/M visit-level and CPT/procedure suggestions with anti-upcoding bias), **note-quality
and documentation-efficiency metrics**, **ASR fairness / word-error-rate reporting**,
**structured FHIR `Composition` + `Encounter` export**, a **time-stamped addendum
workflow** distinct from amend, **specialty/macro template extensibility**, and a
**golden-set evaluation gate** for note generation. Every item is additive and
independently feature-flagged (flags off ⇒ byte-for-byte current behavior) and preserves
all existing guardrails.

### Goals
- Reduce clinician documentation time per encounter while keeping the clinician the
  final author (assistive, never autonomous).
- Vietnamese-first, code-switching-aware transcription and note generation.
- Verifiable correctness: a signed note is immutable + audit-trailed; no note content
  is silently lost or fabricated.
- Grounded by construction: clinically significant note statements are traceable to
  transcript spans; ungrounded statements are flagged or omitted, never presented as fact.
- Observable quality: structured extraction provenance, note-quality/efficiency metrics,
  and ASR word-error-rate are derivable from non-PII metadata and gated by evaluation.

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
- **Clinically significant statement**: a discrete factual assertion in a generated note
  that, if wrong, could affect care — a finding, diagnosis, medication, allergy, vital,
  procedure, or plan item (as opposed to boilerplate/section headings).
- **Grounding / Claim traceability**: a verifiable link from a note statement to one or
  more transcript spans that support it; a statement with at least one supporting span is
  `grounded`, otherwise `ungrounded`.
- **Transcript span**: a referenceable region of the transcript (segment id plus optional
  character offsets) used as evidence/provenance for an extracted item or note statement.
- **Claim verification (NLI)**: the pass that decides whether a transcript span entails,
  contradicts, or is neutral toward a note statement, reusing the CLARA Research / FIDES
  NLI-based claim-verification approach.
- **Ungrounded statement**: a note statement no transcript span supports; it is flagged
  `unverified` or omitted, and a critical safety statement (medication, allergy, dose,
  vital, diagnosis) that is ungrounded is never presented as fact.
- **Structured clinical data**: machine-readable problems, medications, allergies, and
  vitals extracted as fields (additive metadata), each carrying provenance to a transcript
  span; never alters the note clinical text.
- **Provenance**: the recorded source (transcript span id(s) and extraction method) for a
  structured item or grounded statement.
- **E/M code**: an Evaluation and Management visit-level code (e.g. office-visit level).
- **CPT code**: a Current Procedural Terminology procedure code.
- **Upcoding**: suggesting a higher-reimbursement code than the documented evidence
  defensibly supports; Scribe is biased against this (anti-upcoding).
- **PDQI-9**: the Physician Documentation Quality Instrument; here used as a structural
  completeness proxy (not a clinical-content judgement).
- **Edit rate**: the proportion of generated note text a clinician changes before signing.
- **WER**: Word Error Rate, the standard ASR accuracy metric; a confidence-based quality
  proxy may stand in where reference text is unavailable.
- **FHIR Composition**: a FHIR structured clinical document resource composed of typed
  sections (distinct from the existing `DocumentReference` pointer resource).
- **Addendum**: a time-stamped clinical note appended to a signed note without altering the
  signed version (distinct from an amend, which creates a new note version).
- **Macro / snippet**: a clinician-defined reusable text fragment insertable into a note.
- **Golden set**: a curated transcript→note evaluation dataset with expected structure used
  to gate note-generation regressions.

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

## Requirement 12: Transcript-grounded note with claim traceability (anti-hallucination)
**User Story:** As a clinician, I want every clinically significant statement in a generated note to be traceable to what was actually said, so that I can trust the note and never sign fabricated findings, medications, allergies, or vitals.

#### Acceptance Criteria
1. WHEN `RAG_SCRIBE_GROUNDING_ENABLED` is false THE Scribe service SHALL generate notes exactly as Requirement 6 defines, with no grounding metadata and no change to note clinical text.
2. WHERE `RAG_SCRIBE_GROUNDING_ENABLED` is true THE system SHALL run a verification pass that, for each clinically significant statement in a generated note, attaches a `grounded` or `ungrounded` indicator and the transcript span(s) supporting it, reusing the CLARA Research / FIDES NLI-based claim-verification approach.
3. WHERE `RAG_SCRIBE_GROUNDING_ENABLED` is true THE system SHALL classify a statement as `grounded` only when at least one transcript span entails the statement under the claim-verification pass, and SHALL classify it `ungrounded` otherwise.
4. IF a clinically significant statement is `ungrounded` THEN THE system SHALL flag the statement as `unverified` or omit it, and SHALL NOT present it as confirmed fact.
5. IF an `ungrounded` statement is a critical safety statement (medication, dose, allergy, vital, or diagnosis) THEN THE system SHALL NOT include the statement as an asserted fact in the generated note clinical text and SHALL surface it only as an `unverified` candidate requiring clinician confirmation.
6. THE grounding indicators and supporting transcript spans SHALL be additive metadata on the note version and SHALL never alter, drop, or reorder the note's existing section text or the transcript.
7. THE system SHALL expose, to the clinician in the review UI, a per-statement grounded/ungrounded indicator with access to the supporting transcript span(s).
8. THE per-note grounded-claim rate SHALL be recorded as non-PII session metadata for analytics and evaluation.

## Requirement 13: Structured clinical data extraction
**User Story:** As a clinician, I want problems, medications, allergies, and vitals pulled out as structured fields linked to what was said, so that coding, export, and reconciliation can use them without re-reading the whole note.

#### Acceptance Criteria
1. WHEN `RAG_SCRIBE_STRUCTURED_EXTRACTION_ENABLED` is false THE system SHALL NOT produce structured-extraction metadata and SHALL behave exactly as the current note flow.
2. WHERE `RAG_SCRIBE_STRUCTURED_EXTRACTION_ENABLED` is true THE system SHALL extract structured fields for at least problems, medications, allergies, and vitals from the transcript and/or generated note.
3. THE structured extraction SHALL attach, to each extracted item, its provenance: the transcript span(s) it derives from and the extraction method.
4. WHERE a medication is extracted THE system SHALL include its `RxCUI` when known, reusing the existing RAG drug lexicon / entity normalization, and SHALL degrade gracefully to surface text when the identifier is unknown.
5. THE structured-extraction output SHALL be additive metadata on the note version and SHALL NEVER alter, drop, or reorder the note's clinical text.
6. WHERE `RAG_SCRIBE_GROUNDING_ENABLED` is also true THE extracted items SHALL reuse the same transcript-span provenance model as the grounding pass (Requirement 12), so an item and its grounding reference the same span identifiers.
7. WHEN no item of a given type is present in the transcript THE system SHALL return an empty structured list for that type and SHALL NOT fabricate items.

## Requirement 14: Conservative coding-assist expansion (E/M + CPT, anti-upcoding)
**User Story:** As a clinician, I want suggested visit-level (E/M) and procedure (CPT) codes alongside ICD-10, justified by the note, so that coding is faster without ever over-coding what I actually documented.

#### Acceptance Criteria
1. WHEN `RAG_SCRIBE_EM_CPT_CODING_ENABLED` is false THE coding assistant SHALL behave exactly as Requirement 7 (ICD-10 + medication safety only).
2. WHERE `RAG_SCRIBE_EM_CPT_CODING_ENABLED` is true THE system SHALL suggest, in addition to ICD-10, an E/M visit-level code and any applicable CPT/procedure codes, each accompanied by the justifying note and/or transcript span.
3. THE E/M and CPT suggestions SHALL be advisory and SHALL require explicit clinician confirmation before they are treated as selected.
4. IF the documented evidence is insufficient to justify a higher E/M level THEN THE system SHALL suggest the lower defensible level and SHALL NOT auto-select a higher level (anti-upcoding).
5. THE system SHALL NOT finalize, submit, or auto-apply any E/M or CPT code without clinician confirmation.
6. WHERE the Vietnamese clinical/coding context differs from US ICD/E/M/CPT conventions THE system SHALL localize the suggestion set accordingly (Vietnamese-first, bilingual where applicable).
7. THE coding suggestions SHALL be additive metadata on the note version and SHALL never modify the note's clinical text.

## Requirement 15: Note-quality and documentation-efficiency metrics
**User Story:** As a clinical-informatics lead, I want note-quality and efficiency metrics derived from non-PII session metadata, so that I can monitor documentation impact without exposing patient data.

#### Acceptance Criteria
1. WHEN `RAG_SCRIBE_QUALITY_METRICS_ENABLED` is false THE system SHALL NOT compute or expose the metrics defined in this requirement.
2. WHERE `RAG_SCRIBE_QUALITY_METRICS_ENABLED` is true THE system SHALL derive, from non-PII session metadata, at least: edit rate (clinician edits vs generated text), time-saved estimate, degraded-ASR rate, grounded-claim rate, and a note-quality proxy based on PDQI-9-style structural completeness.
3. THE computed metrics SHALL contain no raw PII (no patient identifiers, no free-text transcript), consistent with the existing analytics PII guard.
4. THE system SHALL expose the metrics to the analytics dashboard via the existing analytics path.
5. THE note-quality proxy SHALL measure structural completeness only and SHALL NOT be presented as a clinical-accuracy judgement of the note content.
6. WHERE a metric's required input is unavailable (e.g. grounded-claim rate when grounding is disabled) THE system SHALL omit that metric rather than report a fabricated value.

## Requirement 16: ASR fairness / word-error-rate reporting
**User Story:** As a quality owner, I want transcription accuracy reported per language and, where available, per accent/speaker, so that quality disparities are observable and can feed evaluation.

#### Acceptance Criteria
1. WHEN `RAG_SCRIBE_WER_REPORTING_ENABLED` is false THE system SHALL NOT compute or surface word-error-rate reporting.
2. WHERE `RAG_SCRIBE_WER_REPORTING_ENABLED` is true THE system SHALL record a word-error-rate measurement, or a confidence-based quality proxy where reference text is unavailable, per language for each session.
3. WHERE per-accent or per-speaker information is available THE system SHALL additionally record the measurement broken down by accent and/or speaker label.
4. THE word-error-rate measurements SHALL be stored as non-PII session/evaluation metadata and SHALL contain no raw transcript text or patient identifiers.
5. THE word-error-rate reporting SHALL feed evaluation and analytics only and SHALL NOT block, gate, or alter a clinician's transcription or note workflow.

## Requirement 17: FHIR Composition + Encounter export
**User Story:** As an integration owner, I want a signed note exportable as a structured FHIR Composition plus an Encounter resource, so that it is interoperable as a structured clinical document, not just a document pointer.

#### Acceptance Criteria
1. WHEN `RAG_SCRIBE_FHIR_COMPOSITION_ENABLED` is false THE export SHALL behave exactly as Requirement 9 (Markdown/DOCX and, where its own flag is set, `DocumentReference`).
2. WHERE `RAG_SCRIBE_FHIR_COMPOSITION_ENABLED` is true THE system SHALL export a signed note as a FHIR `Composition` resource whose sections correspond to the note's template sections, in addition to the existing `DocumentReference`.
3. WHERE `RAG_SCRIBE_FHIR_COMPOSITION_ENABLED` is true THE system SHALL export a FHIR `Encounter` resource derived from the session's encounter context (visit type, encounter datetime, opaque patient reference).
4. THE exported `Composition` SHALL reference the signing clinician and sign timestamp and SHALL include required source/medical attribution, consistent with Requirement 9.2.
5. THE FHIR `Composition` and `Encounter` export SHALL be interface-only with no live EHR write in v1.
6. Exporting the FHIR `Composition`/`Encounter` SHALL be permitted only for `signed`/`exported` notes; exporting a `draft` SHALL be rejected.

## Requirement 18: Addendum workflow (distinct from amend)
**User Story:** As a clinician, I want to attach a time-stamped addendum to a signed note without changing the signed version, so that I can add later information while preserving the original signed record.

#### Acceptance Criteria
1. WHEN `RAG_SCRIBE_ADDENDUM_ENABLED` is false THE system SHALL expose only the existing amend (new-version) workflow of Requirement 8.
2. WHERE `RAG_SCRIBE_ADDENDUM_ENABLED` is true THE system SHALL allow a clinician to attach a time-stamped addendum (author, timestamp, text) to a `signed` note.
3. WHEN an addendum is attached THE signed note version SHALL remain byte-for-byte unchanged, preserving signed-note immutability (Requirement 8.2).
4. WHEN an addendum is attached THE system SHALL record an append-only audit entry for the addendum (actor, action, timestamp).
5. THE addendum workflow SHALL be distinct from amend: an addendum SHALL NOT create a new note version, and the existing amend semantics (new `amended` version) SHALL remain available and unchanged.
6. WHERE the note is exported THE export SHALL include the addendum(s) as a clearly demarcated, time-stamped section without altering the signed content.

## Requirement 19: Specialty and macro template extensibility
**User Story:** As a clinician, I want specialty-specific templates and my own text macros added through the templates registry, so that documentation fits my specialty without engineering changes.

#### Acceptance Criteria
1. WHEN `RAG_SCRIBE_SPECIALTY_TEMPLATES_ENABLED` is false THE note generator SHALL offer exactly the template set of Requirement 6.
2. WHERE `RAG_SCRIBE_SPECIALTY_TEMPLATES_ENABLED` is true THE system SHALL allow a specialty-specific template to be added via the templates registry without changing the generation call site (extending Requirement 6.1).
3. WHERE `RAG_SCRIBE_SPECIALTY_TEMPLATES_ENABLED` is true THE system SHALL allow a clinician to define text macros/snippets that can be inserted into a note.
4. WHEN a specialty template is selected THE generated note SHALL contain exactly the sections that template declares, preserving the structure-completeness guarantee of Requirement 6.2/6.3.
5. THE addition of a template or macro SHALL NOT alter the structure or output of any existing template.
6. Specialty templates and macros SHALL be Vietnamese-first and bilingual where applicable.

## Requirement 20: Note-generation evaluation gate
**User Story:** As a platform owner, I want a golden-set evaluation gate for note generation, so that regressions in structural completeness, grounding, fabrication, or coding precision are caught before release.

#### Acceptance Criteria
1. WHEN `RAG_SCRIBE_EVAL_GATE_ENABLED` is false THE evaluation gate SHALL NOT run and SHALL NOT affect runtime behavior.
2. WHERE `RAG_SCRIBE_EVAL_GATE_ENABLED` is true THE system SHALL provide an evaluation harness that runs note generation over a golden set and computes at least: structural completeness, grounded-claim rate, a no-fabrication check, and a coding-precision proxy.
3. WHEN the evaluation harness runs THE harness SHALL produce a pass/fail result against declared thresholds for each computed metric.
4. IF any declared threshold is not met THEN THE evaluation gate SHALL report failure so the regression can block release, mirroring the existing research quality-gate pattern.
5. THE evaluation harness SHALL use only non-PII golden-set data and SHALL emit no raw patient identifiers in its reports.
6. THE evaluation gate SHALL be an offline/CI quality gate and SHALL NOT alter the runtime note-generation behavior experienced by clinicians.

---

## Verification expectations (enterprise-grade)
- Property-based tests for the correctness invariants: template section-completeness (R6.2/6.3), transcript-preservation under diarization (R3.4), audit append-only + signed-immutability (R8.2/8.3), no-fabricated-text on degraded ASR (R1.4/2/6.4), and status-transition legality (R8.1).
- **Grounding / traceability (R12)**: for any generated note with grounding on, every clinically significant statement carries a grounded/ungrounded indicator; a statement is `grounded` only if a supporting transcript span entails it; no `ungrounded` critical safety statement (medication/dose/allergy/vital/diagnosis) appears as asserted fact; grounding metadata never mutates note text or transcript.
- **Structured-extraction provenance integrity (R13)**: every extracted item references a valid transcript span and method; extraction is additive (note clinical text byte-for-byte unchanged); absent item types yield empty lists (no fabricated items); medication items carry RxCUI when known and degrade to surface text otherwise.
- **Anti-upcoding (R14)**: when documented evidence supports only a lower E/M level, the suggested level is never higher than the defensible level; no E/M/CPT code is auto-selected/finalized without clinician confirmation; coding metadata never mutates note text.
- **FHIR Composition shape (R17)**: an exported `Composition` has exactly one section per template section and round-trips its section text; an `Encounter` resource is derived from encounter context; export is gated to `signed`/`exported` notes.
- **Addendum preserves signed (R18)**: attaching an addendum leaves the signed note version byte-for-byte unchanged, creates no new note version, and appends exactly one audit entry; export includes the addendum as a demarcated section.
- **Metrics/WER are PII-free (R15/R16)**: quality metrics and WER reports assert clean against the redaction projection (no transcript/patient identifiers); a metric with unavailable input is omitted, not fabricated.
- **Evaluation gate (R20)**: the harness computes structural completeness, grounded-claim rate, no-fabrication, and coding-precision proxy over the golden set and returns failure when any declared threshold is unmet; uses non-PII golden data; runtime behavior is unaffected by the gate.
- Unit + integration tests for ML (ASR seam, generator, coding, grounding/claim-verification pass, structured extraction, WER reporting), API (routes, RBAC, persistence, audit, addendum, FHIR Composition/Encounter export), and Web (streaming client, review/sign UI, per-statement grounded/ungrounded indicators).
- All existing scribe tests SHALL continue to pass; the legacy path SHALL stay green with flags off (including all new R12–R20 flags defaulting off ⇒ byte-for-byte current behavior).

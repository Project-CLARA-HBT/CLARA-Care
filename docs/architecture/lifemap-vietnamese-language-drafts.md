# LifeMap Vietnamese language drafts

`POST /api/v1/lifemap/v2/visit-preparation-drafts` is a feature-gated,
Vietnamese-first read endpoint for preparing a discussion with a health
professional. It is available only when `LIFEMAP_VIETNAMESE_DRAFTS_ENABLED`
is enabled.

The task-first web entry point is `/lifemap/visit-prep`. It first reads the
server-authoritative `lifemap_vietnamese_drafts` profile capability, then shows
one editable preparation step. The browser never persists the draft, health
records, or capability result. A user may copy the draft for their own visit,
but copy is not an export, a LifeMap command, or a confirmation action.

The endpoint resolves the caller's LifeMap profile scope and medical consent
before retrieving records. Its response contains only current revisions from
that profile. It returns a consumer summary, exact cited source text, and
editable questions to consider at a visit. The returned draft is not stored,
does not create an event or revision, and cannot confirm, change, or infer a
LifeMap truth state.

Safety boundary:

- Emergency wording takes the existing fast path and bypasses profile retrieval.
- Diagnosis, prescribing, and personal-dose requests are rejected by the
  existing legal guard before records are read.
- Plain-language copy is fixed. Any record wording included in a question is an
  exact source-revision copy and carries its evidence id.
- The response is explicitly non-medical-advice, draft-only, and requires user
  review. It directs a user with emergency symptoms to local emergency care.
- No generated draft is telemetry, an audit payload, a decision, or a command.

The generic LifeMap summary response also exposes `consumer_summary`. It has
the same revision ids and uncertainty flags as the underlying deterministic
summary, so presentation cannot mask a disputed, conflicting, or stale record.

Rollback: set `LIFEMAP_VIETNAMESE_DRAFTS_ENABLED=false`. The endpoint returns
the existing feature-disabled response and the web entry shows an unavailable
state; no migration or persisted data needs to be reverted.

## Free-text Capture drafts

`LIFEMAP_TEXT_DRAFT_EXTRACTION_ENABLED` is a separate, default-off switch for
the existing Universal Capture text entry point. With both this switch and
`LIFEMAP_CAPTURE_ENABLED` on, API sends a bounded (maximum 6,000-character)
note to the registry-owned `LIFEMAP_TEXT_DRAFT_EXTRACTION` task. That task is
currently routed to DeepSeek V4 Flash and may return at most five ordered,
non-overlapping Unicode offsets plus one closed category: `symptom`,
`medication`, `measurement`, `sleep`, or `care_note`.

The model cannot supply a rewritten phrase, diagnosis, dosage, confidence, or
truth state. API validates the checksum and offsets, reconstructs every phrase
from the original note, stores an internal `text_source` provenance row, and
exposes only `text_draft` candidates for review. Each draft has no confidence
score and remains editable, rejectable, and explicitly confirmable. Confirming
creates the existing `text` LifeMap event type with source span provenance;
the source row is never reviewable or confirmable.

Failures, an unavailable ML service, malformed output, a checksum mismatch,
or a note above the bound leave the legacy direct-text draft untouched. Nothing
is silently inferred or dropped. Roll back immediately by setting
`LIFEMAP_TEXT_DRAFT_EXTRACTION_ENABLED=false` in **both API and ML** and
restarting those services; already-created drafts and their append-only review
history remain intact.

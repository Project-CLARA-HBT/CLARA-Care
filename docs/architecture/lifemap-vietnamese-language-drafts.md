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

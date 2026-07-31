# LifeMap review-only model proposals

`POST /api/v1/lifemap/v2/review-findings/scan` remains a profile-scoped,
consent-gated, rule-first review surface. When both
`LIFEMAP_AI_REVIEW_FINDINGS_ENABLED=true` and
`LIFEMAP_REVIEW_MODEL_PROPOSALS_ENABLED=true`, the API may send a bounded
packet of current, active revisions from that same authorized profile to ML.

## Boundary

The API filters to current revisions before any ML request, removes groups that
cannot be compared, caps the packet at 24 records and refuses oversized source
payloads rather than truncating them. The packet contains only
`revision_id`, `field_key` and source `payload`; it contains no profile ID,
account ID, consent state, action or write instruction.

ML runs `ModelTask.LIFEMAP_REVIEW_PROPOSALS` through the typed registry. Its
V4 Flash contract permits JSON-only proposals for exactly two supplied revision
IDs in the same field, labelled only `possible_duplicate` or
`possible_conflict`. It cannot return an explanation, confidence, medical
recommendation, truth-state or action.

The API deterministically validates every returned pair against the exact
packet it sent. A valid result persists as a `model_proposal` finding with
`requires_human_resolution=true`; it is not a LifeMap event or revision.
`resolved`/`dismissed` actions remain append-only review actions and never
alter source facts, provenance or truth-state.

## Failure and rollback

The two feature flags default to `false`. If the ML service is disabled,
unavailable, returns malformed JSON, tries an unknown revision, or crosses
fields, the API accepts no model proposal and still persists deterministic rule
findings. No exception text, source payload or model response is logged or
shown to end users.

To roll back, set `LIFEMAP_REVIEW_MODEL_PROPOSALS_ENABLED=false` in both API
and ML service environments, then restart those services. Existing review
findings and their append-only human actions remain readable; no migration or
data deletion is required.

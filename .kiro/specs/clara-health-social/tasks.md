# Implementation Plan — CLARA Health Social Platform

Each task is additive and flag-gated. Stages map to the design's rollout plan. Check off in order; every stage must keep flags-off behavior byte-identical and preserve the medical guardrails.

- [ ] 1. Foundation: schema, flag, empty router
  - [ ] 1.1 Add `social_platform_enabled` (+ sub-flags) to API and ML config, default off.
  - [ ] 1.2 Alembic migration creating all `social_*` tables with reversible downgrade.
  - [ ] 1.3 Mount `/api/v1/social` router that returns 404 when the master flag is off.
  - [ ] 1.4 Property test: flag-off ⇒ routes 404, nav hidden, baseline unchanged.
  - _Requirements: 1, 12_

- [ ] 2. Consent + profiles
  - [ ] 2.1 `social_participation_v1` consent type; gate reused from `UserConsent`.
  - [ ] 2.2 `GET/PATCH /me/profile`, `GET /profiles/{handle}` with PHR-isolated serializer.
  - [ ] 2.3 Test: PHR fields unreachable via any social route; consent gates writes.
  - _Requirements: 2, 3, 10_

- [ ] 3. Communities (read + membership)
  - [ ] 3.1 Seed curated communities; `GET /communities`, `GET /communities/{id}`.
  - [ ] 3.2 `join`/`leave` with rate limit + audit.
  - _Requirements: 5_

- [ ] 4. Posts/comments/reactions + moderation gate
  - [ ] 4.1 ML `POST /v1/social/moderate` reusing legal guard + emergency + PII filter.
  - [ ] 4.2 Post/comment CRUD with pre-publish moderation and edit/delete.
  - [ ] 4.3 Reactions (helpful/relate/thanks), no public vanity counts.
  - [ ] 4.4 Guard-preservation tests: prescribing/dosing/diagnosis blocked; emergency escalates.
  - _Requirements: 4, 6, 7, 8_

- [ ] 5. Feed + discovery + follows
  - [ ] 5.1 Cursor feed (personalized w/ consent, else curated), Redis-cached.
  - [ ] 5.2 Follows; recency+relevance ranking (no engagement-maximizing signals).
  - _Requirements: 9, 11_

- [ ] 6. Reporting + moderation queue + audit
  - [ ] 6.1 `POST /reports`; auto-escalation thresholds.
  - [ ] 6.2 Role-gated moderation queue + actions; PII-free `social_moderation_audit`.
  - _Requirements: 7, 12, 13_

- [ ] 7. AI assistance
  - [ ] 7.1 `POST /posts/{id}/ask-clara` → guarded chat with thread context + disclaimer.
  - [ ] 7.2 `POST /posts/{id}/summary` → labeled AI thread summary via RAG.
  - _Requirements: 8, 14_

- [ ] 8. Web surfaces (`apps/web/app/community`)
  - [ ] 8.1 Feed + post detail + compose (consent + moderation states).
  - [ ] 8.2 Communities, profile, role-gated moderation views; collapsed telemetry.
  - [ ] 8.3 Vitest + property tests for gating.
  - _Requirements: 4-9, 12_

- [ ] 9. Mobile surfaces (`apps/mobile/.../redesign`)
  - [ ] 9.1 Feed, post detail, compose sheet, community list, profile via `ApiClient`.
  - [ ] 9.2 Reuse disclaimer, offline guard, no-PII analytics, glass/tokens.
  - [ ] 9.3 Widget tests incl. fail-closed + consent/moderation states.
  - _Requirements: 4-9, 12_

- [ ] 10. Observability + limits + docs
  - [ ] 10.1 No-PII metrics (counts/distributions), rate limits, admin config.
  - [ ] 10.2 Update CLAUDE.md, README, nav config, onboarding path.
  - _Requirements: 11, 12, 13_

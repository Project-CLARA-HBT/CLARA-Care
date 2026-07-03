# Design Document — CLARA Health Social Platform

## Overview

The social layer is a new, flag-gated vertical that follows CLARA's existing request path
(**Web/Mobile → API `/api/v1/social/*` → ML internal**) and reuses every existing safety
mechanism rather than inventing parallel ones. It stores its own relational entities in
PostgreSQL (via Alembic), reuses Redis for rate limiting and feed caching, and calls the
guarded ML endpoints for the AI moderation gate and "ask CLARA" assistance.

Design principles:

1. **Safety reuse over reinvention.** The legal hard-guard, emergency fast-path, FIDES,
   consent, RBAC, CSRF, and no-PII telemetry are consumed as-is. The social layer adds a
   moderation gate on top; it never bypasses the medical guardrails.
2. **Fail closed.** Master flag off ⇒ routes 404, nav hidden, baseline behavior unchanged.
   Consent absent ⇒ read-only curated content, writes rejected.
3. **PHR isolation.** The public social profile and the private PHR share no fields and no
   routes. This is a hard boundary enforced at the schema and serializer level.
4. **Anti-doomscroll by design.** No public like counts / follower leaderboards; recency +
   relevance ranking, not outrage-maximizing engagement.

## Architecture

```
Social_Web (Next.js, apps/web/app/community)
Social_Mobile (Flutter, apps/mobile/.../redesign)
        │  /api/v1/social/*  (cookie+bearer, CSRF, RBAC, consent)
        ▼
CLARA_API (FastAPI)
   social router ── posts · comments · reactions · communities ·
   │                profiles · feed · reports · moderation
   │  internal (X-ML-Internal-Key)
   ▼
CLARA_ML (FastAPI)
   /v1/social/moderate   ── content-safety + medical-advice gate (reuses legal guard,
   │                          emergency detector, PII filter)
   /v1/chat/routed        ── existing guarded chat for "ask CLARA about this"
   (AI thread summary uses the RAG pipeline with thread + retrieved sources)

PostgreSQL: social_* tables   Redis: rate limits + feed cache
```

### Why this shape

- The API gateway already owns auth/RBAC/consent/rate-limit/CSRF, so the social router slots
  in beside `chat`, `careguard`, `council`, etc. under the same `/api/v1` prefix.
- Moderation and AI assistance are ML concerns, so they live behind `X-ML-Internal-Key`,
  reusing the exact guard/emergency/PII code paths that protect chat. This guarantees the
  social layer can never be a softer path around the medical guardrails.

## Components and Interfaces

### API router (`services/api/src/clara_api/api/v1/endpoints/social.py`)

Prefix `/api/v1/social`. All mutating routes: `require_roles`, CSRF (cookie auth), consent
gate, rate limit.

- `GET  /feed?cursor=` — personalized (consented) or curated feed.
- `POST /posts` · `GET /posts/{id}` · `PATCH /posts/{id}` · `DELETE /posts/{id}`
- `POST /posts/{id}/comments` · `GET /posts/{id}/comments?cursor=`
- `PATCH /comments/{id}` · `DELETE /comments/{id}`
- `POST /posts/{id}/reactions` · `DELETE /posts/{id}/reactions/{type}` (and comment variants)
- `GET  /communities` · `GET /communities/{id}` · `POST /communities/{id}/join` · `.../leave`
- `GET  /profiles/{handle}` · `GET /me/profile` · `PATCH /me/profile`
- `POST /reports` · (moderation) `GET /moderation/queue` · `POST /moderation/{id}/action`
- `POST /posts/{id}/ask-clara` — proxies to ML guarded chat with thread context.
- `POST /posts/{id}/summary` — AI thread summary (labeled, disclaimered).

### ML moderation endpoint (`services/ml/.../main.py`)

- `POST /v1/social/moderate` (internal): input `{text, kind}`; output
  `{decision: allow|block|warn, categories: [...], emergency: bool, pii_spans: [...]}`.
  Reuses `_detect_legal_guard_violation`, the emergency keyword detector, `redact_pii`, and
  the content-safety classifier. Deterministic-first, LLM-assisted where configured.

### Web (`apps/web/app/community/`)

`page.tsx` (feed), `[postId]/page.tsx` (detail), `compose/`, `communities/`,
`profile/[handle]/`, `moderation/` (role-gated). Reuses `http-client`, auth store,
`EndUserSafeAnswer`-equivalent renderer, and the existing `TelemetryPanel` (collapsed).

### Mobile (`apps/mobile/lib/experience/redesign/`)

`social_feed_screen.dart`, `social_post_detail.dart`, `social_compose_sheet.dart`,
`community_list_screen.dart`, `social_profile_screen.dart`. Wired via `ApiClient` with new
`social*` methods; reuses `ResearchTelemetryPanel`, standing disclaimer, offline guard,
no-PII analytics, and glass/token design system.

## Data Models (PostgreSQL, Alembic)

```
social_profiles(id, user_id FK unique, handle unique, display_name, avatar_url, bio,
                visibility enum(public|communities|private), is_expert bool,
                created_at, updated_at)
social_communities(id, slug unique, name, description, topic, is_active, created_at)
social_community_members(community_id FK, user_id FK, role enum(member|mod), joined_at,
                         PK(community_id,user_id))
social_posts(id, author_user_id FK, community_id FK nullable, type enum(question|experience|tip),
             title, body, tags jsonb, linked_answer jsonb nullable,
             moderation_state enum(pending|published|hidden|removed), edited bool,
             created_at, updated_at)
social_comments(id, post_id FK, parent_comment_id FK nullable, author_user_id FK, body,
                moderation_state, edited bool, created_at, updated_at)
social_reactions(id, target_type enum(post|comment), target_id, user_id FK,
                 type enum(helpful|relate|thanks), created_at, unique(target,user,type))
social_reports(id, target_type, target_id, reporter_user_id FK, reason enum, note,
               status enum(open|actioned|dismissed), created_at)
social_moderation_audit(id, actor_ref opaque, action, target_type, target_id, meta jsonb,
                         created_at)
social_follows(follower_user_id FK, followee_user_id FK, created_at, PK(both))
social_consent → reuse UserConsent with consent_type='social_participation_v1'
```

PHR isolation: no FK or column references any `phr_*` table; serializers whitelist fields.

## Moderation Flow

```
compose → POST /posts → API consent+RBAC+rate-limit ok
   → ML /v1/social/moderate
        block  → 422 with reason + standing guidance (+ emergency escalation if detected)
        warn   → publish with warning label / PII redaction offer
        allow  → moderation_state=published
   → feed cache invalidate
report → social_reports → threshold/auto-escalate → moderation queue → mod action → audit
```

Two configurable modes: **pre-publish gate** (block before visible) or **optimistic +
post-hoc** (publish then remove within a bounded window). Default: pre-publish for new
low-reputation accounts, optimistic for expert accounts.

## Error Handling

- Flag off → 404 (indistinguishable from a non-existent route).
- Consent absent → 403 on write, curated-only on read.
- ML moderation unavailable → fail closed (queue as pending, not auto-publish) in pre-publish
  mode; in optimistic mode, publish and flag for mandatory human review.
- Rate-limit exceeded → 429 with retry hint.

## Testing Strategy

- **Flags-off equivalence**: routes 404, nav hidden, baseline byte-identical (property test).
- **Guard preservation**: prescribing/dosing/diagnosis content in posts/comments is blocked;
  emergency content triggers escalation; PII is detected — reuse the ML guardrail suites.
- **Consent gating**: writes rejected without consent; personalized feed suppressed.
- **RBAC/moderation**: only doctor/admin (or community mods) can act; audit is PII-free.
- **PHR isolation**: assert no PHR field is reachable via any social route.
- **No-PII telemetry**: metrics carry only counts/distributions.
- Web: Vitest + property tests for feed/compose/moderation gating.
- Mobile: widget tests for feed, compose (consent + moderation states), profile, fail-closed.

## Rollout Plan

1. Migrations + flag (off) + empty router returning 404.
2. Profiles + communities (read).
3. Posts/comments/reactions + moderation gate (pre-publish).
4. Feed + discovery + follows.
5. Reporting + moderation queue + audit.
6. AI assistance (ask CLARA / summaries).
7. Mobile parity.
8. Observability + rate limits.
Each stage ships behind its sub-flag; enable incrementally per environment.

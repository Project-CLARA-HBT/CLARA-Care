# Requirements Document — CLARA Health Social Platform

## Introduction

This feature adds a **safety-first health social layer** to CLARA-Care, integrated across
both `apps/web` (Next.js) and `apps/mobile` (Flutter) and backed by the existing FastAPI
gateway (`services/api`). The goal is to let users learn from and support each other around
health topics — questions, experiences, curated communities, and expert-verified content —
**without ever becoming a channel for unlicensed medical advice, misinformation, or PII
leakage**.

This is **additive, feature-flagged, and back-compatible**. All new behavior defaults OFF
(`SOCIAL_PLATFORM_ENABLED=false`) and preserves every existing safety invariant: RBAC,
versioned medical consent, the legal hard-guard (no prescribing/diagnosis/personal dosing),
the emergency fast-path, FIDES verification, no-PII telemetry, and CSRF on cookie-auth
mutations. The social layer reuses the standard request path (Web/Mobile → API `/api/v1/*`
→ ML internal), and any AI assistance (summaries, moderation, "ask CLARA about this post")
routes through the existing guarded ML endpoints.

CLARA remains a clinical decision-support assistant, not a doctor. The social layer is
explicitly positioned as **peer support and health literacy**, not medical care. Every
surface that could be read as advice carries the standing disclaimer and routes urgent
situations to the emergency fast-path. The UI is Vietnamese-first with bilingual vi/en copy.

## Glossary

- **Social_System**: The backend service + data layer storing posts, comments, reactions, communities, follows, reports, and moderation state.
- **Social_Web**: The web social interface under `apps/web/app/community` (new).
- **Social_Mobile**: The mobile social screens under `apps/mobile/lib/experience/redesign` (new).
- **Post**: A user-authored health-topic entry (question, experience, or tip) with title, body, optional tags, and optional linked CLARA answer.
- **Comment**: A threaded reply to a post or another comment.
- **Reaction**: A lightweight, non-numeric-pressure signal of support (e.g. "hữu ích" / helpful, "đồng cảm" / relate). No public follower/like leaderboards.
- **Community**: A moderated topic space (e.g. "Tiểu đường", "Sức khỏe tinh thần", "Chăm sóc người cao tuổi") a user can join.
- **Expert badge**: A verified marker on accounts whose clinical role (`doctor`) has been validated; only badged accounts may post in "expert" content lanes.
- **Moderation queue**: The admin/mod surface for reviewing reported or auto-flagged content.
- **AI moderation gate**: An ML pass that screens new posts/comments for disallowed medical advice, dangerous instructions, PII, spam, and hate/harassment before they go live or by post-hoc flagging.
- **Health graph**: The follow/community-membership relationships used to build a user's feed.
- **User profile (social)**: The public-facing, user-controlled profile (display name, avatar, bio, optional role badge, communities) — distinct from the private PHR.
- **Feature flag**: `SOCIAL_PLATFORM_ENABLED` (master) plus per-capability sub-flags.

## Requirements

### Requirement 1: Feature Flag & Fail-Closed Rollout

**User Story:** As a platform operator, I want the entire social layer behind a master flag defaulting off, so that it ships dark and can be enabled per environment without affecting existing behavior.

#### Acceptance Criteria

1. THE Social_System SHALL expose a master feature flag `SOCIAL_PLATFORM_ENABLED` defaulting to false.
2. WHERE `SOCIAL_PLATFORM_ENABLED` is false, THE Social_System SHALL return HTTP 404 for all `/api/v1/social/*` routes and SHALL NOT surface any social navigation entry on web or mobile.
3. WHERE `SOCIAL_PLATFORM_ENABLED` is false, THE existing API/ML/web/mobile behavior SHALL be byte-for-byte equivalent to the pre-feature baseline.
4. THE Social_System SHALL gate each major capability (posting, communities, direct follow, AI summary) behind its own sub-flag so capabilities can be enabled incrementally.

### Requirement 2: Consent & RBAC

**User Story:** As a user, I want to explicitly opt in before I can participate socially, so that my public activity is always something I chose.

#### Acceptance Criteria

1. WHEN a user first opens any social surface, THE Social_System SHALL require a versioned social-participation consent (distinct from medical consent) before any read of the personalized feed or any write.
2. IF social-participation consent is absent, THEN THE Social_System SHALL reject write actions with a descriptive error and SHALL show only public, non-personalized content on read surfaces.
3. THE Social_System SHALL enforce `require_roles(...)` on all mutating routes and SHALL treat `admin` as having implicit moderator access.
4. WHEN a user revokes social-participation consent, THE Social_System SHALL hide their profile from discovery and stop building a personalized feed on subsequent requests, without deleting their prior content unless deletion is separately requested.
5. THE Social_System SHALL enforce CSRF protection on all cookie-authenticated mutating social requests.

### Requirement 3: Safety Guardrails on User Content

**User Story:** As a user and as a platform, I want every post and comment screened so the community never becomes a channel for dangerous medical advice or abuse.

#### Acceptance Criteria

1. WHEN a user submits a post or comment, THE Social_System SHALL run it through the AI moderation gate before it becomes publicly visible OR SHALL publish optimistically and remove within a bounded window on a failed gate, per the configured moderation mode.
2. IF content contains a personal prescribing/dosing directive to another user (e.g. "uống X mg mỗi ngày"), THEN THE AI moderation gate SHALL block it and SHALL surface the standing "CLARA does not prescribe" guidance.
3. IF content matches the emergency acute-symptom detector, THEN THE Social_System SHALL surface the emergency fast-path escalation to the author immediately, in addition to normal posting.
4. THE AI moderation gate SHALL screen for PII (names, phone numbers, national IDs, addresses, emails) and SHALL warn the author and offer redaction before publishing.
5. THE Social_System SHALL screen for hate/harassment and disallowed content per the platform content-safety policy and SHALL block on match.
6. THE Social_System SHALL exclude all free-text content and PII from telemetry, emitting only counts/distributions.
7. WHERE content is medical in nature, THE Social_System SHALL attach the standing decision-support disclaimer to the rendered view.

### Requirement 4: Posts, Comments, Reactions

**User Story:** As a user, I want to ask questions and share experiences, and respond to others, so that I can learn and give support.

#### Acceptance Criteria

1. THE Social_System SHALL let a consented user create a Post with a title, body, an optional post type (question | experience | tip), and optional tags.
2. THE Social_System SHALL let a consented user comment on a Post and reply to a Comment (threaded).
3. THE Social_System SHALL let a consented user add or remove a support Reaction on a Post or Comment, and SHALL NOT display competitive vanity metrics that pressure engagement.
4. THE Social_System SHALL let an author edit or delete their own Post or Comment, recording an edit indicator, and SHALL let a moderator remove any content.
5. WHEN a Post links a CLARA answer, THE Social_System SHALL render it through the End_User-safe answer view with the technical-detail panel collapsed.
6. THE Social_System SHALL paginate feeds and comment threads.

### Requirement 5: Communities

**User Story:** As a user, I want topic communities, so that I can find relevant peers and content.

#### Acceptance Criteria

1. THE Social_System SHALL provide curated, admin-managed Communities with a name, description, and topic.
2. THE Social_System SHALL let a consented user join and leave a Community.
3. WHERE a user is a member, THE Social_System SHALL include that community's content in the user's personalized feed.
4. THE Social_System SHALL scope a Post to at most one Community or to the general feed.
5. THE Social_System SHALL let a Community have assigned moderators (doctor/admin) whose removals are scoped to that community.

### Requirement 6: Social Profile & Expert Verification

**User Story:** As a user, I want a public profile distinct from my private health record, and I want to trust that "expert" content comes from verified clinicians.

#### Acceptance Criteria

1. THE Social_System SHALL provide a public social profile with a user-controlled display name, avatar, and short bio, storing NO PHR/medical data on it.
2. THE Social_System SHALL keep the social profile strictly separate from the PHR; no PHR field SHALL be exposed through any social route.
3. WHERE an account's role is verified as `doctor`, THE Social_System SHALL display an expert badge and SHALL allow that account to post in expert-only content lanes.
4. IF an unverified account attempts to post in an expert-only lane, THEN THE Social_System SHALL reject the action with a descriptive error.
5. THE Social_System SHALL let a user control profile visibility (public | communities-only | private).

### Requirement 7: Feed & Discovery

**User Story:** As a user, I want a relevant, safe feed, so that I see useful health content without doomscrolling or misinformation amplification.

#### Acceptance Criteria

1. THE Social_System SHALL build a personalized feed from the user's joined communities and followed accounts, plus curated/expert content.
2. THE Social_System SHALL rank the feed by recency and relevance, and SHALL NOT optimize for engagement-maximizing outrage signals.
3. THE Social_System SHALL provide topic/tag search over public content.
4. THE Social_System SHALL de-rank or hide content that failed or is pending the moderation gate.
5. WHERE the user has not consented to personalization, THE Social_System SHALL show a non-personalized curated feed only.

### Requirement 8: Reporting & Moderation

**User Story:** As a user and moderator, I want to report and act on harmful content, so that the community stays safe.

#### Acceptance Criteria

1. THE Social_System SHALL let any user report a Post or Comment with a reason category.
2. WHEN content is reported, THE Social_System SHALL enqueue it in the moderation queue and SHALL notify assigned moderators.
3. THE Social_System SHALL let a moderator hide, remove, or restore content and warn or suspend an author, recording each action in an immutable audit log.
4. THE Social_System SHALL auto-escalate content that crosses configurable report thresholds.
5. THE moderation audit log SHALL exclude PII and SHALL reference actors by opaque IDs.

### Requirement 9: AI Assistance (guarded)

**User Story:** As a user, I want CLARA to help me understand a post safely, so that I get grounded context, not amplified misinformation.

#### Acceptance Criteria

1. THE Social_System SHALL offer an "ask CLARA about this" action on a Post that routes through the existing guarded ML chat endpoint with the legal hard-guard and emergency fast-path intact.
2. THE Social_System SHALL offer optional AI thread summaries that are clearly labeled as AI-generated and carry the standing disclaimer.
3. THE AI assistance SHALL never generate a personal prescription, diagnosis, or dosing directive; the legal hard-guard SHALL apply identically to social AI calls.
4. THE Social_System SHALL ground AI summaries only in the thread content plus retrieved authoritative sources, and SHALL surface source attribution in the technical-detail panel.

### Requirement 10: Web & Mobile Parity

**User Story:** As a user on either platform, I want the same core social capability, so that my experience is consistent.

#### Acceptance Criteria

1. THE Social_Web SHALL provide feed, post detail, compose, community list/detail, profile, and moderation (role-gated) surfaces under `apps/web/app/community`.
2. THE Social_Mobile SHALL provide feed, post detail, compose, community list/detail, and profile surfaces wired to the same `/api/v1/social/*` API.
3. Both clients SHALL reuse the shared End_User-safe answer view, standing disclaimer, offline guard (mobile), and no-PII analytics.
4. Both clients SHALL fail closed when the master flag or consent is absent.

### Requirement 11: Data, Privacy & Retention

**User Story:** As a user, I want control over my social data, so that my privacy is respected.

#### Acceptance Criteria

1. THE Social_System SHALL persist social entities via Alembic migrations with reversible downgrades; no runtime `create_all`.
2. THE Social_System SHALL let a user delete their own content and their social profile, and SHALL cascade or anonymize per policy.
3. THE Social_System SHALL not expose any user's PHR, email, or auth identifiers through social routes.
4. THE Social_System SHALL store minimal profile data and SHALL support export of a user's own social content.

### Requirement 12: Observability & Rate Limiting

**User Story:** As an operator, I want the social layer observable and abuse-resistant, so that it stays healthy.

#### Acceptance Criteria

1. THE Social_System SHALL rate-limit posting, commenting, and reporting per user via the existing limiter (Redis-backed when distributed limiters are enabled).
2. THE Social_System SHALL emit no-PII metrics: post/comment/report counts, moderation outcomes distribution, feed latency percentiles.
3. THE Social_System SHALL surface moderation-queue depth and gate outcomes to the admin observability surface.

# LifeMap current-state inventory

Date: 2026-07-28

This inventory records the production foundation currently deployed. “Dark”
means implemented but unavailable because its server-authoritative flag remains
off. Production usage is based on the deployed route/container/configuration,
not a claim of clinical adoption.

| Area | Canonical implementation | Owner | Production status | Verification |
| --- | --- | --- | --- | --- |
| Profile scope | `lifemap/profile_scope.py` | API/Security | Active for LifeMap V2-compatible routes | Two-profile and grant tests |
| Truth/task commands | `lifemap/domain.py`, `lifemap/commands.py` | API/Clinical Safety | Active compatibility floor | Transition/idempotency tests |
| LifeMap HTTP API | `endpoints/lifemap.py` | API | Active; V2 expansions dark | API regression and authenticated smoke |
| Insights/questions | `endpoints/lifemap_insights.py` | API/Clinical Safety | Existing routes active; V2 flags dark | Focused API tests |
| Family integration | `endpoints/family.py`, `lifemap/visit_family_service.py` | API/Privacy | Existing grants active | Authorization tests |
| Evidence integration | `endpoints/evidence_questions.py` | API/Research | Existing route active | Evidence tests |
| Canonical schema | `db/models.py`, migration `20260728_0030` | API/Data | Production migration head | Reconciliation and migration rehearsal |
| Outbox worker | `lifemap/worker.py`, `lifemap/outbox_relay.py` | Platform/API | Active standalone container | Health, concurrency, soak, recovery tests |
| Outbox operations | `/lifemap/admin/outbox/*` | Platform/Security | Active, admin-only | RBAC/audit/no-PII tests |
| Web Today/LifeMap | `apps/web/app/today`, `apps/web/app/lifemap` | Web/Product | Active authenticated surfaces | Unit/build/E2E |
| Mobile unified shell | `apps/mobile/lib/experience` | Mobile/Product | Active release path | Analyze, tests, release APK |
| Council heuristic | `services/ml/.../council_neural.py` | ML/Clinical Safety | Shadow heuristic only | ML regression |
| LifeMap V2/AI flags | `core/config.py`, profile/mobile capabilities | API/Product | All 16 new flags dark | Configuration/capability tests |

## Canonical tables

- Existing: `phr_profiles`, `lifemap_events`, `lifemap_episodes`,
  `lifemap_care_tasks`, `lifemap_decision_ledger`,
  `lifemap_outbox_events`.
- V2 additive: `health_source_references`, `lifemap_event_revisions`,
  `lifemap_task_actions`, `lifemap_command_records`,
  `lifemap_projection_dependencies`.
- Every V2 identifier exposed to clients is opaque. Numeric lookup remains only
  as a bounded compatibility adapter and is not a new contract.

## Worker loops

- Production LifeMap delivery runs only in `lifemap-worker`.
- API startup contains no LifeMap relay thread.
- Research recovery and other non-LifeMap loops remain owned by their existing
  modules and are outside LifeMap retirement scope.

## Maintained shared capabilities

Chat, Scribe, CareGuard DDI/OCR, PHR, consent, auth, and Research are maintained
shared platform capabilities. They are not obsolete merely because LifeMap can
link to them. Research’s old primary page remains a redirect to Chat.

## Known legacy/compatibility surface

- Numeric LifeMap identifiers are accepted by bounded internal resolvers for
  older clients.
- Generic event creation is retained but cannot create confirmed truth; it
  maps legacy confirmation attempts to `user_reported`.
- Old web/mobile roots remain until traffic, parity, and rollback evidence
  satisfy Phase 14.

## Test inventory

| Gate | Location | Current evidence |
| --- | --- | --- |
| Truth/profile/outbox safety | `services/api/tests/test_lifemap_v2_safety_contracts.py` | Passing |
| Relay/recovery | `services/api/tests/test_lifemap_outbox_relay.py` | Passing |
| PostgreSQL concurrency | `services/api/tests/integration/test_lifemap_outbox_postgres.py` | Passing against isolated production PostgreSQL schema |
| Worker health | `services/api/tests/test_lifemap_worker_health.py` | Passing |
| Typed event envelope | `services/api/tests/test_lifemap_outbox_events.py` | Passing |
| Web core experience | `apps/web/e2e/core-experience.spec.ts` | Passing with documented device skips |
| Mobile | `apps/mobile/test` | Passing baseline |
| ML | `services/ml/tests` | Passing baseline |

The detailed numeric results and known repository debt are maintained in
`implementation-status-2026-07-28.md`.

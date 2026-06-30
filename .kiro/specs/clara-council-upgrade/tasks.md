# Implementation Plan: CLARA Council Upgrade (Production-Grade Multi-Specialist Deliberation)

## Overview

This plan upgrades the Council additively and behind feature flags (all default
OFF). Tasks are ordered so each is independently shippable and verifiable, and so
the highest-value gaps (streaming, run history, real oversight) land on a stable
foundation. Every task preserves existing guardrails (doctor RBAC, owner
isolation, no-PII telemetry, CSRF, deterministic red-flag escalation) and adds a
regression test where it touches a shared path.

### Testing prerequisites (set up once, in task 1.1)
- Reuse the existing harnesses: `services/api/tests` and `services/ml/tests`
  (pytest + hypothesis), and the web fast-check setup for `lib/council.ts`.
- Add a `council_upgrade` test grouping; tag property tests `P1..P14` mapping to
  the design's Correctness Properties.
- A flags-off baseline fixture asserts byte-equivalence with pre-feature behavior.

## Task Dependency Graph

Same-file tasks are serialized into different waves to avoid write conflicts:
`council.py` API endpoints (1.2→2.2→3.1→3.2→4.1→4.2→5.1), ML `council.py`/`main.py`
(2.1→6.1), and web `lib/council.ts` + `app/council/page.tsx` (2.3→3.3→4.3→6.2).
Property tests live in their own files and parallelize freely once their target
module exists.

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "1.4", "2.1"] },
    { "id": 2, "tasks": ["1.5", "2.2", "6.1"] },
    { "id": 3, "tasks": ["2.3", "2.4", "6.2", "6.3"] },
    { "id": 4, "tasks": ["2.5", "3.1", "5.1", "5.2", "5.3"] },
    { "id": 5, "tasks": ["3.2", "3.3", "3.4", "5.4", "7.1"] },
    { "id": 6, "tasks": ["4.1", "4.2", "7.2", "7.3"] },
    { "id": 7, "tasks": ["4.3", "4.4", "8.1"] },
    { "id": 8, "tasks": ["4.5", "4.6", "8.2", "8.3"] },
    { "id": 9, "tasks": ["9.1", "9.2", "9.3"] },
    { "id": 10, "tasks": ["10.1"] }
  ]
}
```

## Tasks

- [ ] 1. Foundations (flags + schema + service skeleton)
  - [x] 1.1 Add `COUNCIL_*` upgrade flags (all default false) to `services/api/.../core/config.py` and the ML `clara_ml.config.settings`; add the `council_upgrade` test grouping. (Req 9.1)
  - [x] 1.2 Add `CouncilRun` and `CouncilOversightAction` models + `council_cases.oversight_state` column in `db/models.py`; one reversible Alembic migration. (Req 2, 3, 9.7)
  - [ ] 1.3 **[PBT]** *(optional)* Migration upgrade/downgrade round-trip property test. (Req 9.7)
  - [x] 1.4 Add `CouncilOrchestrationService` skeleton (flag-aware no-ops wrapping the existing ML proxy). (Req 5, 6, 7)
  - [x] 1.5 Checkpoint — foundations land dark; flags-off equivalence test green. **[PBT]** *(optional)* P8 flags-off equivalence. (Req 9.2)

- [ ] 2. Streaming / progressive deliberation (Req 1)
  - [x] 2.1 ML: add `POST /v1/council/run/stream` (SSE) reusing the `chat_stream` `StreamingResponse` pattern; emit one `stage` event per `reasoning_timeline` step, then a terminal `result`/`error`. (Req 1.1, 1.4)
  - [x] 2.2 API: add `POST /council/cases/{id}/run/stream` proxy, gated by `COUNCIL_STREAMING_ENABLED`, same `doctor` + ownership authz as `/run`. (Req 1.3, 1.6)
  - [x] 2.3 Web: add `streamCouncilRun` in `lib/council.ts` and consume the stream on the review/result surfaces; fall back to blocking `/run` when the flag is off. (Req 1.3)
  - [ ] 2.4 **[PBT]** *(optional)* P1 stream/blocking result equivalence + P2 stage ordering/termination. (Req 1.2)
  - [x] 2.5 Checkpoint — streaming works behind the flag; blocking path unchanged when off.

- [ ] 3. Run history & versioning (Req 2)
  - [x] 3.1 API: on run (blocking and streaming), append a `CouncilRun` when `COUNCIL_RUN_HISTORY_ENABLED`; keep `result_json`/`last_run_at` mirroring the latest run. (Req 2.1, 2.3, 2.6)
  - [x] 3.2 API: `GET /council/cases/{id}/runs` (owner-isolated, newest-first). (Req 2.4, 2.5)
  - [x] 3.3 Web: render run history on the result/workspace surfaces. (Req 2.4)
  - [ ] 3.4 **[PBT]** *(optional)* P3 append-only history + latest-equals-newest invariant. (Req 2.2)

- [ ] 4. Human oversight actions (Req 3, 4)
  - [x] 4.1 API: `POST /council/cases/{id}/oversight` (handoff/override/pause) with server-side role authz + ownership; append `CouncilOversightAction`; `pause` sets `oversight_state`. (Req 3.1, 3.2, 4.2, 4.3)
  - [x] 4.2 API: override retains the AI recommendation alongside the human decision; `GET /council/cases/{id}/oversight` for owner/admin. (Req 3.3, 3.4)
  - [x] 4.3 Web: wire the existing handoff/override/pause controls in `app/council/page.tsx` to the real endpoint when the flag is on; render "not yet confirmed" on pause; keep local-notice behavior when off. (Req 3.2, 3.6)
  - [x] 4.4 Preserve the "review with a licensed clinician" directive on every output regardless of oversight state. (Req 3.5)
  - [ ] 4.5 **[PBT]** *(optional)* P5 override retention + P6 pause-gates-confirmation + P7 authorization soundness + P4 owner isolation. (Req 3, 4)
  - [ ] 4.6 Checkpoint — oversight is persisted and enforced behind the flag; CSRF asserted on mutations (P13).

- [ ] 5. Resilient orchestration & error handling (Req 5)
  - [x] 5.1 API: implement bounded retry/timeout in `CouncilOrchestrationService.run_with_policy` (gated by `COUNCIL_RESILIENCE_ENABLED`); preserve today's single-attempt mapping when off. (Req 5.1, 5.2, 5.5)
  - [x] 5.2 ML/API: label heuristic intake as `is_fallback`/degraded in machine-readable + user-visible form. (Req 5.3)
  - [x] 5.3 Preserve input validation (empty-input 400; audio 15MB / content-type allow-list 413/415). (Req 5.4)
  - [ ] 5.4 **[PBT]** *(optional)* P12 resilience non-corruption (failure leaves case state byte-identical). (Req 5.2, 5.6)

- [ ] 6. Model & fallback disclosure (Req 6)
  - [x] 6.1 ML: attach `ai_disclosure` to `run_council` (`rule_based_council_v2`, `is_fallback=false`) and intake (`is_fallback` iff heuristic), gated by `COUNCIL_MODEL_DISCLOSURE_ENABLED`. (Req 6.1, 6.2, 6.3)
  - [x] 6.2 Web: surface disclosure on result/landing without exposing admin-only telemetry to non-admins; omit entirely when the flag is off. (Req 6.4, 6.5)
  - [ ] 6.3 **[PBT]** *(optional)* P10 disclosure correctness. (Req 6.6)

- [ ] 7. Observability & no-PII telemetry (Req 7)
  - [ ] 7.1 Emit per-stage flow events `{stage, duration_ms, outcome}` and run metrics `{latency_ms, specialist_count, conflict_count, emergency_triggered, fallback_used}`, gated by `COUNCIL_OBSERVABILITY_ENABLED`. (Req 7.1, 7.2)
  - [ ] 7.2 Add a no-PII redaction guard for all Council telemetry writers; preserve existing coarse `council_viewed`/`council_run` events. (Req 7.3, 7.4)
  - [ ] 7.3 **[PBT]** *(optional)* P9 no-PII telemetry (adversarial PII is dropped). (Req 7.3)

- [x] 8. Mobile parity (Req 8)
  - [x] 8.1 Extend `apps/mobile/.../api_client.dart` with case create/intake/specialists/run/result calls reusing the existing Council_API endpoints. (Req 8.1, 8.2)
  - [x] 8.2 Add case/intake/result screens behind `COUNCIL_MOBILE_PARITY_ENABLED` + the existing feature-flags gate; render consensus/divergence/final + clinician directive; preserve no-PII analytics. (Req 8.3, 8.4, 8.5, 8.6)
  - [x] 8.3 Mobile widget/integration test for the parity flow.

- [ ] 9. Guardrail & back-compatibility hardening (Req 9)
  - [x] 9.1 Re-assert deterministic safety: negation-aware red flags force `emergency_escalation`; neural risk stays shadow-only. (Req 9.3, 9.4)
  - [ ] 9.2 **[PBT]** *(optional)* P11 safety preservation + P14 neural shadow containment across all flag permutations. (Req 9.3, 9.4)
  - [x] 9.3 Confirm RBAC, owner isolation, CSRF preserved on all new/existing endpoints; additive/reversible migration verified. (Req 9.6, 9.7)

- [ ] 10. Final quality gate
  - [ ] 10.1 Full flags-off regression suite green (P8) + per-property suite (P1–P14) green; lint/type/build clean across `services/api`, `services/ml`, `apps/web`, `apps/mobile`; staged-enablement runbook authored. (All requirements)

## Notes

### Property → implementing test task
- P1 → 2.4 · P2 → 2.4 · P3 → 3.4 · P4 → 4.5 · P5 → 4.5 · P6 → 4.5 · P7 → 4.5 ·
  P8 → 1.5 / 10.1 · P9 → 7.3 · P10 → 6.3 · P11 → 9.2 · P12 → 5.4 · P13 → 4.6 ·
  P14 → 9.2

### Staged enablement order (production)
1. `MODEL_DISCLOSURE` + `OBSERVABILITY` (user-visible / operational, low risk)
2. `RUN_HISTORY` (after migration verified)
3. `STREAMING` (after stream/blocking equivalence verified)
4. `RESILIENCE` (after retry/timeout policy verified)
5. `OVERSIGHT` (after authz + audit verified)
6. `MOBILE_PARITY` (after endpoints + feature-flags gate verified)

### Subagent assignment guidance
- Backend service + migration + endpoints (tasks 1, 3, 4, 5) — one writer.
- ML streaming + disclosure (tasks 2.1, 6.1) — one writer.
- Web surfaces (2.3, 3.3, 4.3, 6.2) — disjoint writer.
- Mobile parity (task 8) — independent writer.

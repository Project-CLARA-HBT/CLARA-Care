# Research Flow Architecture Refactor Plan (2026-04-11)

## Goal
Reduce architectural risk in the current Research flow by:
1. Removing duplicated Tier2 job orchestration logic in web clients.
2. Hardening API-side safety and consistency for job/upload handling.
3. Shipping focused tests that lock the refactor behavior.

## Scope (This Execution)
- `apps/web`: Chat/Research pages and shared research runtime utilities.
- `services/api`: Research endpoint internals and configuration wiring.
- `services/api/tests`: Regression coverage for the new behavior.

## Out of Scope (Deferred)
- Full decomposition of `services/ml/src/clara_ml/agents/research_tier2.py`.
- Migration from in-process worker queue to external queue infrastructure.
- End-to-end contract generation (OpenAPI -> TS) for all research payloads.

## Phase Plan

### Phase 1: Web Tier2 Orchestration Consolidation
Status: `completed`

Deliverables:
- Add one shared Tier2 job runner utility for create -> stream -> poll -> finalize.
- Remove duplicated retry/poll/refetch logic from:
  - `apps/web/app/chat/page.tsx`
  - `apps/web/app/research/page.tsx`
- Keep existing UX behavior (live status, streaming fallback to polling, final-result guardrails).

Acceptance criteria:
- Both pages call the shared runner.
- No duplicated `fetchTier2JobWithRetry` remains in those pages.
- Existing error semantics are preserved.

### Phase 2: API Research Hardening
Status: `completed`

Deliverables:
- Scope transient uploaded file resolution by owner user ID before forwarding to ML.
- Normalize Tier2 query extraction through a dedicated helper (supporting legacy keys).
- Remove config drift for research job limits by sourcing from typed settings (instead of direct env parsing in endpoint module).

Acceptance criteria:
- Uploaded transient docs cannot be consumed cross-user.
- Tier2 uses normalized query/message consistently.
- Job limit values are controlled via `Settings` fields.

### Phase 3: Regression Coverage + Plan Closeout
Status: `completed`

Deliverables:
- Add/adjust API tests for new ownership and query normalization behavior.
- Run focused test suite for changed surfaces.
- Update this plan file statuses to completed with verification notes.

Acceptance criteria:
- New tests pass.
- Existing touched tests pass.
- Plan marked completed with executed commands.

## Execution Log
- Implemented shared Tier2 job runner:
  - `apps/web/lib/research-tier2-job-runner.ts`
  - `apps/web/app/chat/page.tsx`
  - `apps/web/app/research/page.tsx`
  - `apps/web/lib/research.ts` (exported shared create-options type)
- Hardened API upload/job handling:
  - `services/api/src/clara_api/api/v1/endpoints/research.py`
  - `services/api/src/clara_api/core/config.py`
- Added regression coverage:
  - `services/api/tests/test_p2_proxy_endpoints.py`
    - query/message forwarding from legacy `question`
    - cross-user uploaded transient document isolation
- Validation executed:
  - `cd apps/web && npx eslint app/chat/page.tsx app/research/page.tsx lib/research-tier2-job-runner.ts lib/research.ts`
    - Result: pass (warnings only, no errors)
  - `python3 -m compileall -q services/api/src/clara_api/core/config.py services/api/src/clara_api/api/v1/endpoints/research.py services/api/tests/test_p2_proxy_endpoints.py`
    - Result: pass
  - `python3 -m venv .venv-api && .venv-api/bin/pip install -e 'services/api[dev]'`
    - Result: pass (isolated test environment prepared)
  - `DATABASE_FALLBACK_ENABLED=true DATABASE_FALLBACK_URL=sqlite+pysqlite:////tmp/clara-test.db ML_INTERNAL_API_KEY='' DEEPSEEK_STRICT_MODE=false .venv-api/bin/pytest -q services/api/tests/test_p2_proxy_endpoints.py -q`
    - Result: pass

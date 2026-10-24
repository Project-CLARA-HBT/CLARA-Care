# Test Report — PH12 A07 (Tests + CI: Mobile Full LifeMap Parity)

## 1. Environment & Execution Context
- **Phase ID**: `PH12` (LifeMap longitudinal intelligence)
- **Subagent ID**: `A07`
- **Role**: `Tests + CI`
- **Task**: `mobile full LifeMap parity`
- **Worktree**: `/dev/shm/clara_worktrees/PH12_A07`
- **Branch**: `phase/ph12-a07`
- **Frozen Base / HEAD SHA**: `36e5b95fac7e65712f0779de253d8ed18dc693d7`
- **Runtime**: Python 3.12.3 / FastAPI / SQLite isolated test db
- **Execution Date**: 2026-10-24

---

## 2. Test Execution Summary

| Test Suite File | Collected | Passed | Failed | Skipped | Duration | Exit Code |
|-----------------|-----------|--------|--------|---------|----------|-----------|
| `services/api/tests/test_lifemap_mobile_parity_integration.py` | 20 | 20 | 0 | 0 | 37.86s | `0` |

---

## 3. Detailed Test Case Verification Matrix

### Section 1: LifeMap Timeline Queries (Mobile Parity & Bitemporal Filters)
1. `test_mobile_timeline_basic_query_and_shape`: **PASS** (Exit 0)
   - Verifies `GET /api/v1/lifemap/timeline` returns items matching mobile client contract: `id`, `event_type`, `truth_state`, `occurred_at`, `recorded_at`, `payload`, `provenance`, `source_kind`, `episode_id`, `revision_no`.
   - Verifies default sort ordering is reverse chronological (`occurred_at DESC`).
2. `test_mobile_timeline_pagination_and_bounds_validation`: **PASS** (Exit 0)
   - Verifies `limit` and `offset` pagination slice across timeline events.
   - Verifies boundary enforcement: `limit=0`, `limit=501`, `offset=-1` correctly rejected with HTTP 422.
3. `test_mobile_timeline_filtering_by_event_type_and_truth_state`: **PASS** (Exit 0)
   - Verifies filtering by event types (`blood_pressure`, `glucose`, etc.) and truth states (`user_reported`, `disputed`).
4. `test_mobile_timeline_bitemporal_filtering`: **PASS** (Exit 0)
   - Verifies `valid_time_from` (filters by event `occurred_at`) and `system_time_from` (filters by revision `recorded_at`).
   - Verifies future cutoffs yield zero results and historical boundaries correctly restrict results.
5. `test_mobile_timeline_episode_scoping`: **PASS** (Exit 0)
   - Verifies `GET /api/v1/lifemap/timeline?episode_id={id}` isolates events associated with an episode.
   - Verifies `GET /api/v1/episodes/{id}/replay` returns the full episode event linkage.
6. `test_mobile_timeline_profile_isolation_and_idor_protection`: **PASS** (Exit 0)
   - Verifies User A's events are never returned to User B.
   - Verifies unauthorized profile context swapping (`X-CLARA-Profile-Context`) fails with HTTP 404 (non-interference).
   - Verifies unauthenticated queries fail with HTTP 401.
7. `test_mobile_timeline_revisions_and_event_history`: **PASS** (Exit 0)
   - Verifies event correction creates successor revision (`revision_no=2`).
   - Verifies `GET /api/v1/lifemap/events/{id}/history` and `/revisions` deliver complete audit history.

### Section 2: Mobile Read Projection & Cache Invalidation
8. `test_mobile_today_read_projection_contract`: **PASS** (Exit 0)
   - Verifies `GET /api/v1/lifemap/today` returns data structure matching mobile `LifeMapReadCache.project()` expectations: `tasks` (id, title, due_at), `episodes` (id, title, priority), `pending_confirmation_count`, `activity_days`, `completed_today_count`.
   - Verifies data minimization: no raw notes or internal foreign keys leaked.
9. `test_mobile_client_contract_offline_policy_and_vocabulary`: **PASS** (Exit 0)
   - Verifies `GET /api/v1/lifemap/v2/client-contract` exposes exactly 7 states (`draft`, `awaiting_review`, `confirmed`, `disputed`, `stale`, `unavailable`, `offline`).
   - Verifies only `confirmed` has `truth_authority: True`.
   - Verifies offline policy: mutations disabled, queued mutations false, encrypted cache required.
10. `test_cache_invalidation_on_event_correction`: **PASS** (Exit 0)
    - Verifies modifying an event marks projection graph dependencies (`LifeMapProjectionDependency`) as invalidated with reason `source_corrected`.
11. `test_cache_invalidation_on_event_dispute_and_resolution`: **PASS** (Exit 0)
    - Verifies disputing an event invalidates projection dependencies with reason `disputed`.
    - Verifies resolving a dispute invalidates dependencies with reason `confirmed`.
12. `test_cache_invalidation_on_source_revocation`: **PASS** (Exit 0)
    - Verifies revoking a health source reference via `POST /api/v1/lifemap/v2/sources/{id}/revoke` invalidates all dependent projections with reason `source_revoked`.
13. `test_cache_invalidation_on_late_arriving_data`: **PASS** (Exit 0)
    - Verifies inserting late-arriving events (>5 min in past) triggers `invalidate_all` on profile projection cache with reason `late_data`.
14. `test_mobile_optimistic_concurrency_and_stale_detection`: **PASS** (Exit 0)
    - Verifies matching `If-Match` succeeds.
    - Verifies stale `If-Match` yields HTTP 409 `stale_version`.
    - Verifies malformed `If-Match` yields HTTP 422 `invalid_if_match`.
    - Verifies `Idempotency-Key` replay returns prior response without re-executing command.

### Section 3: Consent Filtering & Invariants
15. `test_consent_gate_blocks_endpoints_without_consent`: **PASS** (Exit 0)
    - Verifies sensitive LifeMap endpoints fail with HTTP 428 Precondition Required when medical disclaimer consent is absent.
16. `test_consent_acceptance_unblocks_endpoints`: **PASS** (Exit 0)
    - Verifies accepting medical disclaimer consent via `POST /api/v1/auth/consent` unblocks sensitive endpoints (returns HTTP 201).
17. `test_consent_revocation_immediately_blocks_endpoints`: **PASS** (Exit 0)
    - Verifies consent withdrawal immediately causes subsequent requests to fail with HTTP 428.
18. `test_consent_version_mismatch_blocks_endpoints`: **PASS** (Exit 0)
    - Verifies outdated consent version causes requests to fail with HTTP 428.
19. `test_consent_ledger_append_only_audit`: **PASS** (Exit 0)
    - Verifies consent ledger (`UserConsent`) is append-only and retains full audit history.

### Section 4: Mobile Summary & Feature Flags Parity
20. `test_mobile_summary_lifemap_flags_exposure`: **PASS** (Exit 0)
    - Verifies `GET /api/v1/mobile/summary` exposes all server-authoritative LifeMap feature flags (`lifemap_v2`, `lifemap_capture`, `lifemap_baselines_v2`, `lifemap_next_question_v2`, `lifemap_replay_v2`, `lifemap_visit_extraction`, `lifemap_evidence_monitor`, `lifemap_fhir_export`, `lifemap_fhir_import`, `lifemap_ask_ai`, `lifemap_ai_summaries`).

---

## 4. Verification Commands & Process Outputs

### 4.1 Pytest Suite
```bash
DATABASE_URL=sqlite+pysqlite:////tmp/clara_api_ci.db AUTH_AUTO_PROVISION_USERS=true AUTH_BOOTSTRAP_ADMIN_ENABLED=true uv run pytest -q tests/test_lifemap_mobile_parity_integration.py
```
**Exit Code**: `0`
**Process Output**:
```
....................                                                     [100%]
20 passed, 31 warnings in 37.86s
```

### 4.2 AST Compilation
```bash
python3 -m compileall -q services/api/tests/test_lifemap_mobile_parity_integration.py
```
**Exit Code**: `0`
**Process Output**: `Clean compilation, zero syntax errors.`

### 4.3 Path Lane ACL Validation
```bash
python3 /home/clue/Documents/CLARA-Care/scripts/ci/check_agent_path_acl.py -a A07 -p PH12
```
**Exit Code**: `0`
**Process Output**:
```
================================================================================
PATH ACL CHECKER — PASSED (Agent: A07, Phase: PH12)
================================================================================
Evaluated Files : 1
Allowed Lanes   : 8
  - services/api/tests/
  - services/ml/tests/
  - apps/web/e2e/
  - .github/workflows/
  - artifacts/PH12/A07/change_manifest.json
  - artifacts/PH12/A07/test_report.md
  - artifacts/PH12/A07/risk_register.md
  - artifacts/PH12/A07/

Result: All touched files conform strictly to the designated path lane.
```

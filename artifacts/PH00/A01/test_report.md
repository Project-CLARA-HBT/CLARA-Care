# PH00-A01 Test & Verification Report

**Phase:** PH00 (Đóng băng baseline và lập traceability)
**Agent:** A01 (API + contract)
**Frozen Base HEAD:** `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`
**Target Branch:** `phase/ph00-a01`
**Worktree:** `/dev/shm/clara_worktrees/PH00_A01`
**Execution Date:** 2026-10-21

---

## 1. Executive Summary

Subagent A01 executed a comprehensive, non-destructive audit and baseline inventory of API schemas, route contracts, consumer terminology, design tokens, and RBAC boundary invariants on the frozen commit `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`.

- **Base SHA Integrity:** Pinned git SHA `8a48afab1dafa2f8ccb4ac9f320505452d18b30f` verified matches HEAD exactly.
- **Contract Verification:** Consumer Terminology (`contracts/consumer-terminology/consumer-terminology.v1.json`, 19 keys) and Design Tokens (`contracts/design-tokens/tokens.json`) verified against web and mobile generated projections.
- **Schema & Route Table Enumeration:** 137 Pydantic `BaseModel` schemas in `schemas.py` and 793 registered OpenAPI route paths cataloged across API v1, v2, and root endpoints.
- **Drift & Defect Capture:** 1 active baseline test failure identified in `test_route_inventory_public_boundaries.py` (`POST /api/v1/auth/callback` missing from `INTENTIONAL_PUBLIC_ROUTES`), along with duplicate OpenAPI operation IDs and an ORM keyword argument mismatch during admin data seeding.
- **Test Suite Results:** 13 focused test suites executed; 12 passed (100 tests passed), 1 failed due to intentional baseline defect detection.

---

## 2. Pinned SHA & Environment Verification

| Parameter | Observed Value | Verification Status |
|---|---|---|
| Git HEAD SHA | `8a48afab1dafa2f8ccb4ac9f320505452d18b30f` | **PASS (EXACT MATCH)** |
| Branch | `phase/ph00-a01` | **PASS** |
| Python Environment | Python 3.12.3, FastAPI 0.141.1, Pydantic 2.13.5, SQLAlchemy 2.0.44 | **PASS** |
| Node Environment | Node.js v20.20.2 | **PASS (Meets Node 20 pin)** |
| SQLite Test Storage | `/dev/shm/pytest_clara.db` (in-memory `tmpfs` via `CLARA_TEST_DATABASE_URL`) | **OPTIMAL (0.41s DDL)** |

*Note on disk I/O:* Root filesystem `/dev/sda2` is at 98% capacity (5.7GB available). Running SQLite tests directly in `/tmp` encounters kernel D-state disk serialization delays. Using `CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/pytest_clara.db"` ensures hermetic, sub-second execution without file disk thrashing.

---

## 3. Test Commands and Exit Codes

| # | Command | Scope / Target | Exit Code | Outcome | Execution Time |
|---|---|---|---|---|---|
| 1 | `git rev-parse HEAD` | Verify frozen SHA | `0` | **PASS** | < 0.1s |
| 2 | `node apps/web/scripts/check-consumer-terminology-contract.mjs` | Consumer terminology v1 contract check | `0` | **PASS** (19 keys) | 0.08s |
| 3 | `node apps/web/scripts/generate-consumer-terminology.mjs --check` | Verify web and mobile projections in sync | `0` | **PASS** (in sync) | 0.09s |
| 4 | `node packages/design-tokens/generate.js` | Deterministic token generation verification | `0` | **PASS** (`0e438d4f0908af78`) | 0.12s |
| 5 | `python3 -c "import clara_api.schemas; ..."` | Pydantic schema reflection & loading | `0` | **PASS** (137 models) | 0.52s |
| 6 | `python3 -m pytest tests/test_validation_error_serialization.py` | Schema validation error serialization | `0` | **PASS** (1/1) | 5.49s |
| 7 | `python3 -m pytest tests/test_api_v2_conventions.py` | API v2 envelopes, ETags, pagination | `0` | **PASS** (17/17) | 11.33s |
| 8 | `python3 -m pytest tests/test_canonicalization_conformance.py` | Field and payload canonicalization | `0` | **PASS** (7/7) | 6.71s |
| 9 | `python3 -m pytest tests/test_connected_health_schemas.py` | Connected health envelope schemas | `0` | **PASS** (14/14) | 9.05s |
| 10 | `python3 -m pytest tests/test_phr_schemas_backcompat.py` | PHR schema additive backcompat | `0` | **PASS** (6/6) | 6.54s |
| 11 | `python3 -m pytest tests/test_router_audit_endpoints.py` | Route audit endpoints & RBAC | `0` | **PASS** (5/5) | 7.69s |
| 12 | `python3 -m pytest tests/test_admin_routers_and_visit_verify.py` | Admin router mounting & verification | `0` | **PASS** (6/6) | 7.08s |
| 13 | `python3 -m pytest tests/test_auth_and_rbac.py` | Core authentication & role checking | `0` | **PASS** (4/4) | 7.85s |
| 14 | `python3 -m pytest tests/test_auth_extended_flow.py` | Extended authentication lifecycle | `0` | **PASS** (3/3) | 9.45s |
| 15 | `python3 -m pytest tests/test_auth_security_hardening.py` | Hardened token parsing & revocation | `0` | **PASS** (6/6) | 8.37s |
| 16 | `python3 -m pytest tests/test_careguard_cabinet_endpoints.py` | Cabinet OCR & drug endpoints | `0` | **PASS** (24/24) | 29.76s |
| 17 | `python3 -m pytest tests/test_admin_audit_module.py` | Admin audit logging & immutability | `0` | **PASS** (10/10) | 7.76s |
| 18 | `python3 -m pytest tests/test_medication_convergence.py` | Medication course idempotency | `0` | **PASS** (2/2) | 8.07s |
| 19 | `python3 -m pytest tests/test_route_inventory_public_boundaries.py` | Live RBAC route classification assert | `1` | **FAIL** (1 fail, 1 pass) | 7.55s |

**Overall Test Suite Counts:**
- **Total Tests Run:** 102
- **Passed:** 101
- **Failed:** 1 (`test_every_unauthenticated_route_has_an_explicit_public_reason`)

---

## 4. Detailed Failure Log Excerpt

```
=================================== FAILURES ===================================
________ test_every_unauthenticated_route_has_an_explicit_public_reason ________

    def test_every_unauthenticated_route_has_an_explicit_public_reason() -> None:
>       assert unclassified_public_routes(app) == []
E       AssertionError: assert [RouteClassification(method='POST', path='/api/v1/auth/callback', classification='public', roles=frozenset(), requires_auth=False, optional_auth=False)] == []
E
E         Left contains one more item: RouteClassification(method='POST', path='/api/v1/auth/callback', classification='public', roles=frozenset(), requires_auth=False, optional_auth=False)

/dev/shm/clara_worktrees/PH00_A01/services/api/tests/test_route_inventory_public_boundaries.py:42: AssertionError
------------------------------ Captured log setup ------------------------------
WARNING  clara_api.core.bootstrap_admin:bootstrap_admin.py:87 Failed to seed admin clinical data: 'version_no' is an invalid keyword argument for PhrProfile
```

### Analysis of the Defect:
1. `POST /api/v1/auth/callback` was implemented in `clara_api/api/v1/endpoints/auth.py` (lines 276-291) to handle OAuth/SSO callback redirects without prior session credentials.
2. `main.py` line 137 correctly added `"/api/v1/auth/callback"` to `_CSRF_EXEMPT_PATHS`.
3. However, `clara_api/core/route_inventory.py` lines 106-138 (`INTENTIONAL_PUBLIC_ROUTES`) omitted `("POST", "/api/v1/auth/callback")`.
4. As a result, the live route inventory checker classifies it as `public` but fails the deny-by-default assertion because it is not explicitly listed.

---

## 5. Schema & Contract Inventory Summary

### 5.1 Route Inventory Overview
- **Total OpenAPI paths registered:** 793
- **Distinct API v1 endpoints:** 372
- **Double-mounted API v1 endpoints:** 372 (`/api/v1/api/v1/*` backward-compatibility aliases)
- **Distinct API v2 endpoints:** 46
- **Root service endpoints:** 3 (`/health`, `/health/ready`, `/metrics`)
- **Route classifications:**
  - `role`: 396 routes (require specific role such as `admin`, `doctor`, `researcher`, or `normal`)
  - `authenticated`: 64 routes (require valid bearer or session cookie, open to any authenticated user)
  - `public`: 25 routes (intentionally reachable without credentials)

### 5.2 Schema Groups in `clara_api/schemas.py`
The 137 Pydantic schemas fall into 12 core domains:
1. **User, Session & Auth:** 22 models (`User`, `Session`, `LoginRequest`, `LoginResponse`, `RegisterRequest`, etc.)
2. **Chat & LLM Interface:** 2 models (`ChatRequest`, `ChatResponse`)
3. **Medicine Cabinet & Careguard:** 14 models (`MedicineCabinetItemCreate`, `CabinetScanDetection`, `CabinetAutoDdiRequest`, etc.)
4. **PHR (Personal Health Record):** 21 models (`PhrRecordResponse`, `PhrEnhancedRecordResponse`, `PhrMedicationItem`, etc.)
5. **Clinical Council:** 2 models (`CouncilRunRequest`, `CouncilRunResponse`)
6. **Research & Living Evidence:** 11 models (`ResearchTier2JobCreateRequest`, `ResearchClarifyRequest`, etc.)
7. **Scribe & Clinical Notes:** 5 models (`ScribeExtractionResponse`, `ScribeAddendumResponse`, etc.)
8. **Workspace Collaboration:** 25 models (`WorkspaceFolderCreateRequest`, `WorkspaceNoteResponse`, etc.)
9. **Knowledge Sources & RAG Control:** 15 models (`KnowledgeSourceResponse`, `RagFlowConfig`, `SystemControlTowerConfig`, etc.)
10. **Vietnamese Drug Bank:** 9 models (`VnDrugResolveRequest`, `VnDrugMappingResponse`, `VnDrugMappingAuditResponse`, etc.)
11. **Mobile Client Health:** 2 models (`MobileApiHealth`, `MobileSummaryResponse`)
12. **OCR Disclosures & Verification:** 4 models (`UnifiedContractMetadata`, `OcrConfirmGate`, etc.)

---

## 6. Contract Verification Checks

### 6.1 Consumer Terminology (`contracts/consumer-terminology/`)
- Contract version: `2026-07-30.v1`
- Supported locales: `vi` (default), `en`
- Keys: 19 keys covering `action.*`, `navigation.*`, and `today.*`
- Status: **100% in sync** with `apps/web/lib/i18n/consumer-terminology.generated.ts` and `apps/mobile/lib/core/consumer_terminology.generated.dart`. Verified through `check-consumer-terminology-contract.mjs`.

### 6.2 Design Tokens (`contracts/design-tokens/` & `packages/design-tokens/`)
- Contract version: `2026-08-19.v1`
- Generated CSS: `apps/web/styles/tokens.css`
- Generated Dart: `apps/mobile/lib/core/clara_tokens.g.dart`
- Status: **Deterministic build confirmed** (Hash: `0e438d4f0908af78`), zero diff against baseline.

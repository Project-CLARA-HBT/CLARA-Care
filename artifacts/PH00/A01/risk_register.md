# PH00-A01 Risk Register & Baseline Defect Log

**Phase:** PH00 (Đóng băng baseline và lập traceability)
**Agent:** A01 (API + contract)
**Frozen Base HEAD:** `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`
**Target Branch:** `phase/ph00-a01`
**Date:** 2026-10-21

---

## Risk Summary Matrix

| Risk ID | Title | Category | Severity | Likelihood | Impact | Status | Target Phase |
|---|---|---|---|---|---|---|---|
| **RISK-A01-01** | `POST /api/v1/auth/callback` missing from `INTENTIONAL_PUBLIC_ROUTES` | Contract / RBAC | **High (P1)** | Certain (100%) | CI test failure in `test_route_inventory_public_boundaries.py` | Active Defect | PH01 / PH02 |
| **RISK-A01-02** | `PhrProfile` ORM model mismatch (`version_no=5`) during admin seeding | Data Model / ORM | **Medium (P2)** | Certain (100%) | Admin bootstrap clinical records fail to seed; warning emitted on startup | Active Defect | PH01 / PH02 |
| **RISK-A01-03** | OpenAPI Operation ID collision from dual-mounted routers | API Contract / OpenAPI | **Medium (P2)** | High | Client SDK generator warnings, operation ID ambiguity | Active Warning | PH01 / PH02 |
| **RISK-A01-04** | SQLite disk I/O lockup on near-capacity host filesystem | Infrastructure / CI | **High (P1)** | Medium | Tests timeout (>120s) if writing to `/tmp` on `/dev/sda2` (98% full) | Mitigated | PH01 |
| **RISK-A01-05** | Dual-source design token representations | Contract Drift | **Low (P3)** | Low | Confusion between `contracts/design-tokens/` and `packages/design-tokens/` | Observational | PH01 |
| **RISK-A01-06** | API v1 vs API v2 Response Contract Asymmetry | Architecture / Contract | **Medium (P2)** | High | Frontend clients must maintain dual parsers (raw JSON vs `ApiV2ResponseEnvelope`) | Structural | PH40 / PH41 |

---

## Detailed Risk Assessments

### RISK-A01-01: `POST /api/v1/auth/callback` missing from `INTENTIONAL_PUBLIC_ROUTES`
- **Location:** `services/api/src/clara_api/core/route_inventory.py:106-138`
- **Related Anchors:**
  - `services/api/src/clara_api/api/v1/endpoints/auth.py:276` (`@router.post("/callback", response_model=LoginResponse)`)
  - `services/api/src/clara_api/main.py:137` (`_CSRF_EXEMPT_PATHS`)
  - `services/api/tests/test_route_inventory_public_boundaries.py:42`
- **Description:**
  The endpoint `POST /api/v1/auth/callback` was implemented to receive OAuth2/SSO provider redirects. `main.py` explicitly exempted it from CSRF protection, recognizing that OAuth callbacks arrive from third-party identity providers without prior session cookies. However, `clara_api/core/route_inventory.py` was not updated to include `("POST", "/api/v1/auth/callback")` in `INTENTIONAL_PUBLIC_ROUTES`.
- **Impact:**
  Running `pytest services/api/tests/test_route_inventory_public_boundaries.py` fails on the frozen commit:
  `AssertionError: assert [RouteClassification(method='POST', path='/api/v1/auth/callback', classification='public', ...)] == []`.
- **Recommended Action:**
  In PH01/PH02, add `("POST", "/api/v1/auth/callback")` to `INTENTIONAL_PUBLIC_ROUTES` in `route_inventory.py` to restore green CI.

---

### RISK-A01-02: `PhrProfile` ORM model mismatch (`version_no=5`) during admin seeding
- **Location:** `services/api/src/clara_api/core/seed_admin_data.py:106`
- **Related Anchors:**
  - `services/api/src/clara_api/db/models.py:845` (`class PhrProfile(Base)`)
  - `services/api/src/clara_api/core/bootstrap_admin.py:87`
- **Description:**
  When bootstrapping an admin user (`ensure_bootstrap_admin`), `seed_admin_clinical_data` attempts to construct a `PhrProfile` passing `version_no=5`. However, the SQLAlchemy model `PhrProfile` defined in `models.py` has no `version_no` column (versioning was moved or structured differently).
- **Impact:**
  Every database initialization logs a warning:
  `WARNING clara_api.core.bootstrap_admin:bootstrap_admin.py:87 Failed to seed admin clinical data: 'version_no' is an invalid keyword argument for PhrProfile`
  Admin test fixture clinical history is not seeded.
- **Recommended Action:**
  Remove `version_no=5` from the `PhrProfile` kwargs in `seed_admin_data.py:106` or add the column to the migration graph if version tracking is required.

---

### RISK-A01-03: OpenAPI Operation ID collision from dual-mounted routers
- **Location:** `services/api/src/clara_api/api/router.py:64-69`, `services/api/src/clara_api/main.py:388-392`
- **Description:**
  1. `clinical_workbench.router` is mounted twice in `router.py`: once at `/clinical-workbench` and once at `/clinical/workbench`.
  2. `api_router` is mounted twice in `main.py`: once at `/` (giving `/api/v1/*`) and once with `prefix="/api/v1"` (giving `/api/v1/api/v1/*` for stale frontend bundles).
- **Impact:**
  FastAPI outputs 22 `UserWarning: Duplicate Operation ID ... for function ... at clinical_workbench.py` when generating OpenAPI JSON. Automated TypeScript client generation (e.g. `openapi-typescript` or `orval`) will generate duplicate types or clobber function names.
- **Recommended Action:**
  Assign explicit `operation_id` generator or unique operation IDs per alias route, or eliminate legacy path aliases once frontend bundle migration is verified in PH05/PH40.

---

### RISK-A01-04: SQLite disk I/O lockup on near-capacity host filesystem
- **Location:** Host OS `/dev/sda2`, mounted on `/` (98% full, ~5.7GB free)
- **Description:**
  Pytest default configuration in `services/api/tests/conftest.py` uses `tempfile.TemporaryDirectory(prefix="clara-api-pytest-")`, creating temporary SQLite databases on `/tmp` (part of the root filesystem). Under high disk saturation, filesystem sync/fsync operations block in uninterruptible kernel sleep (D-state), causing tests to hang past 120s timeouts.
- **Impact:**
  Test runs intermittently freeze or timeout unless an in-memory or tmpfs location is used.
- **Mitigation Applied:**
  Set `CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/pytest_clara.db"` when running tests. This uses the `tmpfs` RAM filesystem (/dev/shm), bypassing disk contention and reducing schema initialization time from >120s to 0.41s.

---

### RISK-A01-05: Dual-source design token representations
- **Location:** `contracts/design-tokens/tokens.json` vs `packages/design-tokens/clara.tokens.json`
- **Description:**
  Two design token contract definitions coexist: `contracts/design-tokens/tokens.json` (v2026-08-19.v1) and `packages/design-tokens/clara.tokens.json`. Web generation currently targets `packages/design-tokens/generate.js`.
- **Impact:**
  Developers modifying tokens in `contracts/design-tokens/` may find their changes do not propagate to web or mobile builds if `packages/design-tokens/generate.js` reads `clara.tokens.json`.
- **Recommended Action:**
  In PH01/PH02, consolidate canonical token storage to `contracts/design-tokens/` and symlink or point `packages/design-tokens/generate.js` directly to it.

---

### RISK-A01-06: API v1 vs API v2 Response Contract Asymmetry
- **Location:** `services/api/src/clara_api/api/v2/conventions.py` vs `services/api/src/clara_api/api/v1/`
- **Description:**
  API v2 introduces strict envelopes:
  - Success: `ApiV2ResponseEnvelope[T] { data: T, meta: ..., message: ..., warnings: [...] }`
  - Error: `ApiV2ErrorEnvelope { code: ..., message_key: ..., message: ..., params: ..., details: ... }`
  - Concurrency: `If-Match` ETags with `BaseVersionPrecondition`
  - Idempotency: `Idempotency-Key` header with automatic replay
  Meanwhile, API v1 returns raw models directly.
- **Impact:**
  Web and mobile clients must support two fundamentally different response parsing paradigms depending on endpoint version.
- **Recommended Action:**
  Maintain adapter wrappers in the web/mobile client API layer (PH05/PH06) until all consumer-facing endpoints are transitioned to API v2 envelopes in PH40+.

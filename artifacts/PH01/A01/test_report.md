# PH01-A01 Test & Verification Report

**Phase:** PH01 (Python 3.12 Env Bootstrap & Defect Remediation)  
**Agent:** A01 (API + contract)  
**Role:** API + contract  
**Worktree:** `/dev/shm/clara_worktrees/PH01_A01`  
**Branch:** `phase/ph01-a01`  
**Frozen Base HEAD:** `2aa9016a57b49b53f1a433d076e1028a6ec45f64`  
**Verified Repo HEAD:** `2aa9016a57b49b53f1a433d076e1028a6ec45f64`  
**Execution Timestamp:** 2026-10-21  
**Overall Status:** **PASS (100%)**

---

## 1. Executive Summary

Subagent A01 completed the assigned tasks within Phase PH01:
1. **Verified Base SHA:** Confirmed worktree HEAD matches frozen commit `2aa9016a57b49b53f1a433d076e1028a6ec45f64`.
2. **Python 3.12 & Environment Bootstrap Audit:** Evaluated Python 3.12.3 environment, `uv` packaging toolchain, and `pyproject.toml` configurations for `services/api` and `services/ml`. Verified compatibility with Python >=3.11 and Python 3.12.
3. **Remediated DEFECT-01:** Updated `services/api/src/clara_api/core/route_inventory.py` to include `("POST", "/api/v1/auth/callback")` in `INTENTIONAL_PUBLIC_ROUTES`.
4. **Verified Route Inventory Boundary Tests:** `tests/test_route_inventory_public_boundaries.py` passed 100% (2 of 2 tests passed).
5. **Verified Cross-Boundary Regression Suites:** Executed schema validation, v2 conventions, RBAC, authorization hardening, consumer terminology, and design token contracts—all passing with zero errors.

---

## 2. Environment & Compatibility Audit

### 2.1 Python Runtime & Tooling

| Component | Target Requirement | Detected System Value | Assessment |
|---|---|---|---|
| Python Runtime | `>=3.11` | Python 3.12.3 (`/usr/bin/python3`, `/home/clue/.local/bin/python`) | **COMPATIBLE** |
| Packaging Tool | `uv` | uv 0.13.4 (`/home/clue/.local/bin/uv`) | **COMPATIBLE** |
| `services/api/pyproject.toml` | `requires-python = ">=3.11"` | Matches spec; ruff `target-version = "py311"`, mypy `python_version = "3.11"` | **AUDITED OK** |
| `services/ml/pyproject.toml` | `requires-python = ">=3.11"` | Matches spec; ruff `target-version = "py311"` | **AUDITED OK** |
| Node.js Runtime | Node 20 | Node.js v20.20.2 (`.nvmrc` pinned) | **COMPATIBLE** |

### 2.2 Python 3.12 Compatibility Findings
- **FastAPI / Starlette:** All router mounts, middleware stacks, and dependency injection patterns execute cleanly on Python 3.12. Minor deprecation warnings from Starlette (`HTTP_422_UNPROCESSABLE_ENTITY` and TestClient `httpx` vs `httpx2`) are observational and do not affect runtime stability.
- **SQLAlchemy 2.0 / Pydantic 2.9:** Core ORM schemas and reflection operate without deprecated Python 3.11 features.
- **SQLite Concurrency & Host Disk Nuance:** The host filesystem (`/dev/sda2`, 98% capacity) experiences high D-state wait times on temporary SQLite database transactions under `/tmp`. Executing tests with `CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/clara-test.db"` on the in-memory `tmpfs` avoids disk saturation and executes the entire schema initialization in sub-second time.

---

## 3. Defect Remediation: DEFECT-01

### 3.1 Problem Statement
In `services/api/src/clara_api/api/v1/endpoints/auth.py`, endpoint `POST /api/v1/auth/callback` handles OAuth authorization code exchange. `main.py` explicitly exempts this route from CSRF protection as an unauthenticated external entry point. However, `INTENTIONAL_PUBLIC_ROUTES` in `services/api/src/clara_api/core/route_inventory.py` omitted this route, causing `unclassified_public_routes(app)` to return `[RouteClassification(method='POST', path='/api/v1/auth/callback', ...)]` and triggering an assertion failure in `test_every_unauthenticated_route_has_an_explicit_public_reason`.

### 3.2 Change Applied
In `services/api/src/clara_api/core/route_inventory.py`:
```python
INTENTIONAL_PUBLIC_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ...
        # Pre-authentication auth surface (no identity exists yet).
        ("POST", "/api/v1/auth/register"),
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/auth/login-otp/verify"),
        ("POST", "/api/v1/auth/callback"),
        ("POST", "/api/v1/auth/refresh"),
        ("POST", "/api/v1/auth/logout"),
        ("POST", "/api/v1/auth/forgot-password"),
        ("POST", "/api/v1/auth/reset-password"),
        ("POST", "/api/v1/auth/verify-email"),
        ("POST", "/api/v1/auth/resend-verification"),
    }
)
```

---

## 4. Test Commands and Exit Codes

| # | Command | Directory | Exit Code | Results | Duration |
|---|---|---|---|---|---|
| 1 | `git rev-parse HEAD` | `/dev/shm/clara_worktrees/PH01_A01` | `0` | Exact match `2aa9016a57b49b53f1a433d076e1028a6ec45f64` | < 0.1s |
| 2 | `CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/clara-test.db" pytest -vv tests/test_route_inventory_public_boundaries.py` | `services/api` | `0` | **2 passed (100%)** | 6.65s |
| 3 | `CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/clara-test.db" pytest -vv tests/hardening/test_authz_under_privileged.py` | `services/api` | `0` | **6 passed (100%)** | 11.16s |
| 4 | `CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/clara-test.db" pytest -q tests/test_validation_error_serialization.py tests/test_api_v2_conventions.py tests/test_canonicalization_conformance.py tests/test_connected_health_schemas.py tests/test_phr_schemas_backcompat.py tests/test_router_audit_endpoints.py tests/test_auth_and_rbac.py tests/test_auth_extended_flow.py tests/test_auth_security_hardening.py` | `services/api` | `0` | **63 passed (100%)** | 38.13s |
| 5 | `node apps/web/scripts/check-consumer-terminology-contract.mjs` | repository root | `0` | 19 keys valid (2026-07-30.v1) | 0.08s |
| 6 | `node apps/web/scripts/generate-consumer-terminology.mjs --check` | repository root | `0` | Projections synchronized | 0.09s |
| 7 | `node packages/design-tokens/generate.js` | repository root | `0` | Hash `0e438d4f0908af78` verified | 0.12s |
| 8 | `uvx ruff check services/api/src/clara_api/core/route_inventory.py` | repository root | `0` | All checks passed | 0.15s |
| 9 | `uvx ruff format --check services/api/src/clara_api/core/route_inventory.py` | repository root | `0` | 1 file already formatted | 0.05s |
| 10 | `uvx mypy services/api/src/clara_api/core/route_inventory.py --ignore-missing-imports` | repository root | `0` | Success: no issues found | 0.45s |

---

## 5. Summary of Test Output

```text
tests/test_route_inventory_public_boundaries.py::test_known_public_liveness_and_capability_readers_are_allowlisted PASSED [ 50%]
tests/test_route_inventory_public_boundaries.py::test_every_unauthenticated_route_has_an_explicit_public_reason PASSED [100%]

============================== 2 passed in 6.65s ===============================
```

All boundary and inventory tests are now passing 100%. Zero unclassified public routes remain.

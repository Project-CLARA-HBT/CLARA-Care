# PH01-A01 Risk Register & Defect Log

**Phase:** PH01 (Python 3.12 Env Bootstrap & Defect Remediation)  
**Agent:** A01 (API + contract)  
**Worktree:** `/dev/shm/clara_worktrees/PH01_A01`  
**Branch:** `phase/ph01-a01`  
**Base SHA:** `2aa9016a57b49b53f1a433d076e1028a6ec45f64`  
**Date:** 2026-10-21  

---

## Risk Summary Matrix

| Risk ID | Title | Category | Severity | Likelihood | Impact | Status | Mitigation / Tracking |
|---|---|---|---|---|---|---|---|
| **DEFECT-01** | `POST /api/v1/auth/callback` missing from `INTENTIONAL_PUBLIC_ROUTES` | Contract / RBAC | High | Certain | Broke `test_route_inventory_public_boundaries.py` | **RESOLVED** | Added route to `INTENTIONAL_PUBLIC_ROUTES` in `route_inventory.py`. Tested green. |
| **RR-PH01-A01-01** | Host disk saturation causing SQLite temporary database lockup | Infrastructure / Test Runner | High | Medium | Tests writing to `/tmp` hang past 120s timeout due to kernel D-state I/O delays | **MITIGATED** | Enforced use of tmpfs via `CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/clara-test.db"`. |
| **RR-PH01-A01-02** | Starlette testclient & status code deprecations in Python 3.12 | Dependency / Deprecation | Low | High | Observational warnings during test runs | **CONTROLLED** | Starlette deprecation warnings (`HTTP_422_UNPROCESSABLE_ENTITY`, `httpx` import) documented; upstream updates planned in dependency maintenance cycles. |
| **RR-PH01-A01-03** | `PhrProfile` ORM model mismatch (`version_no=5`) during admin seeding | Data Model / ORM | Medium | Certain | Emits warning log during database initialization | **MONITORED** | Non-blocking warning originating in `seed_admin_clinical_data.py`. Logged for PH02/PH03 ORM reconciliation. |
| **RR-PH01-A01-04** | Operation ID collisions in OpenAPI schema generation | Contract / OpenAPI | Medium | High | Dual-mounted router aliases produce duplicate operation ID warnings | **MONITORED** | Preserved for backward-compatibility; client SDK generators should disambiguate by path. |

---

## Detailed Risk Assessments

### DEFECT-01 (RESOLVED): `POST /api/v1/auth/callback` in `INTENTIONAL_PUBLIC_ROUTES`
- **Location:** `services/api/src/clara_api/core/route_inventory.py:131`
- **Resolution:** Route `("POST", "/api/v1/auth/callback")` added to the `INTENTIONAL_PUBLIC_ROUTES` frozenset.
- **Verification:** `pytest tests/test_route_inventory_public_boundaries.py` passes 2/2 tests without failures.
- **Status:** **CLOSED / RESOLVED**

### RR-PH01-A01-01 (MITIGATED): SQLite Test Database I/O Contention
- **Description:** Default test configuration initializes SQLite databases under `/tmp`, which resides on the host root filesystem (`/dev/sda2`, 98% full). Concurrent disk writes trigger high filesystem sync delays, causing test timeouts.
- **Mitigation:** Setting `CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/clara-test.db"` redirects SQLite files to tmpfs, reducing test execution times from >120s to <7s.
- **Status:** **MITIGATED**

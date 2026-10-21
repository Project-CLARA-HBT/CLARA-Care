# PH00 / A07 — Risk Register: Tests & CI Infrastructure

**Phase:** PH00
**Agent:** A07 (Tests + CI)
**Frozen Base SHA:** `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`
**Date:** October 21, 2026
**Status:** COMPLETE

---

## 1. Overview

This risk register documents known vulnerabilities, test coverage gaps, execution environment disparities, and CI pipeline risks identified during the baseline inventory of the CLARA Care repository.

---

## 2. Identified Risks and Mitigations

### RISK-01: Mobile Flutter Test Suite Omitted from CI Workflows
- **Category:** CI / Automated Verification Gap
- **Severity:** HIGH (P1)
- **Description:**
  The mobile application has 94 test files in `apps/mobile/test/` covering critical user journeys, consent gates, offline caching, and PII-free analytics. However, `.github/workflows/mobile-apk.yml` only runs `flutter pub get` and `flutter build apk`, and `.github/workflows/ci.yml` does not include a Flutter test job. As a result, breaking mobile regressions can pass CI and merge undetected.
- **Root Cause:** Initial CI configuration focused on APK build artifact generation rather than headless widget test verification.
- **Affected Paths:** `apps/mobile/test/`, `.github/workflows/mobile-apk.yml`, `.github/workflows/ci.yml`.
- **Proposed Mitigation (PH01 / PH02):**
  Add a dedicated `mobile-test` job in `.github/workflows/ci.yml` (triggered on changes to `apps/mobile/**`) executing `flutter test --no-pub --coverage`.

---

### RISK-02: Test Module Name Collision in Evaluation Hierarchy
- **Category:** Test Suite Execution / Pytest Namespace Collision
- **Severity:** MEDIUM (P2)
- **Description:**
  Running recursive test collection across `evaluation/` fails with:
  `ERROR collecting evaluation/governance_adversarial/test_run.py: import file mismatch with evaluation/glhs_assurance/tests/test_run.py`.
  Both test files share the identical base name `test_run.py` without package isolation.
- **Root Cause:** Both test directories lack root package prefixes or distinct module names, causing pytest's import mechanism to register them under `sys.modules["test_run"]`.
- **Affected Paths:**
  - `evaluation/glhs_assurance/tests/test_run.py`
  - `evaluation/governance_adversarial/test_run.py`
- **Proposed Mitigation (PH01 / PH02):**
  Rename `evaluation/governance_adversarial/test_run.py` to `test_governance_adversarial_run.py` and `evaluation/glhs_assurance/tests/test_run.py` to `test_glhs_assurance_run.py`, or introduce `__init__.py` files to establish package boundaries.

---

### RISK-03: SQLite In-Memory / File Fallback Masking PostgreSQL Concurrency Invariants
- **Category:** Test Fidelity / Production Parity
- **Severity:** HIGH (P1)
- **Description:**
  All 1,894 tests in `services/api/tests/` (except two integration tests in `services/api/tests/integration/`) run against SQLite via `conftest.py` (`sqlite+pysqlite:///<temp_dir>/clara-test.db`). SQLite does not support row-level locking (`SELECT ... FOR UPDATE`), transactional outbox concurrency under high load, or PostgreSQL-specific native UUID and JSON operators.
- **Root Cause:** Fast local test execution prioritizes SQLite over containerized PostgreSQL.
- **Affected Paths:** `services/api/tests/conftest.py`, `services/api/tests/test_glhs_*.py`, `services/api/tests/test_lifemap_outbox_*.py`.
- **Proposed Mitigation:**
  Maintain SQLite for rapid local unit testing, but enforce mandatory PostgreSQL integration runs (`docker-compose-smoke` or dedicated PostgreSQL service) in CI before merge or release.

---

### RISK-04: Advisory PR Mode in CI May Permit Regressions on Main
- **Category:** CI Policy / Gate Enforcement
- **Severity:** HIGH (P1)
- **Description:**
  In `.github/workflows/ci.yml:970-986`, core test jobs (`quality`, `api-tests`, `ml-tests`, `web-e2e`) run in advisory mode on pull requests unless `CI_STRICT_PR_HARDENING=true`. If failing, they log warnings rather than failing the `required-ci-gates` consolidation step on PRs.
- **Root Cause:** Temporary accommodation for legacy test debt during early migration phases.
- **Affected Paths:** `.github/workflows/ci.yml:required-ci-gates`.
- **Proposed Mitigation:**
  Set repository-level variable `CI_STRICT_PR_HARDENING=true` once baseline test debt is cleared so that PRs fail closed.

---

### RISK-05: Web Test Suite Dependency on Pre-Installed `node_modules`
- **Category:** Environment Bootstrap / Hermeticity
- **Severity:** MEDIUM (P2)
- **Description:**
  In a fresh git checkout or worktree, `apps/web/node_modules` is not present. Executing Vitest or Playwright immediately fails (`MODULE_NOT_FOUND`). CI resolves this by invoking `npm ci` in `apps/web` with package-lock cache, but local execution requires explicit setup.
- **Root Cause:** Standard repository hygiene excludes `node_modules` from git tracking.
- **Affected Paths:** `apps/web/package.json`, `apps/web/vitest.config.ts`.
- **Proposed Mitigation:**
  Document clear bootstrap requirements in `Makefile` and developer onboarding scripts (assigned to PH01).

---

### RISK-06: Playwright E2E Standalone WebServer Build Overhead
- **Category:** CI Performance / Resource Exhaustion
- **Severity:** MEDIUM (P2)
- **Description:**
  `apps/web/playwright.config.ts:41-42` configures `webServer` to execute `npm run build && node .next/standalone/server.js` before launching tests. On single-core or memory-constrained runners, the Next.js production build can take 3-4 minutes and consume significant RAM, risking runner OOM or timeout.
- **Root Cause:** Playwright intentionally tests the exact production standalone build to verify CSS hydration and accessibility tree rendering.
- **Affected Paths:** `apps/web/playwright.config.ts`, `.github/workflows/ci.yml:web-e2e`.
- **Proposed Mitigation:**
  Maintain the 300s timeout floor, ensure worker concurrency remains `workers: 1`, and retain Playwright failure artifact uploads for debugging.

---

### RISK-07: Deprecation Warning on FastAPI / Starlette TestClient
- **Category:** Upstream Dependency Maintenance
- **Severity:** LOW (P3)
- **Description:**
  Test collection emits: `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`
- **Root Cause:** Newer versions of Starlette deprecate standard `httpx` bindings in favor of `httpx2`.
- **Affected Paths:** `services/api/pyproject.toml`, `services/ml/pyproject.toml`.
- **Proposed Mitigation:**
  Track dependency update in dependency lock synchronization (PH01 A02/A03).

---

## 3. Summary Risk Matrix

| Risk ID | Title | Severity | Impact | Owner / Target Phase |
|---|---|---|---|---|
| **RISK-01** | Mobile Flutter Test Suite Omitted from CI | HIGH (P1) | Mobile regressions slip into main | PH01 / PH02 (A06/A07) |
| **RISK-02** | Evaluation Test Module Name Collision (`test_run.py`) | MEDIUM (P2) | Recursive pytest collection breaks | PH01 / PH02 (A07) |
| **RISK-03** | SQLite Concurrency Masking PostgreSQL Invariants | HIGH (P1) | False-positive passing concurrency tests | PH00 / PH02 (A02/A07) |
| **RISK-04** | Advisory CI Mode on PRs Allowing Regression Merges | HIGH (P1) | Unchecked PR merges into main | PH01 / PH02 (A07/A10) |
| **RISK-05** | Web Test Suite Dependency on `npm ci` | MEDIUM (P2) | Local test runners fail without setup | PH01 (A04/A05) |
| **RISK-06** | Playwright E2E Next.js Build Resource Demand | MEDIUM (P2) | Runner timeouts during E2E runs | Ongoing |
| **RISK-07** | Starlette TestClient Deprecation Warning | LOW (P3) | Future library upgrade friction | PH01 (A02/A03) |

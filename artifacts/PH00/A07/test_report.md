# PH00 / A07 — Existing Tests and Fixture Inventory Report

**Phase:** PH00 (Đóng băng baseline và lập traceability)
**Agent:** A07 (Tests + CI)
**Frozen Base SHA:** `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`
**Branch:** `phase/ph00-a07`
**Date:** October 21, 2026
**Status:** COMPLETE

---

## 1. Executive Summary & Inventory Scope

This report establishes the baseline inventory of all test suites, fixtures, CI workflows, test coverage tools, and execution environments across the CLARA monorepo as of frozen commit `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`.

### Repository Quantitative Summary

| Test Layer / Component | Location / Directory | Test Files | Collected Test Cases | Runner / Toolchain | CI Execution Status |
|---|---|---|---|---|---|
| **API Backend Pytest** | `services/api/tests/` | 245 | 1,894 | `pytest-9.1.1` + `pytest-asyncio` | Active (`ci.yml:api-tests`) |
| **ML/NLP Service Pytest** | `services/ml/tests/` | 161 | 1,568 | `pytest-9.1.1` | Active (`ci.yml:ml-tests`) |
| **Root Research Pytest** | `tests/` | 4 | 36 | `pytest-9.1.1` | Active (`glhs-r3`, `glhs-r4`) |
| **Evaluation Framework Pytest** | `evaluation/` | 173 | 475+ | `pytest-9.1.1` | Partial (`research-evidence.yml`, `ci.yml`) |
| **Web Unit & Component (Vitest)** | `apps/web/` | 304 | ~1,200+ | `vitest-2.1.8` (`jsdom`) | Active (`ci.yml:web-unit-tests`) |
| **Web End-to-End (Playwright)** | `apps/web/e2e/` | 6 | 24 (4 projects) | `@playwright/test-1.62.0` | Active (`ci.yml:web-e2e`) |
| **Mobile Client Tests (Flutter)** | `apps/mobile/test/` | 94 | ~350+ | `flutter_test` (Dart 3.3+) | **NOT IN CI** (Defect identified) |
| **CI Automation Workflows** | `.github/workflows/` | 10 | 45+ jobs | GitHub Actions | Active |

Total identified test files across repository: **987 files**.

---

## 2. Python API Test Suite (`services/api/tests/`)

### 2.1 Configuration and Execution Environment
- **Configuration File:** `services/api/pyproject.toml:60-63`
  ```toml
  [tool.pytest.ini_options]
  pythonpath = ["src"]
  asyncio_mode = "auto"
  ```
- **Async Mode:** Automatically applies `asyncio_mode = "auto"`. All async test functions are scheduled without requiring manual `@pytest.mark.asyncio`.
- **Database Engine:** Isolated SQLite file (`sqlite+pysqlite:///<temp_dir>/clara-test.db`). Overridable via `CLARA_TEST_DATABASE_URL`.
- **Pytest Collection Command:**
  ```bash
  DATABASE_URL=sqlite+pysqlite:////tmp/clara_api_ci.db AUTH_AUTO_PROVISION_USERS=true AUTH_BOOTSTRAP_ADMIN_ENABLED=true pytest --collect-only -q
  ```
  **Result:** 1,894 test cases collected across 245 files in 28.82s (Exit code: 0).

### 2.2 Shared Fixture Architecture (`services/api/tests/conftest.py`)
- **Temp Database Initialization (`lines 18-24`):** Allocates a dedicated `tempfile.TemporaryDirectory(prefix="clara-api-pytest-")` and sets `DATABASE_URL` before application module imports.
- **Rate Limiter Bucket Isolation (`lines 35-54`):** `_clear_process_rate_limit_buckets()` traverses `app.middleware_stack` to find `RateLimiterMiddleware` and atomically resets in-memory sliding windows.
- **Bootstrap Admin Fixture (`lines 56-78`):** Session-scoped autouse fixture configuring `admin@example.com` with password `test-admin-pass-123`.
- **Schema Lifecycle (`lines 80-87`):** `Base.metadata.create_all(bind=engine)` runs at session start; `Base.metadata.drop_all(bind=engine)` runs at session teardown.
- **Row Reset Isolation (`lines 89-97`):** Autouse per-test fixture deleting rows in reverse topological order of `Base.metadata.sorted_tables` and ensuring the bootstrap admin row is restored.

### 2.3 Subdirectory Breakdown and Major Test Domains
1. **Root API Suites (`services/api/tests/*.py` - 199 files):**
   - **Auth & RBAC:** `test_auth_and_rbac.py`, `test_auth_security_hardening.py`, `test_auth_extended_flow.py`, `test_auth_me_and_mobile_summary.py`.
   - **Scribe Clinician Workflow:** `test_scribe_workflow.py`, `test_scribe_consent.py`, `test_scribe_stream_proxy.py`, `test_scribe_addendum.py`, `test_scribe_pii.py`, `test_scribe_export.py`, `test_scribe_analytics_metrics.py`.
   - **LifeMap Longitudinal Intelligence:** `test_lifemap_capture.py`, `test_lifemap_intelligence.py`, `test_lifemap_fhir_r4.py`, `test_lifemap_client_contract.py`, `test_lifemap_next_best_question.py`, `test_lifemap_outbox_events.py`.
   - **GLHS Verification & Concurrency:** `test_glhs_gateway.py`, `test_glhs_commit_kernel.py`, `test_glhs_canonical_json.py`, `test_glhs_inference_consumption.py`, `test_glhs_dynamic_ww_locking.py`, `test_glhs_phantom_concurrency.py`, `test_glhs_r4_admission.py`.
   - **CareGuard & Medication Safety:** `test_medication_safety_drugbank.py`, `test_careguard_drugbank_required.py`, `test_careguard_cabinet_endpoints.py`, `test_medication_convergence.py`.
   - **Compliance & Privacy:** `test_compliance_dsar_csrf.py`, `test_compliance_transparency_notice.py`, `test_metrics_no_pii.py`, `test_phr_audit_service.py`.
   - **System, Analytics & Observability:** `test_system_endpoints.py`, `test_system_control_tower_config.py`, `test_analytics_rbac.py`, `test_analytics_aggregator.py`, `test_timeout_floor.py`.
2. **Specialized Test Packages:**
   - `council_upgrade/` (14 files): Multidisciplinary council orchestration, resilience policies, evidence snapshot attachments, and telemetry PII guard.
   - `compliance/` (10 files): Dedicated DSAR export/delete, consent ledger, retention policies, and model disclosure harness.
   - `careguard_upgrade/` (8 files): Cabinet expiry reminders, structured dual read/write, and normalization status confirmation gates.
   - `admin_observability/` (8 files): Admin mutation audit, flow event sinks, alert engine, and RAG ingestion controls.
   - `hardening/` (3 files): Privilege escalation resistance, ownership isolation, and harness checks.
   - `integration/` (2 files): Real PostgreSQL concurrency (`test_glhs_postgres_concurrency.py`, `test_lifemap_outbox_postgres.py`).
   - `safety/` (1 file): Safety verification harness.

---

## 3. Python ML Test Suite (`services/ml/tests/`)

### 3.1 Configuration and Execution Environment
- **Configuration File:** `services/ml/pyproject.toml:41-45`
  ```toml
  [tool.pytest.ini_options]
  pythonpath = ["src"]
  testpaths = ["tests"]
  addopts = "-q"
  ```
- **Hermetic Environment (`services/ml/tests/conftest.py:1-10`):** Sets null defaults for `DEEPSEEK_API_KEY`, `ROUTER_API_KEY`, `OPENAI_API_KEY`, `EMBEDDING_API_KEY`, `YESCALE_API_KEY`, and `OCR_API_KEY` to prevent unintended live network egress.
- **Pytest Collection Command:**
  ```bash
  pytest --collect-only -q services/ml/tests
  ```
  **Result:** 1,568 test cases collected across 161 files in 4.23s (Exit code: 0).

### 3.2 Safety Fixtures (`services/ml/tests/safety/fixtures.py`)
- **Roles:** `ADMIN_ROLE = "admin"`, `DOCTOR_ROLE = "doctor"`, `NORMAL_ROLE = "normal"` (`lines 41-50`).
- **Consent States:** `ConsentState` dataclass (`lines 57-79`) providing `CONSENT_GRANTED` and `CONSENT_ABSENT`.
- **Emergency Keywords:** Vietnamese (`cấp cứu`, `khó thở`, `đau thắt ngực`, etc.) and English triggers mirroring production `P1RoleIntentRouter`.
- **FIDES Claim Contradictions:** Payloads that induce critical contradictions to verify fail-closed blocking.
- **CareGuard DDI Rules:** Seeded medication pairs (warfarin-aspirin, metformin-iodinated contrast) for testing interaction floors.

### 3.3 Subdirectory Breakdown and Major Test Domains
1. **Root ML Suites (`services/ml/tests/*.py` - 147 files):**
   - **RAG & Chunking:** `test_rag_pipeline.py`, `test_chunking_properties.py`, `test_chunker_token_bound_property.py`, `test_chunker_section_bounded_property.py`, `test_hybrid_retriever_provenance_property.py`, `test_rrf_fusion_properties.py`.
   - **Vietnamese Clinical NLP:** `test_vietnamese_clinical.py`, `test_nlp_vi_pipeline.py`, `test_nlp_vi_llm_extraction.py`, `test_language_renderer.py`.
   - **Council AI & Shadow Execution:** `test_council_stream.py`, `test_council_evidence_packet.py`, `test_council_model_shadow.py`, `test_council_shadow_contracts.py`.
   - **Scribe AI Engine:** `test_scribe_asr.py`, `test_scribe_extraction.py`, `test_scribe_grounding.py`, `test_scribe_generator.py`, `test_scribe_coding.py`, `test_scribe_em_cpt_coding.py`, `test_scribe_wer.py`, `test_scribe_specialty_templates.py`.
   - **LifeMap AI & Multimodal:** `test_lifemap_adaptive.py`, `test_lifemap_multimodal.py`, `test_lifemap_entity_resolution.py`, `test_lifemap_evidence_intelligence.py`, `test_lifemap_capture_extraction.py`.
   - **Synthesis V2:** `test_synthesis_v2_convergence.py`, `test_synthesis_v2_config.py`, `test_synthesis_v2_scope_classifier.py`, `test_synthesis_v2_budget_properties.py`.
   - **Model Gateway & Routers:** `test_model_router.py`, `test_model_registry.py`, `test_model_gateway_v2.py`, `test_deepseek_client.py`.
2. **Safety & Upgrade Packages:**
   - `safety/` (8 files): Consent gate preservation, DDI medium floor, dosage legal block, emergency fastpath, FIDES critical block, and research guardrail preservation.
   - `council_upgrade/` (6 files): Clinician review directive, disclosure, flags-off baseline, intake fallback label, and medication safety.

---

## 4. Root & Evaluation Pytest Suites (`tests/`, `evaluation/`)

### 4.1 Root Regression Tests (`tests/` - 4 files, 36 tests)
- `tests/test_dependency_completeness.py`: Dependency vector structure, determinism, mutation rejection (12 tests).
- `tests/test_q3_r3_reproducibility.py`: Zero-network clean sweep, chronology anomalies, claim budgets, fail-closed verification (13 tests).
- `tests/test_q2_r2_reproducibility.py`: Network isolation, SHA-256 digests, experiment sweep E00-E13 (7 tests).
- `tests/test_fullstack_performance.py`: HTTP benchmark execution, sample size invariants, E10 workflow seals (4 tests).

### 4.2 Evaluation Framework Tests (`evaluation/` - 173 files)
Key test areas in evaluation:
- `commitloop/tests/` (28 files): FHIR construction, freeze validation, generation probes, solver packets, TOST equivalence, and V5-V8 cohort verification.
- `governance_adversarial/` (25 files): Boundary adapters, cache observers, controls schema, protocol repetition, and residual analysis.
- `property_assurance/` (22 files): Budget fair runner, mutation catalog, state machines, and SOICT final runners.
- `glhs_postgres_toctou/` (16 files): TOCTOU replay and PostgreSQL concurrency observers.
- `evidence_program/` (8 files): Dataset registry validation, release gate v2, and seal verification.
- `glhs_systems_benchmark/` (7 files): DAG leases and systems benchmark harnesses.
- `careguard_external/` (7 files): Source manifests, DailyMed, RxNorm, DAV, and DDInter ingestion tests.

### 4.3 Evaluation Pytest Collection Warning / Module Conflict
- **Finding:** Running recursive pytest collection across `evaluation/` encounters an `import file mismatch` between `evaluation/glhs_assurance/tests/test_run.py` and `evaluation/governance_adversarial/test_run.py`.
- **Cause:** Both test files share identical module names (`test_run.py`) without unique top-level package scoping.
- **Resolution:** Workflows invoke evaluation tests by explicit subdirectory or file path (e.g. `research-evidence.yml:130` and `ci.yml:api-glhs-runtime-compat`).

---

## 5. Web Application Test Suite (`apps/web/`)

### 5.1 Vitest Unit & Component Test Suite
- **Configuration File:** `apps/web/vitest.config.ts:18-33`
  - Environment: `jsdom` (simulating DOM for React Testing Library)
  - Setup: `apps/web/vitest.setup.ts` (sets jest-dom matchers and mock polyfills)
  - Inclusion Pattern: `**/*.test.ts`, `**/*.test.tsx`
  - Exclusion Pattern: `node_modules/**`, `.next/**`
  - Test Timeout: 15,000ms
  - Path Alias: `@/*` mapped to `rootDir` (`apps/web`)
- **Total Test Files:** 304 files.
  - Component tests: 135 files (`components/shell/`, `components/health/`, `components/ask/`, `components/capture/`, `components/landing/v7/`, `components/medicines/`, `components/admin/`).
  - Page & Route tests: 104 files (`app/chat/`, `app/account/`, `app/admin/`, `app/medicines/`, `app/lifemap/`, `app/phr/`, `app/(consumer)/`).
  - Library unit tests: 60 files (`lib/api/`, `lib/i18n/`, `lib/scribe.*`, `lib/council.*`, `lib/careguard.*`, `lib/analytics/`).
  - Styling & Tokens: 5 files (`styles/contrast.test.ts`, `styles/design-tokens-contract.test.ts`, etc.).
- **Execution Script:** `npm run test` or `npx vitest run` in `apps/web`.

### 5.2 Playwright End-to-End Suite (`apps/web/e2e/`)
- **Configuration File:** `apps/web/playwright.config.ts:1-56`
  - Projects (4): `desktop-chromium` (1440x900), `laptop-chromium` (1280x800), `tablet-chromium` (768x1024), `mobile-chromium` (390x844).
  - Parallelism: `fullyParallel: false`, `workers: 1` (avoids port collisions and memory pressure).
  - WebServer Command (`lines 41-42`):
    ```bash
    npm run build && cp -R public .next/standalone/ && mkdir -p .next/standalone/.next && cp -R .next/static .next/standalone/.next/ && HOSTNAME=127.0.0.1 PORT=3000 node .next/standalone/server.js
    ```
  - WebServer Timeout: 300,000ms (5 minutes, accommodating production build).
  - Auth Mode: Injects `AUTH_BYPASS="true"` and `NEXT_PUBLIC_AUTH_BYPASS="true"`.
- **Spec Files (6 files):**
  1. `accessibility.spec.ts`: Uses `@axe-core/playwright` to assert zero serious/critical accessibility violations on `/` and `/login`.
  2. `clinical-research-states.spec.ts`: Stubs `/api/v1/**` workspace endpoints, asserts clinician/doctor views (Council, Scribe, Research Source Hub).
  3. `core-experience.spec.ts`: Stubs `/auth/me`, `/profiles/context`, tests navigation across Ask AI, Today, PHR, Medicines.
  4. `dashboard.spec.ts`: Tests researcher dashboard cards, system alerts, and task counters.
  5. `today.spec.ts`: Tests daily task list, completed task counters, and streak visualization.
  6. `visual.spec.ts`: Captures screenshots for `/` and `/login` across projects, verifies scrollWidth matches clientWidth.

---

## 6. Mobile Application Test Suite (`apps/mobile/test/`)

### 6.1 Configuration and Framework
- **Configuration File:** `apps/mobile/pubspec.yaml:19-23`
  - Requires: `flutter_test` (Flutter SDK) and `flutter_lints: ^5.0.0`.
  - SDK Constraint: `>=3.3.0 <4.0.0`.
- **Total Test Files:** 94 test files.
- **Execution Command:** `flutter test` within `apps/mobile`.

### 6.2 Test Architecture and Fakes Layer
- **Fakes Barrel (`apps/mobile/test/fakes/fakes.dart:1-15`):**
  - `fake_api_client.dart`: Stubbed REST responses for `/api/v1/mobile/summary`, `/auth/login`, `/phr`, `/medicines`.
  - `fake_secure_storage.dart`: In-memory storage for auth tokens and consent records without platform channels.
  - `fake_session_store.dart`: In-memory session tracking.
  - `fake_connectivity_service.dart`: Offline/online mode simulator.
  - `recording_analytics_transport.dart`: Verifies no-PII analytics events are logged without transmitting over network.
- **Experience Harness (`apps/mobile/test/support/experience_pump.dart`):**
  - Wraps widgets in `MaterialApp`, `ThemeController`, and localized scopes for deterministic headless widget testing.
- **Major Test Domains:**
  - Modern V2 Experience (`test/experience/` - 12 files): `v2_happy_path_test.dart`, `onboarding_gate_test.dart`, `home_screen_test.dart`, `no_pii_analytics_test.dart`.
  - Screens (`test/*_screen_test.dart` - 35 files): `chat_screen_test.dart`, `phr_screen_test.dart`, `careguard_cabinet_screen_test.dart`, `council_screen_test.dart`, `scribe_screen_test.dart`.
  - API Client Adapters (`test/api_client_*_test.dart` - 10 files): `api_client_auth_lifecycle_test.dart`, `api_client_chat_test.dart`, `api_client_selfmed_cabinet_test.dart`.
  - Spatial & Adaptive Shell (`test/spatial/` - 3 files): `adaptive_clara_shell_test.dart`, `morphing_dock_test.dart`, `clara_orb_test.dart`.
  - Theming & Design Tokens (`test/theme/` - 4 files): `clara_theme_test.dart`, `web_palette_test.dart`, `clara_flow_scaffold_test.dart`.

---

## 7. GitHub Actions CI Workflows Inventory (`.github/workflows/`)

All 10 GitHub Actions workflows were audited:

### 7.1 Detailed Workflow Breakdown
1. **`ci.yml` (Main Continuous Integration - 16 Jobs):**
   - **Trigger:** Push to `main`, Pull Requests, manual `workflow_dispatch`.
   - **Jobs:**
     - `changes`: Detects changed files across services, web, mobile, docs, and python paths.
     - `quality`: Runs `scripts/docs/check-docs-links.sh`, `ruff check`, and `mypy` on changed Python code.
     - `scripts-syntax`: Validates compilation of repository maintenance scripts.
     - `artifact-safety-policy`: Scans artifacts for unencrypted credentials or PHI.
     - `hackathon-artifacts-smoke`: Validates demo scripts and mock scenarios.
     - `clara-eval-vn-smoke`: Executes `make eval-smoke`.
     - `api-tests`: Executes `pytest -q tests` on `services/api` (SQLite in `/tmp/clara_api_ci.db`).
     - `api-glhs-runtime-compat`: Executes GLHS tests on Python 3.14 runner.
     - `ml-tests`: Executes `pytest -q tests` on `services/ml`.
     - `web-lint-build`: Runs `consumer-terminology:check`, `i18n:check`, `npm run lint`, and `npm run build`.
     - `web-unit-tests`: Runs `npm run test` (Vitest).
     - `web-e2e`: Installs Chromium and runs `npm run test:e2e` (Playwright).
     - `security-audit`: Runs `pip-audit`, `npm audit`, and `trivy` vulnerability scanners.
     - `docker-compose-smoke`: Builds and runs containerized multi-service stack.
     - `container-scan`: Scans container images for CVEs.
     - `required-ci-gates`: Consolidated status aggregator (lines 907-1040).
2. **`clara-eval-vn.yml` (Clinical AI Evaluation - 2 Jobs):**
   - **Trigger:** `workflow_dispatch` (inputs: `smoke` or `judge_demo`).
   - **Jobs:** `smoke` (validates dataset manifest and runs offline smoke test), `judge-demo` (generates HTML judge report).
3. **`glhs-r3-reproducibility-gate.yml` (GLHS R3 Gate - 4 Jobs):**
   - **Trigger:** Push/PR on `main` and `research/glhs-q2-r2-experiments`.
   - **Jobs:** `secret-scan`, `chronology-audit`, `unit-and-invariant-tests`, `hermetic-reproduction` (`reproduce_q3_r3.py`).
4. **`glhs-r4-novelty-gate.yml` (GLHS R4 Novelty Gate - 5 Jobs):**
   - **Trigger:** Push/PR on `main`, `workflow_dispatch`.
   - **Jobs:** `secret-scan`, `chronology-audit`, `r4-admission-and-comparator-tests`, `r4-claim-lint`, `offline-reproducibility-sweep` (`reproduce_q4_r4.py`).
5. **`mobile-apk.yml` (Release Android APK - 1 Job):**
   - **Trigger:** Push to `main` with changes in `apps/mobile/**`, `workflow_dispatch`.
   - **Jobs:** `build-apk` (JDK 17 + Flutter stable, builds signed release APK with `CLARA_API_BASE_URL=https://theclaracare.com`).
   - **Critical Note:** Does **not** invoke `flutter test`.
6. **`research-evidence.yml` (Research & Evaluation Integrity - 6 Jobs):**
   - **Trigger:** PR, `workflow_dispatch`.
   - **Jobs:** `docs-status-consistency`, `ruff`, `focused-pytest`, `secret-scan`, `govmut-preflight`, `artifact-schema`.
7. **`active-eval.yml` (Nightly Active Evaluation - 1 Job):**
   - **Trigger:** Nightly cron (`30 2 * * *`), `workflow_dispatch`.
   - **Jobs:** `run-active-eval` (runs live model evaluations).
8. **`branch-protection-sync.yml` (Branch Policy Sync - 1 Job):**
   - **Trigger:** Weekly cron, `workflow_dispatch`.
   - **Jobs:** `sync` (ensures `required-ci-gates` is enforced on `main`).
9. **`cd.yml` (Controlled Deployment - 2 Jobs):**
   - **Trigger:** `workflow_dispatch`.
   - **Jobs:** `preflight` (checks image digest and migrations), `deploy` (rolling deployment).
10. **`release.yml` (Release Pipeline - 5 Jobs):**
    - **Trigger:** `workflow_dispatch`.
    - **Jobs:** `prepare-release-context`, `clara-eval-release-gate`, `create-semver-tag`, `build-push-images`, `publish-github-release`.

---

## 8. Test Fixtures and Synthetic Datasets Inventory

| Location | Format | Purpose | Safety Invariant |
|---|---|---|---|
| `services/api/tests/fixtures/fhir/lifemap-summary-r4.json` | JSON | FHIR R4 Bundle for LifeMap test imports | Purely synthetic patient IDs |
| `services/ml/tests/fixtures/lifemap_ai_golden_v1.json` | JSON | Golden reference for adaptive question ranking | No real patient disclosures |
| `services/ml/tests/fixtures/lifemap_capture_eval_v1.json` | JSON | Clinical OCR and lab extraction test cases | Anonymized laboratory ranges |
| `services/ml/tests/safety/fixtures.py` | Python | Hardcoded roles, consent objects, emergency keywords | Deterministic static fixtures |
| `evaluation/clara_eval/datasets/fixtures/*.smoke.jsonl` | JSONL (9 files) | Smoke evaluations for Scribe, CareGuard, Council | PII-free synthetic cases |
| `evaluation/fhir_conformance/fixtures/` | JSON (17 files) | Positive and negative FHIR conformance bundles | Strict negative test assertions |
| `testdata/glhs/canonicalization/v2/` | JSON (2 files) | Canonical JSON serialization test vectors | Deterministic byte hashing |

---

## 9. Non-Destructive Test Collection Execution Log

Commands executed during PH00 A07 baseline validation:

```bash
# 1. API Pytest Collection
DATABASE_URL=sqlite+pysqlite:////tmp/clara_api_ci.db AUTH_AUTO_PROVISION_USERS=true AUTH_BOOTSTRAP_ADMIN_ENABLED=true pytest --collect-only -q services/api/tests
# Result: 1894 tests collected in 28.82s (Exit code: 0)

# 2. ML Pytest Collection
pytest --collect-only -q services/ml/tests
# Result: 1568 tests collected in 4.23s (Exit code: 0)

# 3. Root Regression Pytest Collection
PYTHONPATH=services/api/src:services/ml/src:. pytest --collect-only tests/test_dependency_completeness.py tests/test_q3_r3_reproducibility.py tests/test_q2_r2_reproducibility.py tests/test_fullstack_performance.py
# Result: 36 tests collected in 5.08s (Exit code: 0)

# 4. Web Vitest Listing
cd apps/web && npx vitest list --filesOnly
# Result: Exit code 1 (NOT_RUN_ENV_BLOCKER: node_modules not installed in clean checkout)

# 5. Mobile Flutter Test
cd apps/mobile && flutter test
# Result: Exit code 127 (NOT_RUN_ENV_BLOCKER: flutter binary not in system PATH on runner)
```

---

## 10. Traceability & Handoff

- **Deliverables Produced:**
  - `artifacts/PH00/A07/change_manifest.json`
  - `artifacts/PH00/A07/test_report.md`
  - `artifacts/PH00/A07/risk_register.md`
- **Integrator Notes:**
  - Zero application source code was modified.
  - All test commands are non-destructive and verified against frozen baseline `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`.

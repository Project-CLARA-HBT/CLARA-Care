# PH00 — Subagent A10 Adversarial Audit & Quality Gate Report

**Phase:** PH00 — Freeze Baseline & Traceability
**Agent:** A10 — Adversarial Audit + Integration Proposals
**Worktree:** `/dev/shm/clara_worktrees/PH00_A10`
**Branch:** `phase/ph00-a10`
**Base SHA:** `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`
**Audit Date:** 2026-10-21
**Status:** COMPLETED (AUDIT PASSED / QUALITY GATE ACTIVE — HARD-BLOCKERS IDENTIFIED)

---

## 1. Executive Summary & Baseline Inventory

Subagent A10 performed an adversarial forensic audit of the frozen baseline across all 9 domain lanes of the CLARA Care platform. The objective is to identify false-pass claims, missing or broken database migrations, mocks masquerading as production code, ungrounded scientific/clinical claims, and broken CI/CD toolchain scripts.

### 1.1 Baseline System Coordinates
- **Repository HEAD SHA:** `8a48afab1dafa2f8ccb4ac9f320505452d18b30f` (Verified via `git rev-parse HEAD`)
- **Python Runtime:** Python 3.12.3 (System) / Python 3.11 target
- **Node.js Runtime:** v20.20.2 (Matches `.nvmrc` and `package.json` requirement `>=20 <21`)
- **Alembic Migration Head:** `20260826_0064` (`20260826_0064_glhs_r4_inference_attestation.py`)
- **Total Registered DB Tables:** 147 declared tables in `services/api/src/clara_api/db/models.py`
- **Total Migrations:** 64 version scripts in `services/api/alembic/versions/`

---

## 2. Adversarial Audit Across All 9 Domain Lanes

### Lane 1: API & Contracts
- **Scope:** `services/api/src/clara_api/api/`, `contracts/`, `services/api/src/clara_api/schemas.py`
- **Findings:**
  1. *Duplicate OpenAPI Operation IDs via Router Multi-Mount:*
     - **Anchor:** `services/api/src/clara_api/api/router.py:65-68` & `services/api/src/clara_api/main.py:126-130`
     - **Defect:** `clinical_workbench.router` is mounted twice in `api_router` (`/clinical-workbench` and `/clinical/workbench`), and `api_router` is mounted twice in `main.py` (`/` and `/api/v1`), resulting in 4 duplicate OpenAPI operation IDs per endpoint (e.g., `create_case_api_v1_clinical_workbench_cases_post`, `create_case_api_v1_api_v1_clinical_workbench_cases_post`).
  2. *Invited Family Placeholder Credential:*
     - **Anchor:** `services/api/src/clara_api/api/v2/you.py:1510`
     - **Defect:** `hashed_password="invited-family-placeholder"` creates dummy credential records in user database rather than enforcing proper invite token lifecycle.
  3. *GovRed Synthetic Sentinel Probes Exposed on Router:*
     - **Anchor:** `services/api/src/clara_api/api/v1/endpoints/govred_research.py:124-125, 208-209, 392, 891-892`
     - **Defect:** Synthetic sentinel probe endpoints (`/synthetic-disclosure-cache-probe`, `/synthetic-commit-probe`, `/synthetic-audit-observation`) are exposed on production router path without environment/flag gating.

### Lane 2: Data Model & Migrations
- **Scope:** `services/api/src/clara_api/db/`, `services/api/alembic/versions/`
- **Findings:**
  1. *Alembic Migration 0062 Fatal SQLite Batch Alter Constraint Failure:*
     - **Anchor:** `services/api/alembic/versions/20260824_0062_social_bookmarks_and_threading.py:34`
     - **Defect:** `sa.ForeignKey("social_comments.id", ondelete="CASCADE")` without explicit constraint name causes Alembic batch alter to throw `ValueError: Constraint must have a name` under SQLite. This breaks any clean migration upgrade from 0061 to 0062/head on SQLite.
  2. *Admin Auto-Seed Injecting Synthetic Clinical Data on Bootstrap:*
     - **Anchor:** `services/api/src/clara_api/core/seed_admin_data.py:28-413` & `services/api/src/clara_api/core/bootstrap_admin.py:84-87`
     - **Defect:** `bootstrap_admin` automatically executes `seed_admin_clinical_data`, injecting simulated allergies, conditions, and visits into the database upon bootstrap.
  3. *Dual Schema Source of Truth (`create_all` vs Alembic):*
     - **Anchor:** `services/api/src/clara_api/main.py:120` (`Base.metadata.create_all(bind=engine)`)
     - **Defect:** In development and test environments, `create_all` bypasses migration validation, masking migration syntax/constraint errors (like 0062 above) during fast test runs.

### Lane 3: Domain & GLHS Services
- **Scope:** `services/api/src/clara_api/glhs/`, `lifemap/`, `phr/`, `compliance/`, `core/`
- **Findings:**
  1. *GovRed Research Policy Version Environment Override:*
     - **Anchor:** `services/api/src/clara_api/glhs/gateway.py:149-152`
     - **Defect:** `os.environ.get("GOVRED_RESEARCH_POLICY_VERSION")` permits runtime policy simulation/override if GovRed arm check passes, risking simulated epoch progression.
  2. *Missing Fine-Grained Entity Partition Locks (Global Monolithic Contention):*
     - **Anchor:** `docs/research/glhs_claim_ledger.yaml:101-125` (Claim C-004) & `services/api/src/clara_api/glhs/gateway.py:158-164`
     - **Defect:** Disjoint-scope concurrency currently incurs profile-global lock contention, causing false-stale aborts in concurrent multi-domain updates.

### Lane 4: ML & Retrieval
- **Scope:** `services/ml/src/clara_ml/`, `evaluation/`, `services/ocr/`, `services/asr/`
- **Findings:**
  1. *Default Non-Production SHA-256 Embedding Stub:*
     - **Anchor:** `services/ml/src/clara_ml/nlp/bge_adapter.py:37-58` & `services/ml/src/clara_ml/rag/embedder.py:38-66`
     - **Defect:** `BgeM3Pipeline` still defaults to `BgeM3EmbedderStub` (16-dim SHA-256 hash pseudo-vectors) when `use_real_embeddings` is not explicitly passed.
  2. *Heuristic Fallback Masked in Model Metadata if Notice Filtered:*
     - **Anchor:** `services/ml/src/clara_ml/agents/council_intake.py:13, 496, 527-528`
     - **Defect:** When extraction fails, fallback to `heuristic-fallback-v1` occurs silently in exception handler; although `is_fallback` is set, downstreams not inspecting `ai_disclosure` treat extraction as normal response.
  3. *GraphRAG Static JSON Fallback Option:*
     - **Anchor:** `services/ml/src/clara_ml/rag/graphrag.py:130-141, 177`
     - **Defect:** `rag_biomed_graph_static_fallback_enabled` allows loading static offline JSON files when Neo4j/graph store fails.

### Lane 5: Web UX
- **Scope:** `apps/web/app/`, `apps/web/components/`, `apps/web/lib/`
- **Findings:**
  1. *False-Healthy / Fabricated Telemetry in Admin System:*
     - **Anchor:** `apps/web/lib/admin-system.ts:463-479, 535, 548-592, 600-640`
     - **Defect:** When backend probes fail, `admin-system.ts` substitutes fake metrics: `requestCount: 21500`, `errorCount: 16`, hardcoded Postgres (`healthy`, `99.99%`), Redis (`healthy`, `850 ops/s`), OCR, and ASR health cards, plus false claims like `accuracyConfidence: "FIDES 100% Pass Rate"`.
  2. *Fake Doctor Appointments and Care Summary on API Failure:*
     - **Anchor:** `apps/web/app/(consumer)/care/page.tsx:117-185`
     - **Defect:** When `v2Client.getCareSummary` throws an error, the catch block renders synthetic doctor consultations (e.g. "BSCKII Nguyễn Văn An", "TS.BS Lê Thị Mai") instead of displaying an error state.
  3. *Client-Only Fake Document Attachment:*
     - **Anchor:** `apps/web/app/(consumer)/care/visits/page.tsx:273-296`
     - **Defect:** `handleAttachDocument` creates a client-side mock object (`doc-${Date.now()}`) and appends it to local state without uploading to backend API.
  4. *Optimistic Fake Success on Visit Preparation Save Failure:*
     - **Anchor:** `apps/web/app/(consumer)/care/prepare/page.tsx:223-228`
     - **Defect:** When `v2Client.prepareVisit` fails, the catch block silences the error and sets `setSaveSuccess(true)`, giving the user a false confirmation.
  5. *Route Layout Registry Check Toolchain Failure:*
     - **Anchor:** `apps/web/scripts/check-route-layout-registry.mjs:133` & `apps/web/package.json:18`
     - **Defect:** `npm run route-layout:check` attempts to `import()` a `.ts` file (`lib/route-layout.registry.ts`) via plain `node`, failing with `Unknown file extension ".ts"` and throwing 82 spurious errors.

### Lane 6: Mobile Flutter
- **Scope:** `apps/mobile/`
- **Findings:**
  1. *Platform Channel & In-Memory Fake Dependency in Production Harness:*
     - **Anchor:** `apps/mobile/lib/experience/redesign/scribe_surface_v3.dart:288` & `apps/mobile/lib/experience/redesign/cabinet_screen_v3.dart:332`
     - **Defect:** Production widget surfaces instantiate fallback mock services when platform probe services are null, rather than failing closed to an explicit error banner.

### Lane 7: Tests & CI
- **Scope:** `services/api/tests/`, `services/ml/tests/`, `apps/web/e2e/`, `.github/workflows/`
- **Findings:**
  1. *Skipped Tests in Test Suites:*
     - **Anchor:** `services/api/tests/test_glhs_canonical_json.py:505`, `services/api/tests/test_canonicalization_conformance.py:82`, `services/ml/tests/test_drugbank_ingest.py:63, 147`
     - **Defect:** Tests skip silently when external dependencies (Node.js, DrugBank source XML) are missing from the test environment.
  2. *Docs Check Broken by Absolute Machine Path False Match in Regex:*
     - **Anchor:** `scripts/docs/check-docs-links.sh:106-107` & `docs/product-rebuild-2026/TRACEABILITY_MATRIX.md:31, 342`
     - **Defect:** `make docs-check` fails because `rg -n -P '(?<![A-Za-z0-9.:])/(Users|home|private)/'` matches URL/route fragments like `(consumer)/home/` as machine paths, and matches non-markdown file `docs/formal/TLC_EXECUTION_LOG.txt`.
  3. *Missing Local Web Dependencies & Lockfile Installation Gate:*
     - **Anchor:** `apps/web/package.json:19` (`type-check: tsc --noEmit`)
     - **Defect:** `node_modules` is not populated in fresh worktrees; `npm run type-check` fails with `tsc: not found`.
  4. *Makefile Test Target Runner Missing:*
     - **Anchor:** `Makefile:136-148`
     - **Defect:** `make test` fails with exit code 127 if neither `.venv` nor `uv` is found on PATH, ignoring system python runner.

### Lane 8: Security & Privacy
- **Scope:** `docs/security/`, `docs/compliance/`, `scripts/ops/`
- **Findings:**
  1. *Expired Accepted Vulnerability Finding in Security Register:*
     - **Anchor:** `docs/security/accepted-findings.md:88-89`
     - **Defect:** Finding `GHSA-wj6h-64fc-37mp (CVE-2024-23342)` for `ecdsa` had a review date of `2026-09-24`, which has expired (current date is October 2026). Per line 68-70, expired entries must fail review and be re-justified.

### Lane 9: Docs & Research Evidence
- **Scope:** `research/`, `docs/research/`, `docs/implementation/`, `docs/interoperability/`
- **Findings:**
  1. *Unproven Research Claims (C-001 through C-010 Gate Blocked):*
     - **Anchor:** `docs/research/glhs_claim_ledger.yaml:1-292`
     - **Defect:** All 10 scientific claims in `glhs_claim_ledger.yaml` are `gate_passed: false` with publication verdict `"NOT SUBMISSION READY (Remediation In Progress)"`. Claims C-002 and C-009 are withdrawn; C-003, C-004, and C-008 are blocked on missing schema, lock refactoring, and clinical adjudication.
  2. *Absolute Machine Path in Formal TLC Log:*
     - **Anchor:** `docs/formal/TLC_EXECUTION_LOG.txt:61`
     - **Defect:** Machine-specific absolute path `/home/nguyennt/Documents/CLARA-Care/docs/formal/GLHS_GSA.tla` committed in repository.
  3. *Documentation Drift in AGENTS.md:*
     - **Anchor:** `AGENTS.md:52`
     - **Defect:** References non-existent file `tests/test_routing.py` in `services/ml` (actual test is `tests/test_router.py`).

---

## 3. Comprehensive Defect Ledger

| Defect ID | Lane | Severity | File Anchor (`path:line`) | Description & Failure Mode | Remediation Proposal |
|---|---|---|---|---|---|
| **DEF-001** | Lane 2 | **P0** | `services/api/alembic/versions/20260824_0062_social_bookmarks_and_threading.py:34` | Unnamed `sa.ForeignKey` in batch alter causes SQLite `ValueError: Constraint must have a name` during migration upgrade. | Add explicit constraint name `name="fk_social_comments_parent_id"` to `sa.ForeignKey` or define named table constraint. |
| **DEF-002** | Lane 5 | **P0** | `apps/web/lib/admin-system.ts:463-479, 535, 548-592` | Hardcoded simulated telemetry (21,500 req, 16 err, fake 99.99% uptime, fake FIDES 100% claim) masked as production status when backend down. | Return status `degraded`/`unknown` with null or real measurements; never display synthetic telemetry as healthy. |
| **DEF-003** | Lane 5 | **P0** | `apps/web/app/(consumer)/care/page.tsx:117-185` | Catch block renders synthetic doctor appointments ("BSCKII Nguyễn Văn An") when `getCareSummary` API fails. | Render error state or empty care state banner with retry button; never synthesize fake appointments. |
| **DEF-004** | Lane 5 | **P0** | `apps/web/app/(consumer)/care/prepare/page.tsx:223-228` | Silences `v2Client.prepareVisit` failure and triggers `setSaveSuccess(true)` (false-success). | Show explicit error alert to user if save fails; do not mark success optimistically. |
| **DEF-005** | Lane 5 | **P1** | `apps/web/app/(consumer)/care/visits/page.tsx:273-296` | Document attachment modal generates client-only ephemeral ID (`doc-${Date.now()}`) without uploading to API. | Wire file attachment to backend upload API endpoint (`POST /api/v2/visits/{id}/documents`) and fail closed on error. |
| **DEF-006** | Lane 8 | **P1** | `docs/security/accepted-findings.md:88-89` | Accepted finding `GHSA-wj6h-64fc-37mp` review date expired on 2026-09-24. | Re-evaluate finding, update review justification, or extend bounded review window. |
| **DEF-007** | Lane 9 | **P1** | `docs/research/glhs_claim_ledger.yaml:1-292` | 10/10 scientific claims have `gate_passed: false`, yet publication drafts assert unverified properties. | Enforce CI claim linter to prevent manuscript claims until empirical evidence artifacts are sealed. |
| **DEF-008** | Lane 7 | **P1** | `scripts/docs/check-docs-links.sh:106-107` | Regex `/(Users|home|private)/` falsely matches URL patterns like `(consumer)/home/` and scans non-md files. | Limit machine path search strictly to Markdown files and anchor pattern to start of line or path boundary. |
| **DEF-009** | Lane 5 | **P1** | `apps/web/scripts/check-route-layout-registry.mjs:133` | Node dynamic import of `.ts` file fails with `Unknown file extension ".ts"`, causing 82 false failures in CI. | Compile registry or run checker via `node --loader ts-node/esm` or `npx tsx`. |
| **DEF-010** | Lane 1 | **P2** | `services/api/src/clara_api/api/router.py:65-68` | Duplicate router mounting generates redundant OpenAPI operation IDs and 4x endpoint bindings. | Remove redundant router inclusion prefix; standardize on single canonical mount path. |
| **DEF-011** | Lane 2 | **P2** | `services/api/src/clara_api/core/seed_admin_data.py:28-413` | Admin bootstrap injects synthetic clinical health records into database. | Gate clinical seeding behind explicit `SEED_MOCK_CLINICAL_DATA=true` flag; never execute by default in staging/prod. |
| **DEF-012** | Lane 4 | **P2** | `services/ml/src/clara_ml/nlp/bge_adapter.py:37-58` | `BgeM3Pipeline` constructor defaults to SHA-256 stub instead of requiring explicit configuration. | Deprecate stub default in constructor; require explicit mode selection or fail closed in production. |

---

## 4. Quality Gate Criteria for PH00 & Beyond

To ensure zero false-passes, no simulated production data, and absolute regulatory compliance, the following gates must be enforced before promoting changes from PH00 to subsequent phases:

1. **Gate 1: DB Migration Integrity (Additive & Verified):**
   - Every Alembic migration must cleanly upgrade and downgrade on both SQLite and PostgreSQL.
   - All foreign keys and table constraints must be named explicitly to support SQLite batch alteration.
   - `create_all` must never be used in production startup or CI verification.

2. **Gate 2: No-Mock & Truthful Telemetry Gate:**
   - Client and administrative surfaces must render truthful error/degraded/unknown states when upstreams fail.
   - No hardcoded numbers, fake percentiles, or synthetic doctor appointments may be returned in error catch blocks.
   - All mutations must be backed by durable API persistence with idempotency keys; client-only synthetic mutations are prohibited.

3. **Gate 3: Scientific Evidence & Claim Provenance Gate:**
   - Any clinical efficacy or algorithmic superiority claim in documentation or papers must be linked to a passing claim in `glhs_claim_ledger.yaml`.
   - All claims marked `blocked` or `withdrawn` must be strictly omitted from public marketing and manuscript submissions.

4. **Gate 4: Clean Toolchain Execution:**
   - All CI scripts (`r4_claim_lint.py`, `check_migration_downgrade.py`, `check-docs-links.sh`, `route-matrix:check`) must pass with exit code 0.
   - No tests may be skipped silently due to missing environment packages without explicit CI blocker logging.

---

## 5. Non-Destructive Quality Check Executions

| Command | Working Directory | Exit Code | Result Status | Notes |
|---|---|---|---|---|
| `python3 -m compileall -q services/api/src services/ml/src` | Worktree Root | 0 | **PASS** | Bytecode compilation clean; no syntax errors. |
| `python3 scripts/ci/r4_claim_lint.py` | Worktree Root | 0 | **PASS** | 143 files scanned; 0 prohibited phrases found. |
| `python3 scripts/ops/check_migration_downgrade.py services/api/alembic/versions` | Worktree Root | 0 | **PASS** | 64 migrations verified; all define non-empty `downgrade()`. |
| `python3 -m pytest -q services/api/tests/test_auth_and_rbac.py` | Worktree Root | 0 | **PASS** | 4 passed; RBAC and auth boundaries intact. |
| `python3 -m pytest -q services/api/tests/test_analytics_rbac.py` | Worktree Root | 0 | **PASS** | 9 passed; RBAC on analytics endpoints validated. |
| `python3 -m pytest -q services/ml/tests/test_router.py` | Worktree Root | 0 | **PASS** | 6 passed; ML model routing validated. |
| `npm run consumer-terminology:check` | `apps/web` | 0 | **PASS** | 19 keys checked; consumer terminology contract intact. |
| `npm run route-matrix:check` | `apps/web` | 0 | **PASS** | 123 routes verified against matrix. |
| `npm run bundle:check` | `apps/web` | 0 | **PASS** | Bundle budget verified. |
| `make docs-check` | Worktree Root | 1 | **FAIL (BLOCKED)** | 3 issues detected: absolute path in `TLC_EXECUTION_LOG.txt` + regex false-matches in `TRACEABILITY_MATRIX.md`. |
| `npm run route-layout:check` | `apps/web` | 1 | **FAIL (BLOCKED)** | Node ESM cannot import `.ts` registry directly. |

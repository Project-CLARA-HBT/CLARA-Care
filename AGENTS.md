# AGENTS.md

Guidance for AI coding agents working in the CLARA monorepo. Full architecture, service reference, and runtime details live in `CLAUDE.md`.

## Core Identity & Safety Invariants (Regression-Locked)

CLARA is a Vietnamese, safety-first Medical AI Assistant — **a clinical assistant, not a doctor replacement**. Never weaken, bypass, or mock safety guardrails to make changes pass:
- **RBAC**: `require_roles(...)` (`services/api/.../core/rbac.py`) gates routes; `admin` has implicit access, others get 403.
- **Consent Gate**: Versioned medical consent precedes medical content on End_User surfaces.
- **Emergency Fast-Path**: Acute-symptom queries return escalation immediately, skipping diagnostic reasoning.
- **FIDES Verification**: Failed `CRITICAL` drug-dosage/DDI claims block the response.
- **Legal Hard-Guard**: ML blocks prescribing / diagnosis / personal-dosage intents (vi/en).
- **CSRF**: Enforced on cookie-authenticated mutations. Bearer exemption requires a valid, non-revoked credential parsed identically to RBAC; malformed Bearer headers fail rather than falling back to cookie auth.
- **No-PII Telemetry**: System metrics, flow events, and analytics exclude PII (names, emails, queries, drug lists). Telemetry labels and upstream errors are sanitized out of End_User views.

## Monorepo Architecture & Entry Points

Request path: **Web (`apps/web`) → API (`services/api`, port 8000/8100) → ML (`services/ml`, port 8010/8110, via `X-ML-Internal-Key`)**.
- `apps/web`: Next.js 15, React 18, TypeScript. Auth uses HttpOnly session cookies + CSRF tokens (never persist bearer tokens in browser storage).
- `services/api`: FastAPI gateway (`src/clara_api/main.py`, `api/router.py`). Router is mounted at `/` and double-mounted at `/api/v1` for backward compatibility.
- `services/ml`: FastAPI orchestration (`src/clara_ml/main.py`, `rag/pipeline.py`, `agents/research_tier2.py`).
- `services/ocr`: Thin FastAPI adapter over Google Cloud Vision (`DOCUMENT_TEXT_DETECTION`). No local model/GPU.
- `services/asr`: FastAPI + `faster-whisper` exposing `POST /v1/audio/transcriptions` for Scribe audio.
- `apps/mobile`: Flutter client (`apps/mobile/lib/main.dart`).

## Environment & Toolchain Gotchas

- **Python Runners**: `make lint`, `make type-check`, and `make test` look for `services/api/.venv` first, then fall back to `uv` or system PATH. If missing, set up a venv (`python3 -m venv services/api/.venv && services/api/.venv/bin/pip install -e ".[dev]"`) or run via system `pytest`.
- **Web Dependencies**: Run `cd apps/web && npm ci` before executing any web scripts if `node_modules` is missing.
- **Alembic Migrations**: Run via `(cd services/api && alembic upgrade head)` with versions in `services/api/alembic/versions/`. **Every migration must define a non-empty `downgrade()`**; verified by `python3 scripts/ops/check_migration_downgrade.py services/api/alembic/versions`.
- **LLM Runtime**: DeepSeek-only by default (`LLM_DEEPSEEK_ONLY=true`). Task registry maps tasks to `DEEPSEEK_PRO_MODEL` and `DEEPSEEK_FLASH_MODEL`. Audio models use `DEEPSEEK_AUDIO_MODEL=whisper-1` / ASR service, never V4 text. Request-level `llm_runtime` payloads are discarded server-side.
- **Startup Timeout Guard**: Enforces `ML_SERVICE_TIMEOUT_SECONDS >= DEEPSEEK_TIMEOUT_SECONDS` and sync-research `>= ML_RESEARCH_TIMEOUT_SECONDS`.

## Focused Verification Commands

Run checks closest to your changes before widening:

### Python Services (`services/api`, `services/ml`)
- Linting: `make lint` or `ruff check services/api/src services/api/tests services/ml/src services/ml/tests scripts --extend-ignore B008`
- Type checking: `make type-check` or `mypy services/api/src services/ml/src --ignore-missing-imports`
- All tests: `make test`
- Single API test: `(cd services/api && pytest tests/test_auth_and_rbac.py)`
  - *API test env*: `DATABASE_URL=sqlite+pysqlite:////tmp/clara_api_ci.db AUTH_AUTO_PROVISION_USERS=true AUTH_BOOTSTRAP_ADMIN_ENABLED=true pytest -q <path>`
- Single ML test: `(cd services/ml && pytest tests/test_routing.py)`

### Web App (`apps/web`)
- Single unit test: `cd apps/web && npx vitest run <path/to/test.ts>`
- Unit test suite: `cd apps/web && npm run test`
- Type check: `cd apps/web && npm run type-check`
- Lint: `cd apps/web && npm run lint`
- E2E tests: `cd apps/web && npm run test:e2e`

### Contracts, i18n & Route Gates
- **Consumer Terminology**: Canonical source is `contracts/consumer-terminology/consumer-terminology.v1.json`. **Never edit generated files directly**.
  - Check: `cd apps/web && npm run consumer-terminology:check`
  - Regenerate: `cd apps/web && npm run consumer-terminology:generate` (updates `apps/web/lib/i18n/consumer-terminology.generated.ts` and `apps/mobile/lib/core/consumer_terminology.generated.dart`)
- **i18n Contract**: `cd apps/web && npm run i18n:check` (ensures migrated surfaces use `t(locale, key)` from `lib/i18n/catalog.ts`).
- **Route Matrix**: `cd apps/web && npm run route-matrix:check` (every new `app/**/page.tsx` must be added to `docs/ui-modernization/route-capability-matrix.md`).
- **Docs Check**: `make docs-check` (`scripts/docs/check-docs-links.sh`). In active `docs/*.md`, absolute machine paths (`/home/*`, `/Users/*`, `/private/*`) and root-relative leading `/` paths are forbidden.

### Evaluations (CLARA-Eval VN)
- Fixture smoke test: `make eval-smoke` (uses synthetic fixtures to verify cross-service contracts; never manufactured into clinical scores).
- Live evaluation: Requires `CLARA_EVAL_LIVE_EXECUTION_ENABLED=true` and approved external manifest (see `evaluation/clara_eval/LIVE_EXECUTION.md`). Never commit evaluation manifests or credentials.

## Routing & Presentation Rules

- **Unified Research**: `/research` and sub-routes are redirect stubs to `/chat`. Research jobs (tier2) run asynchronously within the chat interface.
- **Medicines Hub**: `/selfmed`, `/selfmed/ddi`, and `/careguard` redirect to `/medicines`. New links must point directly to `/medicines`.
- **Role Portals**: Consumers land on `/today`; clinicians/researchers/admins land on `/dashboard`.
- **UI Modernization Changes**: Refer to `docs/ui-modernization/07-exec-plan.md` and `08-task-list.md`. Keep route authorization separate from navigation presentation. Update the ExecPlan and decision log after checkpoints.
- **Language**: Respond and document in the user's language (Vietnamese when requested).

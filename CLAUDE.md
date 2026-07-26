# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLARA (Clinical Agent for Retrieval & Analysis) is a Vietnamese, safety-first Medical AI Assistant. It is an **implemented polyglot monorepo** with running source code across web, API, ML, and mobile runtimes — it is no longer documentation-only. The product positions itself as a clinical assistant and explicitly does not replace a doctor; safety guardrails (RBAC, consent gating, emergency fast-path, FIDES verification, no-PII telemetry) are treated as invariants, not optional features.

The four runtimes are:

- **`apps/web`** — Next.js 15 (React 18, TypeScript) production web app.
- **`services/api`** — FastAPI gateway (Python 3.11+): auth, RBAC, consent, rate limiting, CSRF, DB state, and proxying to ML.
- **`services/ml`** — FastAPI ML orchestration (Python 3.11+): routing, guardrails, RAG, and domain agents (CareGuard / Council / Scribe), plus FIDES verification.
- **`apps/mobile`** — Flutter starter client (Dart); core screens wired to the API, session currently being hardened toward persistence.

Two supporting sidecar microservices back the media pipelines:

- **`services/ocr`** — thin FastAPI adapter over **Google Cloud Vision** (`DOCUMENT_TEXT_DETECTION`) for medication-label OCR; the API reaches it through the OCR bridge (`TGC_OCR_*`). It holds no model and needs no GPU.
- **`services/asr`** — FastAPI + `faster-whisper` (local Whisper) exposing an OpenAI-compatible `POST /v1/audio/transcriptions`, used by Scribe transcription (`DEEPSEEK_AUDIO_BASE_URL` points at it because the YEScale `deepseek` group has no audio model).

## Repository Structure

```text
.
├── apps/
│   ├── web/      # Next.js frontend production app
│   └── mobile/   # Flutter client (login, dashboard, research, careguard, council)
├── services/
│   ├── api/   # FastAPI gateway + SQLAlchemy models + Alembic migrations
│   ├── ml/    # FastAPI ML layer: routing + RAG pipeline + agents + FIDES
│   ├── ocr/   # FastAPI adapter over Google Cloud Vision (medication-label OCR)
│   └── asr/   # FastAPI + faster-whisper (Scribe audio transcription)
├── deploy/
│   ├── docker/   # docker-compose.yml (infra), .app.yml (app), .deploy.yml (server)
│   └── nginx/    # reverse proxy conf
├── scripts/      # setup, deploy, ops, release, demo, docs helpers
├── docs/         # hackathon and design docs
└── data/docs/    # data/knowledge docs and index
```

## Architecture

### Runtime flow

The standard request path is **Web → API (`/api/v1/*`) → ML (internal)**:

1. `CLARA_Web` calls the API under the `/api/v1/*` prefix using cookie + bearer auth.
2. `CLARA_API` handles auth / RBAC / consent / rate-limit and DB state, then forwards to ML internal endpoints with `X-ML-Internal-Key` when configured.
3. `CLARA_ML` runs the router + guardrails + retrieval orchestration + synthesis/verification.
4. `CLARA_API` normalizes the ML payload (telemetry, flow events, verification matrix) back to `CLARA_Web`.

```
CLARA_Web (Next.js)
   │  /api/v1/*  (cookie + bearer, CSRF, RBAC)
   ▼
CLARA_API (FastAPI)  ── auth · RBAC · consent · chat proxy · research jobs ·
   │                      careguard · council · scribe · system(metrics/flow-events)
   │  internal (X-ML-Internal-Key)
   ▼
CLARA_ML (FastAPI)   ── router (role/intent/confidence) · RAG pipeline ·
                         research_tier2 (fast/deep/deep_beta) · careguard (DDI) ·
                         council · scribe · FIDES verification · emergency fast-path

CLARA_Mobile (Flutter)  ── core screens reuse the same /api/v1 surface via ApiClient
```

### Data plane (via Docker Compose)

The local infra stack (`deploy/docker/docker-compose.yml`) provides: **PostgreSQL** (relational state), **Redis** (cache / distributed limiters), **Milvus** (vector store, backed by **etcd** + **MinIO**), **Elasticsearch** (lexical / hybrid search), and **Neo4j** (graph). The app stack (`deploy/docker/docker-compose.app.yml`) adds **SearXNG** for external web retrieval alongside the `api`, `ml`, `web`, `ocr`, and `asr` containers.

### Common local ports (app compose)

- Web: `127.0.0.1:3100` · API: `127.0.0.1:8100` · ML: `127.0.0.1:8110` · SearXNG: `127.0.0.1:8888`
- Infra defaults: Postgres `5432`, Redis `6379`, Milvus `19530`, Elasticsearch `9200`, Neo4j `7474/7687`, MinIO `9000/9001`.

## Development Commands

Root `Makefile` targets (Python tooling spans both `services/api` and `services/ml`):

```bash
# Environment & infra
make setup-env          # create .env from .env.example if missing
make check-env          # validate local toolchain (.env, docker, docker compose)
make docker-up          # start local infra (postgres/redis/milvus/elasticsearch/neo4j/minio/etcd)
make docker-down
make docker-app-up      # build + start app stack (api/ml/web/searxng)
make docker-app-down

# Dev servers
make dev-api            # uvicorn clara_api.main:app (services/api, default port 8000)
make dev-ml             # uvicorn clara_ml.main:app  (services/ml, default port 8010)
make dev-web            # next dev (apps/web, port 3000)

# Quality gates (Python: ruff/mypy/pytest over services/api + services/ml + scripts)
make lint               # ruff check
make type-check         # mypy --ignore-missing-imports
make test               # pytest -q over services/*/tests
make docs-check         # validate docs links and docs path references
make precommit-install  # install git pre-commit hooks
```

Web (`apps/web`) uses npm scripts directly:

```bash
cd apps/web
npm run dev             # next dev -p 3000
npm run build           # next build
npm run lint            # next lint
npm run start           # next start -p 3000
npm run test            # vitest run (Vitest + fast-check property tests)
```

Docker Compose can also be driven directly:

```bash
docker compose --env-file .env -f deploy/docker/docker-compose.yml up -d        # infra
docker compose --env-file .env -f deploy/docker/docker-compose.app.yml up -d --build   # app
```

Database migrations run via Alembic from `services/api` (`alembic upgrade head`); versions live under `services/api/alembic/versions/`.

## Service Reference

### CLARA_API (`services/api/src/clara_api`)

- **Bootstrap & security** (`main.py`): CORS (no wildcard origins in production), auth-context middleware, rate limiter, API-metrics middleware, security headers (HSTS on HTTPS), and CSRF middleware that applies only to **cookie-authenticated mutating requests** (bearer-token requests and a small set of auth paths are exempt). A startup invariant enforces the ML timeout floor (`ML_SERVICE_TIMEOUT_SECONDS >= DEEPSEEK_TIMEOUT_SECONDS`, sync-research path `>= ML_RESEARCH_TIMEOUT_SECONDS`) so a misconfiguration fails fast. Production startup guards block default JWT secrets, require `AUTH_COOKIE_SECURE=true`, require `ML_INTERNAL_API_KEY`, forbid auto-provisioning, reject weak admin bootstrap passwords, and require `REDIS_URL` when distributed limiters are enabled. The router is also mounted a second time under `/api/v1` for backward compatibility with stale double-prefixed frontend calls.
- **Router** (`api/router.py`, prefix `/api/v1`): `health`, `auth` (register/verify/login + 2-step OTP for sensitive roles/consent), `mobile`, `chat` (routed proxy), `phr` (personal health record get/upsert), `search` (multi-source federated source-hub search across PubMed/RxNorm/openFDA/DailyMed/EuropePMC/Semantic Scholar/ClinicalTrials/DAVID), `research` (conversations, knowledge sources/documents, tier2 sync `/tier2` and async jobs `/tier2/jobs` with poll + SSE, source hub), `careguard` (medicine cabinet, scan, auto DDI, VN drug dictionary, `/analyze`), `council`, `scribe`, `system` (metrics, dependencies, control-tower config, flow events + SSE), `workspace` (folders/channels/share/export/notes), `social` (flag-gated community, see below), `admin/rag`, `admin/audit`, `admin/observability`, and `compliance` (DSAR / data-rights).
- **Research Tier2** (`api/v1/endpoints/research.py`): normalized request contract, document upload + OCR bridge (`TGC_OCR_*`), per-user knowledge sources, and an in-API async job engine (DB-backed `ResearchJob`, background worker pool via `RESEARCH_JOB_MAX_WORKERS`) exposing polling and SSE streams.
- **Data** (`db/models.py`): identity/session (`User`, `SessionModel`, `Query`, `AuthToken`, `UserConsent`), `PhrProfile`, `ResearchJob`, CareGuard (`MedicineCabinet`/`MedicineItem`, VN drug dictionary tables), scribe/council case tables, federated source records, `SystemSetting`, knowledge (`KnowledgeSource`/`KnowledgeDocument`), and workspace models. Migrations are in `services/api/alembic/versions/` (`20260324_0001` … `20260422_0018`).

### CLARA_ML (`services/ml/src/clara_ml`)

- **Endpoints** (`main.py`): `GET /health`, `/health/details`, `/metrics`, `/metrics/json`; `POST /v1/chat/routed`, `/v1/research/tier2`, `/v1/rag/poc`; agents `/v1/careguard/analyze`, `/v1/scribe/soap`, `/v1/scribe/transcribe` (audio upload), `/v1/council/run|consult|intake`; `GET /v1/prompts/{role}/{intent}`; `WS /ws/stream`. Protected prefixes require `X-ML-Internal-Key` when configured (503 in production if missing).
- **Guardrails**: a legal hard-guard (vi/en regex) blocks prescribing / diagnosis / personal-dosage intents, and an **emergency fast-path** returns escalation immediately on acute-symptom detection without diagnostic reasoning.
- **Router** (`routing.py`): heuristic role classification (`normal`/`researcher`/`doctor`) + intent + confidence, with a dedicated emergency keyword set.
- **RAG pipeline** (`rag/pipeline.py`): retrieve → synthesize (LLM) → deterministic local fallback; supports `auto`/`full` retrieval stacks, planner hints, hybrid internal + external retrieval, optional reranker and GraphRAG sidecar, and detailed trace/telemetry. The local fallback always carries safety wording and minimum references.
- **Research Tier2** (`agents/research_tier2.py`): `fast` / `deep` / `deep_beta` modes; deep modes add multi-pass retrieval, verification matrices, and (deep_beta) parallel reasoning nodes, quality gates, and long-form report synthesis.
- **Agents**: CareGuard DDI (`agents/careguard.py`) merges local rules with external sources, applies VN drug-dictionary normalization + active-ingredient expansion, and ranks severity; Council (`agents/council.py`) runs multi-specialist assessment with consensus/divergence; Scribe (`agents/scribe_soap.py`) produces SOAP output.

### CLARA_Web (`apps/web`)

- **Auth/session** (`middleware.ts`, `lib/http-client.ts`, `lib/auth-store.ts`): route guards, axios client with credentials + bearer + CSRF header for mutations, single-flight token refresh on 401, and memory + session/localStorage token recovery.
- **Navigation** (`lib/navigation.config.ts`): roles `normal`/`researcher`/`doctor`/`admin`, all homing to `/chat` post-login. Nav routes: `/chat`, `/dashboard`, `/phr`, `/selfmed` (all roles), `/careguard` (`normal`/`doctor`/`admin`), `/council` and `/scribe` (`doctor`/`admin`), `/admin/overview`, `/admin/knowledge-sources`, `/admin/answer-flow`, `/admin/observability` (admin-only), and `/huong-dan` (help). Research is unified into Chat — the legacy `/research` route (and its sub-routes) is a server redirect to `/chat`.
- **Surfaces**: Chat (routed ML chat + flow/policy context; `fast` runs the tier1 chat proxy while `deep`/`deep_beta` run tier2 research jobs with a realtime flow timeline and knowledge sources), SelfMed/CareGuard (cabinet + DDI + VN dictionary admin), Council (intake/consult/result), Scribe (SOAP), PHR (personal health record), and Workspace (folders/channels/share/export/notes).

### CLARA_Social (health community platform, `SOCIAL_PLATFORM_ENABLED`, default OFF)

An additive, flag-gated peer-support layer (spec `.kiro/specs/clara-health-social`). API router `/api/v1/social` (404 when the flag is off) covers consent (`social_participation_v1`), profiles (PHR-isolated), curated communities + join/leave, posts/comments/reactions, a recency feed, and reports + admin moderation queue. Every user-authored body is screened by ML `POST /v1/social/moderate` (reuses the legal hard-guard + emergency fast-path) BEFORE publish, failing closed. Web surface `apps/web/app/community`; mobile `SocialSurfaceV3` (flag `MOBILE_SOCIAL_ENABLED`). No PHR/medical-record data is reachable via any social route; moderation audit is PII-free.

### CLARA_Mobile (`apps/mobile`)

Flutter client with core screens (login, dashboard, research, careguard, council) wired to the API via `ApiClient`. Not yet at full parity with web.

## Models & Runtime (as-built)

The LLM runtime is **DeepSeek-only** by default (`LLM_DEEPSEEK_ONLY=true`), served through a YEScale-compatible endpoint (`DEEPSEEK_BASE_URL`, model `deepseek-v4-pro` by default per `.env.example`) with a configurable timeout and retry policy. Embeddings use `text-embedding-3-large` via an OpenAI-compatible base URL. Reranking is optional (embedding-cosine strategy by default), NLI verification defaults to a heuristic strategy, and GraphRAG / biomedical rerank are off by default. These are all configured through `.env` (see `.env.example`).

> Note: when `LLM_DEEPSEEK_ONLY` is enabled and a supplied runtime matches the configured DeepSeek env, the pipeline must reuse the default DeepSeek client (preserving its longer timeout) rather than constructing a short-timeout runtime client — and the API ML request timeout must stay `>=` the ML synthesis timeout for the same request class.

## Safety-First Guardrails (invariants)

These behaviors are regression-locked and must be preserved by every change:

- **RBAC** — `require_roles(...)` (`services/api/.../core/rbac.py`) gates protected routes; `admin` has implicit access, non-authorized roles get HTTP 403.
- **Consent gating** — versioned medical consent (`UserConsent` + `/auth/consent-status` / `/auth/consent`); the consent gate precedes medical content on End_User surfaces.
- **Emergency fast-path** — acute-symptom queries return an escalation response immediately and skip diagnostic reasoning.
- **FIDES verification & CRITICAL blocking** — failed `CRITICAL` drug-dosage / DDI claims block the response; verdicts and blocked-claim counts flow through flow events.
- **No-PII telemetry** — system metrics, flow events, and analytics aggregations exclude PII (names, emails, free-text queries, drug lists); outward views are projections of counts/distributions/percentiles only.
- **CSRF** — enforced for cookie-authenticated mutations.
- **End_User clarity** — internal telemetry labels and raw upstream errors are sanitized out of primary End_User views (detailed telemetry is admin-only).

## Deploy, CI/CD & Ops

- **Compose stacks**: `deploy/docker/docker-compose.yml` (infra), `docker-compose.app.yml` (api/ml/web/searxng), `docker-compose.deploy.yml` (server deploy).
- **CI/CD** (`.github/workflows/`): `ci.yml` (quality/test/build/security + docs smoke), `cd.yml` (preflight → staging → production), `release.yml` (semver tag, build/push images), `active-eval.yml`, `branch-protection-sync.yml`.
- **Scripts** (`scripts/`): deploy (`deploy/redeploy_app_stack.sh`), ops (`ops/validate_runtime_env.sh`, backup/cleanup/cron installers, source-hub auto-crawl), release (semver + image push), and demo/eval loops.

## Onboarding Path for New Contributors

1. `README.md`
2. API bootstrap + router: `services/api/src/clara_api/main.py`, `api/router.py`
3. ML bootstrap + routed chat + tier2: `services/ml/src/clara_ml/main.py`, `rag/pipeline.py`, `agents/research_tier2.py`
4. Web auth/research integration: `apps/web/lib/http-client.ts`, `lib/research.ts`, `app/chat/page.tsx` (research is unified into Chat; `app/research/page.tsx` is a redirect stub)
5. DB schema + migrations: `services/api/src/clara_api/db/models.py`, `alembic/versions/*`
6. Deploy/Ops: `.github/workflows/*`, `deploy/docker/*`, `scripts/deploy/redeploy_app_stack.sh`

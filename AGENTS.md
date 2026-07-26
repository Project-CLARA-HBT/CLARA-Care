# AGENTS.md

Guidance for AI coding agents working in the CLARA monorepo. This is a condensed
operational reference — see `CLAUDE.md` for the full architecture, service, and
onboarding detail.

## What CLARA is

CLARA (Clinical Agent for Retrieval & Analysis) is a Vietnamese, safety-first
Medical AI Assistant. It is a **clinical assistant, not a replacement for a
doctor**. Safety guardrails are invariants, not optional features — never weaken
or bypass them to make a change "work".

## Runtimes (polyglot monorepo)

| Path | Stack | Role |
| --- | --- | --- |
| `apps/web` | Next.js 15 / React 18 / TypeScript | Production web app |
| `apps/mobile` | Flutter / Dart | Client (subset of web features) |
| `services/api` | FastAPI (Python 3.11+) | Gateway: auth, RBAC, consent, rate limit, CSRF, DB, proxy to ML |
| `services/ml` | FastAPI (Python 3.11+) | Routing, guardrails, RAG, agents (CareGuard/Council/Scribe), FIDES |
| `services/ocr` | FastAPI over Google Cloud Vision | Medication-label OCR sidecar |
| `services/asr` | FastAPI + faster-whisper | Scribe audio transcription sidecar |

Request path: **Web → API (`/api/v1/*`) → ML (internal, `X-ML-Internal-Key`)**.

## Common commands

Root `Makefile` drives Python tooling across `services/api` + `services/ml` + `scripts`:

```bash
make lint          # ruff check
make type-check    # mypy --ignore-missing-imports
make test          # pytest -q over services/*/tests
make docs-check    # validate docs links/path references

make dev-api       # uvicorn clara_api.main:app (services/api, port 8000)
make dev-ml        # uvicorn clara_ml.main:app  (services/ml, port 8010)
make dev-web       # next dev (apps/web, port 3000)

make docker-up / docker-down            # local infra stack
make docker-app-up / docker-app-down    # app stack (api/ml/web/searxng)
```

Web app (`apps/web`) uses npm directly:

```bash
cd apps/web
npm run dev / build / lint / start
npm run test        # vitest run (Vitest + fast-check property tests)
npm run test:e2e    # playwright
```

Python services use `uv` (see `uv.lock`, `pyproject.toml` per service).
DB migrations run via Alembic from `services/api` (`alembic upgrade head`);
versions live in `services/api/alembic/versions/`.

## Validation expectations

After Python changes: run `make lint`, `make type-check`, and `make test`
(or the narrower `pytest` path under the service you touched).
After web changes: run `npm run lint` and `npm run test` in `apps/web`.
Start with the tests closest to your change, then widen. Do not claim
validation passed unless you actually ran it.

## Safety-first invariants (regression-locked — must preserve)

- **RBAC** — `require_roles(...)` (`services/api/.../core/rbac.py`) gates routes; `admin` has implicit access, others get 403.
- **Consent gating** — versioned medical consent precedes medical content on End_User surfaces.
- **Emergency fast-path** — acute-symptom queries return an escalation response immediately, skipping diagnostic reasoning.
- **FIDES verification** — failed `CRITICAL` drug-dosage/DDI claims block the response.
- **No-PII telemetry** — metrics, flow events, and analytics exclude PII (names, emails, free-text queries, drug lists); expose only counts/distributions/percentiles.
- **CSRF** — enforced for cookie-authenticated mutations (bearer requests exempt).
- **Legal hard-guard** — ML blocks prescribing / diagnosis / personal-dosage intents (vi/en).
- **End_User clarity** — internal telemetry labels and raw upstream errors are sanitized out of primary End_User views (detailed telemetry is admin-only).

## Conventions

- Reply and write docs in the user's language (Vietnamese when they use it).
- Match existing style and reuse existing dependencies/patterns; keep changes minimal and focused.
- LLM runtime is DeepSeek-only by default (`LLM_DEEPSEEK_ONLY=true`); when a runtime matches the configured DeepSeek env, reuse the default DeepSeek client (preserve its longer timeout). API ML timeout must stay `>=` ML synthesis timeout for the same request class.
- `CLARA_Social` (`SOCIAL_PLATFORM_ENABLED`, default OFF) is additive and flag-gated; every user body is screened by ML `POST /v1/social/moderate` before publish, failing closed. No PHR/medical data is reachable via social routes.
- Research is unified into Chat — `apps/web/app/research/page.tsx` is a redirect stub to `/chat`.

## Key entry points

- API bootstrap + router: `services/api/src/clara_api/main.py`, `api/router.py`
- ML bootstrap + RAG + tier2: `services/ml/src/clara_ml/main.py`, `rag/pipeline.py`, `agents/research_tier2.py`
- Web auth/http: `apps/web/lib/http-client.ts`, `lib/auth-store.ts`, `app/chat/page.tsx`
- DB schema: `services/api/src/clara_api/db/models.py` + `alembic/versions/*`

# Risk Register: PH01_A04 Dependency Parity & Auxiliary Services

## Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant | Status |
|---|---|---|---|---|---|---|
| **RR-PH01-01** | Node Engine Mismatch | CI or deployment environment running Node != 20, causing Next.js 15 SSR hydration mismatches or npm lockfile discrepancies. | High | Low | Root `.nvmrc` strictly pinned to `20`; `apps/web/package.json` specifies `"node": ">=20 <21"`. Build pipelines enforce Node 20 via `.nvmrc` lookup. | Controlled |
| **RR-PH01-02** | npm Lockfile Inconsistency | Drift between `package.json` dependencies and `package-lock.json`, causing non-reproducible builds in CI. | High | Low | Lockfile version 3 is locked and verified with `npm ci --dry-run`. Overrides (`postcss`, `sharp`) ensure consistent resolutions across environments. | Controlled |
| **RR-PH01-03** | Heavy In-Process ML Bloat | Accidental introduction of `sentence-transformers` or PyTorch directly into `services/ml`, inflating container memory and causing cold-start timeouts. | Critical | Low | Invariant enforced: `sentence-transformers` is strictly excluded from `services/ml`. Embeddings are resolved via `HttpEmbeddingClient` to external endpoints, and reranking uses `EvidenceReranker` cosine scoring or LLM task contracts. | Controlled |
| **RR-PH01-04** | pgvector Absence on PostgreSQL | Deploying to a PostgreSQL cluster lacking `vector` or `pg_trgm` extensions, causing ML service crashes during startup. | High | Low | Defensive initialization in `clara_ml.rag.store.health.run_startup_self_check`: if pgvector is absent, the service logs a warning and falls back to `InMemoryRetriever`, preventing boot failure. | Controlled |
| **RR-PH01-05** | ASR Sidecar Native Library Dependency | `faster-whisper` failing in Docker due to missing system `ffmpeg` packages. | Medium | Low | `services/asr/Dockerfile` relies on PyAV bundled inside the `av` wheel, which includes bundled FFmpeg codecs for WebM/Opus audio streams without host packages. | Controlled |
| **RR-PH01-06** | ASR Provider Cyclic Fallback | Primary ASR failing and repeatedly attempting the same failed provider as fallback, causing consultation timeouts. | High | Low | `services/ml/src/clara_ml/services/scribe_asr.py` deduplicates `SCRIBE_ASR_PRIMARY` and `SCRIBE_ASR_FALLBACK`. If both point to the same provider, fallback loops are suppressed. | Controlled |
| **RR-PH01-07** | OCR Multi-Model Gateway Outage | `gemini-3.7-flash-tiered` gateway endpoint experiencing 5xx errors or network timeout during prescription analysis. | High | Medium | Dual-model fallback in `services/ocr/server.py` (`OCR_MODEL` fails over to `OCR_FALLBACK_MODEL=gemini-3.6-flash-high`) combined with secondary fallback to Google Cloud Vision Document Text Detection. | Controlled |
| **RR-PH01-08** | Secret Exposure in Router Configuration | Upstream API keys or internal tokens hardcoded in configuration files or test fixtures. | Critical | Low | All router keys use environment variables (`ROUTER_API_KEY`, `OCR_API_KEY`, `DEEPSEEK_API_KEY`) with empty string defaults. Pre-commit hooks reject hardcoded secrets. | Controlled |

---

## Architectural Invariants & Safety Guarantees

1. **Monorepo Node 20 Standard:** The entire web frontend is aligned with Node 20 LTS. Package installations must strictly use `npm ci` with `package-lock.json` v3.
2. **Zero-PyTorch Core ML Invariant:** `services/ml` remains a lightweight, rapid-boot FastAPI gateway without in-process PyTorch or heavy transformer weights. Embeddings and reranking are strictly decoupled over HTTP boundaries.
3. **Decoupled Auxiliary Sidecars:** Heavy audio processing (`faster-whisper`) and multimodal vision bridges are isolated into `services/asr` and `services/ocr` sidecars, preserving service boundaries and fault isolation.
4. **Additive Database Migrations:** All vector extension and table operations in `clara_ml.rag.store.migrations` strictly execute `CREATE ... IF NOT EXISTS` semantics.
5. **No PHI in Telemetry:** All telemetry events, audio transcription metadata, and OCR extraction digests omit patient identifying information, adhering to CLARA's clinical safety architecture.

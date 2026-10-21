# Risk Register: PH00_A04 ML + Retrieval Subsystem

## Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant | Status |
|---|---|---|---|---|---|---|
| **RR-A04-01** | Model Registry Drift | An unregistered model task or undocumented prompt version bypassing governance checks. | Critical | Low | Enforced in `load_task_contracts()`: manifest is strictly validated against `ModelTask` enum; undefined tasks fail closed immediately with `unregistered_model_task`. | Controlled |
| **RR-A04-02** | Provider Capability Mismatch | Routing a structured-JSON or multimodal task to an adapter lacking the required capability. | High | Low | `ModelGateway.enforce_capabilities()` cross-checks adapter-declared capabilities against `TaskContract.required_capabilities` before invoking the model, raising `CapabilityMismatchError` on deficit. | Controlled |
| **RR-A04-03** | Silent Fallback to Weaker LLM | Network or provider timeout silently downgrading a clinical reasoning task to an unverified smaller model. | Critical | Low | Hard rule in `resolve_model_selection`: `fallback_model` is empty for medical safety tasks; failures raise typed exceptions or invoke deterministic legal/emergency safety fallbacks rather than executing a lower-tier LLM. | Controlled |
| **RR-A04-04** | RAG pgvector Extension Absence | Deployment environments lacking PostgreSQL `vector` or `pg_trgm` extensions crashing the ML service at startup. | High | Low | Handled defensively by `_rag_persistent_store_self_check` and `clara_ml.rag.store.health.run_startup_self_check`: if extensions or `kb_*` tables are missing, the system gracefully falls back to `InMemoryRetriever` without crashing startup. | Controlled |
| **RR-A04-05** | FIDES Drug-Safety Gate Loosening | Stale or low-authority retrieved documents causing FIDES claim verification to pass unsafe dosages or DDIs. | Critical | Low | Implemented in `RagPipelineP1.tighten_fides_verdict_with_trust`: ranking metadata operates under a strict "tighten-only" invariant where low authority (tier >= 3) or stale evidence (> 5 years) can only escalate `warn` to `fail`, never downgrade a `fail` to `pass`. | Controlled |
| **RR-A04-06** | Synthesis v2 Word Bloat / Hallucination | Synthesis v2 generating excessive verbiage or hallucinating citations on narrow queries. | High | Low | Enforced by property P1 (`min_words <= target <= max_words <= 15000`) and property P5 (no appendix padding on narrow/sparse topics). Feature is gated behind `SYNTHESIS_V2_ENABLED=false` until clinical validation. | Controlled |
| **RR-A04-07** | PII / PHI Leakage in ML Telemetry | User medical queries, drug lists, or raw transcripts leaking into Prometheus metrics or operational logs. | High | Low | Enforced by `compute_context_digest` which emits only `sha256:...` hashes in `ModelRunProvenance`. Query texts are passed through `redact_pii` before indexing or storage. | Controlled |
| **RR-A04-08** | OCR Service Gateway Availability | External Vision LLM router outages blocking image-based prescription and lab document ingestion. | High | Medium | Dual-model fallback (`OCR_MODEL=gemini-3.7-flash-tiered` with `OCR_FALLBACK_MODEL=gemini-3.6-flash-high`) combined with fallback to Google Cloud Vision document text detection. | Controlled |
| **RR-A04-09** | ASR Streaming Latency & Transcription Drift | Audio buffer bottlenecks or ASR hallucinations during live doctor-patient consultations. | High | Medium | `services/asr` runs local `faster-whisper` with VAD filtering (`vad_filter=True`) and `int8` CPU quantization. Deployment allows failover to secondary provider (`SCRIBE_ASR_FALLBACK`), while preventing same-provider failover loops. | Controlled |
| **RR-A04-10** | Evaluation Metrics Fabrication | Synthetic test fixtures accidentally or deliberately cited as real-world clinical validation scores. | Critical | Low | Invariant locked in `evaluation/clara_eval/LIVE_EXECUTION.md`: smoke fixtures in `datasets/fixtures/*.smoke.jsonl` are strictly labeled synthetic and used only for PR contract verification. Production clinical claims require audited live execution manifests. | Controlled |

---

## Architectural Invariants & Safety Guarantees

1. **Safety-First Routing:** All medical queries undergo deterministic regex triage (`_LEGAL_GUARD_PATTERNS` in `clara_ml.main`) before LLM reasoning. Inquiries seeking prescriptions, diagnosis, or personal dosage adjustments are intercepted and returned with fail-closed medical disclaimers.
2. **Deterministic Emergency Fast-Path:** Acute symptom patterns immediately yield emergency escalation advice, bypassing multi-step retrieval or synthesis.
3. **Decoupled API/ML Service Boundary:** No direct cross-service database coupling. The API layer proxies requests using authenticated HTTP with `X-ML-Internal-Key`.
4. **Additive RAG Migrations:** DDL statements in `clara_ml.rag.store.migrations` strictly use `IF NOT EXISTS` constructs, guaranteeing zero destruction of existing tables.
5. **No PHI in Tracing & Observability:** Model selection records, circuit breaker logs, and telemetry counters only store closed enum values and hashed identifiers.

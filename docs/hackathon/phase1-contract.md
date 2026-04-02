# Phase 1 Contract (Day 1-3)

Date: 2026-04-02
Owner scope: Day 1-3 (contract + config + reranker + pipeline hook + timeout fallback)

## 1) Goal of Day 1-3
Lock a stable contract for the new retrieval reranker before pipeline integration.

Day 1 deliverables:
- Runtime flags in ML settings for reranker control.
- Written contract for I/O and telemetry keys.

Day 2 deliverables:
- `rag/retrieval/reranker.py` skeleton module with deterministic placeholder behavior.
- Unit-test coverage for pass-through and rerank metadata shape.

Day 3 deliverables:
- Hook reranker into `services/ml/src/clara_ml/rag/retrieval/in_memory.py`.
- Guarantee timeout fallback does not break retrieval/generation.
- Surface telemetry in `index_phase.rerank` and `index_summary.rerank`.

## 2) Config Flags (ML)
Defined in `services/ml/src/clara_ml/config.py`:

- `RAG_RERANKER_ENABLED` (`bool`, default: `false`)
- `RAG_RERANKER_MODEL` (`str`, default: `phase1-skeleton-reranker-v0`)
- `RAG_RERANKER_TOP_N` (`int`, default: `12`)
- `RAG_RERANKER_TIMEOUT_MS` (`int`, default: `250`)

Notes:
- These flags are additive and do not remove existing biomedical score-engine rerank flags.
- Pipeline hook is introduced only at retrieval index boundary (`InMemoryRetriever`), not in API contract.

## 3) Reranker Module Contract
Module path:
- `services/ml/src/clara_ml/rag/retrieval/reranker.py`

Public API:
- `NeuralReranker.rerank(query: str, documents: Sequence[Document], top_k: int | None = None)`
- Returns `RerankResult` with:
  - `documents: list[Document]`
  - `metadata: dict[str, Any]`

Input assumptions:
- `documents` are retrieval candidates already normalized into `Document` with mutable metadata.
- `top_k=None` means no final truncation.

Behavior in Day 2-3:
- If disabled or no candidates: pass-through documents (optional top-k truncation).
- If enabled: rerank only top-N candidates using placeholder score (not model inference).
- If timeout/error: deterministic fallback to original ranked list, keep serving answer.
- Writes doc-level fields for reranked candidates:
  - `rerank_score`
  - `rerank_rank`
  - `rerank_applied`

## 4) Telemetry / Metadata Contract
The reranker return metadata MUST include:

- `rerank_latency_ms` (float)
- `rerank_topn` (int)

Current metadata payload also includes:
- `rerank_enabled`
- `rerank_model`
- `rerank_timeout_ms`
- `rerank_input_count`
- `rerank_output_count`
- `rerank_applied_count`
- `rerank_timed_out`
- `rerank_reason` (`ok | disabled_or_empty | timeout_fallback | error_fallback`)
- `rerank_error` (nullable, for failure mode only)

## 5) Out of Scope for Phase 1
- Replacing or removing current `score_engine` biomedical rerank logic.
- UI wiring or API payload changes.
- Deployment script changes.

## 6) Test Contract (Phase 1)
Added tests validate:
- Pass-through behavior when disabled.
- Presence and type of `rerank_latency_ms` and `rerank_topn`.
- Top-N bounded reranking and doc metadata (`rerank_rank`, `rerank_score`, `rerank_applied`).
- Safe behavior when `top_k <= 0`.
- Timeout fallback (`timeout_fallback`) returns deterministic ranked list and telemetry.

## 7) 2026 Research Notes (Applied)
Phase 1 follows low-risk adoption: keep current scorer, add optional reranker sidecar, preserve fallback.

Reference directions to guide later Phase 2:
- BAR-RAG (generator-aware reranking): https://arxiv.org/abs/2602.03689
- LCR (training-free reranking): https://arxiv.org/abs/2602.13571
- MedRAGChecker (claim-level medical verification): https://arxiv.org/abs/2601.06519

## 8) Day 5 Safety Override
- `research_tier2` áp dụng `safety_critical_override` khi claim-type `dosage|contraindication`
  ở trạng thái `insufficient|contradicted`.
- Override policy:
  - `contradicted` -> `policy_action=block`
  - `insufficient` -> `policy_action=warn`
- Payload `verification_matrix` chứa thêm trường `safety_override` để UI/admin trace được lý do.

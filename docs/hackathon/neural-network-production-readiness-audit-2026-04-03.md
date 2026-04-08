# Neural Network 28-Day Plan: Production Readiness Audit (2026-04-03)

## 1) Kết luận nhanh
- Trạng thái tổng: **Production phase completed** cho phạm vi 28-day NN plan.
- Các mục Day 1-28 đã đồng bộ lại checklist với thực thi thật.
- Các phần trước đây ở mức v1/skeleton đã được nâng cấp thành production-path có timeout/fallback an toàn.

## 2) Ma trận V1 vs Production
| Hạng mục | Done V1 | Nâng cấp Production | Trạng thái |
|---|---|---|---|
| Neural Reranker | Embedding + heuristic score + timeout fallback | Thêm `llm_hybrid` score fusion, metadata degrade rõ ràng | Done |
| NLI Verification | Heuristic overlap/negation | Thêm `llm_hybrid` claim verification, confidence clamp, fallback heuristic | Done |
| Verification Matrix | rows + summary + contradiction | Giữ contract, tăng độ tin cậy verdict từ LLM-path khi bật | Done |
| Runtime safety | fallback local | giữ hard-guard, timeout cứng, degrade có lý do | Done |
| Test coverage | unit/integration cơ bản | thêm tests cho LLM-path + fallback-path | Done |

## 3) File thay đổi chính
1. `services/ml/src/clara_ml/config.py`
2. `services/ml/src/clara_ml/factcheck/nli_verifier.py`
3. `services/ml/src/clara_ml/factcheck/fides_lite.py`
4. `services/ml/src/clara_ml/rag/retrieval/reranker.py`
5. `services/ml/tests/test_nli_verifier.py`
6. `services/ml/tests/test_retrieval_reranker.py`
7. `docs/hackathon/neural-network-3phase-28day-execution-plan.md`

## 4) Bằng chứng kiểm thử
- Command:
  - `services/ml/.venv/bin/python -m pytest services/ml/tests/test_nli_verifier.py services/ml/tests/test_retrieval_reranker.py services/ml/tests/test_factcheck_module.py -q`
- Kết quả:
  - `18 passed`

## 5) Cờ runtime production khuyến nghị
```env
RAG_RERANKER_ENABLED=true
RAG_RERANKER_STRATEGY=llm_hybrid
RAG_RERANKER_LLM_ENABLED=true
RAG_RERANKER_LLM_TOP_N=6
RAG_RERANKER_LLM_TIMEOUT_MS=900

RAG_NLI_ENABLED=true
RAG_NLI_STRATEGY=llm_hybrid
RAG_NLI_LLM_ENABLED=true
RAG_NLI_LLM_TIMEOUT_MS=900
RAG_NLI_MIN_CONFIDENCE=0.35
```

## 6) Guardrails bắt buộc giữ nguyên
1. Không cho chatbot vượt ranh giới pháp lý (kê đơn/liều/chẩn đoán).
2. Khi upstream lỗi/timeout, bắt buộc degrade an toàn thay vì trả lỗi trống.
3. Luôn log được metadata để truy vết: `fallback_reason`, `source_errors`, `rerank_llm_used`, `rerank_llm_error`.

# Deep Research Audit + Upgrade Plan (2026-04-01)

## 1) Mục tiêu
- Đánh giá quy trình Deep Research hiện tại của CLARA theo góc độ runtime thực chiến.
- Chỉ ra rõ điểm mạnh, điểm chưa tốt, các rủi ro vận hành.
- Đề xuất lộ trình nâng cấp lên Agentic RAG thế hệ mới, có thể triển khai theo phase.
- Cập nhật lại canvas flow để phản ánh pipeline nâng cấp.

## 2) Phạm vi audit
- ML pipeline:
  - `services/ml/src/clara_ml/agents/research_tier2.py`
  - `services/ml/src/clara_ml/rag/pipeline.py`
  - `services/ml/src/clara_ml/rag/retrieval/external_gateway.py`
  - `services/ml/src/clara_ml/rag/retrieval/score_engine.py`
- API orchestration:
  - `services/api/src/clara_api/api/v1/endpoints/research.py`
- Web research runtime:
  - `apps/web/app/research/page.tsx`
  - `apps/web/components/research/markdown-answer.tsx`
- Canvas flow:
  - `apps/web/components/admin/admin-flow-visualizer.tsx`

## 3) Điểm tốt hiện tại
- Có legal hard guard ở tầng ML:
  - Chặn kê đơn/chẩn đoán/liều trước khi vào generation.
  - Giảm rủi ro pháp lý thực tế khi chatbot bị prompt tấn công.
- Có planner hints theo mode:
  - `fast` ưu tiên SLA.
  - `deep` mở rộng multi-pass, contradiction scan, cross-source.
- Retrieval đã có hybrid scoring cơ bản:
  - Semantic + lexical blend.
  - Source bias, trust tier, tag relevance, diversity.
  - DDI-aware filter giảm tài liệu lệch chủ đề thuốc.
- Có flow events + telemetry:
  - UI theo dõi timeline theo stage.
  - Có tín hiệu cho fallback/degraded path.
- Có fallback an toàn:
  - Không gãy phiên khi upstream LLM không sẵn sàng.

## 4) Điểm chưa tốt và rủi ro
- Query planning chưa đủ source-aware:
  - Chưa tách rõ chiến lược keyword theo từng nguồn (ví dụ nguồn VN cần query tiếng Việt, PubMed cần tiếng Anh y khoa).
- Retrieval orchestration còn thiên rule-based:
  - Chưa có learned orchestrator cho phân bổ ngân sách truy xuất theo độ khó truy vấn.
- Rerank chưa có cross-encoder chuyên y sinh:
  - Dẫn đến tình huống "retrieved có nhưng chọn chưa đúng top evidence".
- Contradiction mining mới ở mức cơ bản:
  - Chưa có agreement/disagreement matrix rõ theo claim.
- Verification hiện tại (FIDES-lite) còn coarse:
  - Chưa chuẩn hóa claim-level support score end-to-end.
- Vòng phản hồi chất lượng còn mỏng:
  - Chưa có hard-negative mining tự động để cải thiện retrieval qua từng vòng.
- Quan sát vận hành chưa đủ sâu:
  - Thiếu trace chuẩn OTel theo span cho từng node trong deep loop.

## 5) Nâng cấp thuật toán và công nghệ (technology radar)

| Công nghệ / hướng | Lợi ích chính | Độ phức tạp | Điểm tích hợp CLARA | KPI kỳ vọng |
|---|---|---|---|---|
| Query Canonicalization + Source-aware query rewrite | Tăng recall đúng nguồn, giảm retrieval lệch miền | Trung bình | `research_tier2.py`, `external_gateway.py` | Recall@K tăng, giảm source-errors |
| Agentic Query Decomposition | Chia truy vấn thành sub-queries có kiểm soát | Trung bình | `research_tier2.py` planner/deep loop | Tăng evidence coverage |
| Learned retrieval orchestration | Phân bổ top_k, timeout budget theo query profile | Cao | `rag/pipeline.py` + `external_gateway.py` | Giảm latency p95, tăng precision@K |
| Hybrid retrieval + RRF | Kết hợp dense/sparse ổn định hơn | Thấp-Trung bình | `score_engine.py` | Precision@K, nDCG tăng |
| Cross-encoder reranker (biomedical) | Chọn top evidence đúng ngữ cảnh hơn | Trung bình-Cao | sau `evidence_index` | Precision@K tăng rõ |
| Contradiction mining node | Phát hiện bằng chứng trái chiều, tránh trả lời quá tự tin | Trung bình | giữa `evidence_index` và `verification_matrix` | Giảm unsupported claims |
| Claim-level verification | Chấm support theo từng claim thay vì verdict tổng | Cao | `factcheck` + payload schema | Tăng citation-grounding rate |
| GraphRAG cho tri thức liên kết thuốc-bệnh-cảnh báo | Truy xuất theo quan hệ, giảm missing context | Cao | pha P2 (sidecar index) | Recall cho query phức tạp tăng |
| Observability chuẩn OpenTelemetry | Debug chuẩn theo span/trace đa node | Trung bình | API + ML middleware | Rút ngắn MTTR, tăng reliability |
| RAG eval stack (RAGAS + BEIR-like harness) | Đo chất lượng khoa học, có regression gate | Trung bình | scripts/demo + CI quality gate | Chốt KPI ổn định trước deploy |

## 6) Kế hoạch triển khai (P0/P1/P2)

### P0 (ngắn hạn, ưu tiên vòng thi)
- Chuẩn hóa query rewrite theo từng nguồn:
  - VN sources: keyword tiếng Việt.
  - PubMed/EuropePMC: keyword tiếng Anh + synonym y khoa.
- Bổ sung node `query_canonicalizer` và `query_decomposition` trong runtime flow.
- Cứng hóa metadata:
  - `source_attempts`, `source_errors`, `fallback_reason`, `query_plan`.
- Nâng score engine:
  - Bổ sung RRF layer và hard filter cho query DDI critical.
- KPI gate:
  - precision@k, recall@k, nDCG@k, fallback rate, refusal compliance.

### P1 (trung hạn)
- Retrieval orchestrator thông minh theo query profile.
- Contradiction miner thành node chính thức trước synthesis cuối.
- Claim-level verification matrix:
  - Mỗi claim có support/unsupported/confidence riêng.
- Telemetry theo OpenTelemetry:
  - Trace xuyên suốt planner -> retrieval -> verifier -> responder.

### P2 (nâng cao)
- GraphRAG sidecar cho miền tri thức y sinh (drug-class, contraindication graph).
- Hard-negative mining tự động từ production logs.
- Active evaluation loop:
  - Regression suite định kỳ, auto compare với baseline run trước.

## 7) KPI và protocol đánh giá
- Retrieval:
  - Precision@K
  - Recall@K
  - nDCG@K
- Generation/grounding:
  - Citation coverage rate
  - Supported-claims ratio
  - Unsupported-claims ratio
- Runtime:
  - p50/p95 latency (fast/deep)
  - Fallback rate
  - Upstream failure recovery rate
- Safety:
  - Refusal compliance rate cho prompt bẫy pháp lý

Protocol:
- Chạy benchmark theo bộ positive/negative set có kiểm chứng.
- Log full trace + flow events + source attribution.
- So sánh với baseline trước mỗi lần thay đổi lớn.

## 8) Mapping vào canvas flow mới
Canvas flow đã được làm lại để khớp lộ trình nâng cấp:
- Node mới:
  - `query_canonicalizer`
  - `query_decomposition`
  - `retrieval_orchestrator`
  - `contradiction_miner`
  - `evaluation_feedback`
- Luồng mới:
  - Safety/legal ingress -> canonicalization -> planner/decomposition -> orchestration đa nguồn -> evidence index -> contradiction + verification -> policy gate -> responder -> feedback loop.

File canvas:
- `apps/web/components/admin/admin-flow-visualizer.tsx`

## 9) Tài liệu tham khảo (primary/official)
- Self-RAG: https://arxiv.org/abs/2310.11511
- CRAG: https://arxiv.org/abs/2401.15884
- RAPTOR: https://arxiv.org/abs/2401.18059
- GraphRAG (Microsoft): https://microsoft.github.io/graphrag/
- ColBERTv2: https://arxiv.org/abs/2112.01488
- BGE-M3: https://arxiv.org/abs/2402.03216
- RAGAS: https://arxiv.org/abs/2309.15217
- BEIR: https://arxiv.org/abs/2104.08663
- OpenTelemetry docs: https://opentelemetry.io/docs/

## 10) Audit trạng thái triển khai thực tế (2026-04-02)

| Hạng mục | Trạng thái codebase | Mức độ |
|---|---|---|
| Query canonicalization + source-aware rewrite | Có trong `research_tier2.py`, đã sinh `source_queries` + `provider_queries` | **Done (P0)** |
| Query decomposition (fast/deep/deep_beta) | Có `decomposition` + deep/deep_beta loop | **Done (P0)** |
| Retrieval orchestrator | Có orchestration plan + budget + stack coverage | **Done (P1 core)** |
| Hybrid scoring + RRF | Có trong `score_engine.py` | **Done (P0)** |
| Contradiction miner + verification matrix | Có FIDES-lite + claim-level matrix summary | **Done (P1 core)** |
| Metadata chuẩn hóa (`source_attempts`, `source_errors`, `query_plan`, `fallback_reason`) | Có ở ML + API normalize path | **Done (P0)** |
| OTel trace metadata | Trước đây mới ở mức stage spans; đã bổ sung `otel_trace_metadata` payload | **Done (P1 incremental)** |
| Learned orchestrator (model-based policy) | Chưa có, hiện vẫn rule-based orchestration | **Partial / chưa full** |
| Cross-encoder biomedical reranker | Đã có lớp `biomedical_rerank` theo feature-flag trong `score_engine` + trace ở `index_summary.rerank` (bản lite, chưa inference model cross-encoder thật) | **Done (P1 incremental)** |
| GraphRAG sidecar | Có sidecar runtime, chưa có graph index lớn production | **Partial / đang mở rộng** |

## 11) Hạng mục còn ở mức cơ bản/skeleton cần hoàn thiện tiếp

1. Learned retrieval orchestration:
   - Hiện tại chủ yếu heuristic/rule.
   - Cần training/inference policy cho allocation top_k/budget theo query class.
2. Cross-encoder reranker:
   - Cần thêm lớp rerank chuyên y sinh để tăng precision@k ở top evidence.
3. Active eval + hard-negative mining:
   - Đã đóng vòng ingest vào KPI runner ở mức runtime.
   - Còn thiếu cron + CI regression gate tự động.
4. OTel exporter thật:
   - Đã có exporter HTTP best-effort (tắt mặc định), nhưng chưa phải OTLP chuẩn + collector production.
5. Cross-encoder model thật (ColBERT/Cross-Encoder biomedical):
   - Bản hiện tại là rerank lite để tăng precision@k an toàn cho vòng thi.
   - Cần thay bằng model inference service ở phase sau.

## 12) Cập nhật mới đã triển khai ngay sau audit

- Bổ sung `provider_queries` vào query plan để rewrite theo từng provider thay vì chỉ theo nhóm nguồn.
- Truyền `provider_query_overrides` xuyên suốt `research_tier2 -> rag pipeline -> in_memory retriever -> external gateway`.
- Bổ sung `otel_trace_metadata` vào `metadata`, `telemetry` và `trace` của kết quả research.
- Bổ sung `otel_export` best-effort:
  - Env: `OTEL_EXPORT_ENABLED`, `OTEL_EXPORT_ENDPOINT`, `OTEL_EXPORT_TIMEOUT_SECONDS`.
  - Trả trạng thái export trong payload (`otel_export`) để debug nhanh khi collector lỗi.
- Bổ sung `retrieval_budget` override vào orchestrator runtime:
  - Cho phép planner/agent truyền budget (`latency_budget_ms`, `max_connector_calls`, `top_k_cap`...) và được áp vào plan thực thi.
  - Có test regression để đảm bảo `top_k` thực tế tuân theo budget cap.
- Bổ sung `biomedical_rerank` (feature-flag) vào retrieval score engine:
  - Env: `RAG_BIOMEDICAL_RERANK_ENABLED`, `RAG_BIOMEDICAL_RERANK_ALPHA`, `RAG_BIOMEDICAL_RERANK_TOP_N`.
  - Trace: `retrieval_trace.index_summary.rerank`.
- Bổ sung ingest `hard-negative` vào KPI pipeline:
  - Nhận `--active-negative-set` / `CLARA_ACTIVE_NEGATIVE_SET`.
  - Thêm `hard_negative_cases` vào test report.
  - Thêm metric `hard_negative_pass_rate` vào KPI report.
- Bổ sung test coverage:
  - `services/ml/tests/test_external_gateway.py` (provider override telemetry)
  - `services/ml/tests/test_research_tier2_agent.py` (query plan có provider queries)
  - `services/ml/tests/test_main_api.py` (schema có `otel_trace_metadata`)
  - `services/ml/tests/test_score_engine.py` (biomedical rerank on/off + top_n limit)

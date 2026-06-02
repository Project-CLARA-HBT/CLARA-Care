# CLARA Research - Latest Science Map (2026-04-04)

## Mục tiêu file
File này chuyển danh sách nghiên cứu mới (2025-2026) thành **kế hoạch kỹ thuật có thể triển khai ngay** trên codebase CLARA.

## Cách đọc nhanh
- `Evidence`: paper/link nguồn.
- `Áp dụng vào CLARA`: thay đổi cụ thể.
- `Code touchpoints`: file/module cần sửa.
- `KPI / Eval`: cách đo khách quan.

---

## 1) Science-to-Implementation Matrix

| # | Evidence | Áp dụng vào CLARA | Code touchpoints | KPI / Eval |
|---|---|---|---|---|
| 1 | JAMA RCT 2026 - EHR intervention for deprescribing (PMID: 41609788) | Thêm nhánh `deprescribing-signal` trong research output cho polypharmacy cao tuổi | `services/ml/src/clara_ml/agents/research_tier2.py`, `services/api/src/clara_api/schemas.py`, `apps/web/components/research/markdown-answer.tsx` | % ca có đề xuất deprescribing hợp lệ; false-positive rate |
| 2 | JAMA Netw Open 2025 - eDecision support deprescribing (PMID: 40445620) | Rule engine “inappropriate meds in elderly” + cảnh báo mức độ | `services/ml/src/clara_ml/factcheck/fides_lite.py`, `services/ml/src/clara_ml/factcheck/nli_verifier.py` | Recall của cảnh báo trên test set lão khoa |
| 3 | Medication safety CDSS with LLM (PMID: 40997804) | Chuẩn hóa format “Medication Safety Summary” theo claim-level | `services/ml/src/clara_ml/agents/research_tier2.py`, `apps/web/lib/research.ts` | Claim support coverage, unsupported-claim ratio |
| 4 | Mapping review LLM for DDI (PMID: 40999995) | Củng cố legal guard: từ chối kê liều/chẩn đoán 100% | `services/ml/src/clara_ml/main.py`, `services/ml/src/clara_ml/agents/careguard.py` | Refusal compliance rate (bộ prompt bẫy) |
| 5 | DDI-caused ADR detection with LLM (PMID: 40385316) | Bổ sung scorer “ADR-risk consequence” trong answer | `services/ml/src/clara_ml/agents/research_tier2.py`, `services/api/src/clara_api/api/v1/endpoints/research.py` | ADR-risk precision@k |
| 6 | Clinical DDI relevance + recommendation quality (PMID: 40590636) | Ràng buộc recommendation chỉ xuất sau verification pass | `services/ml/src/clara_ml/factcheck/nli_verifier.py`, `services/ml/src/clara_ml/rag/pipeline.py` | % recommendation có evidence trực tiếp |
| 7 | npj Digital Medicine 2025 adherence RCT (s41746-025-01748-2) | Tạo template “adherence intervention plan” theo risk segment | `services/ml/src/clara_ml/agents/research_tier2.py`, `apps/web/components/research/markdown-answer.tsx` | Adherence-plan completeness score |
| 8 | JMIR 2025 meta-analysis mHealth older adults (PMID: 40527504) | Tạo mode output “older-adult friendly” (plain language + checklist) | `services/ml/src/clara_ml/agents/research_tier2.py`, `apps/web/components/research/flow-timeline-panel.tsx` | Readability score (vi), user comprehension test |
| 9 | Adherence strategies review 2025 (PMID: 41467772) | Bổ sung ranking ưu tiên can thiệp: reminder + education + follow-up | `services/ml/src/clara_ml/rag/retrieval/reranker.py`, `services/ml/src/clara_ml/agents/research_tier2.py` | Intervention relevance score |
| 10 | DILI-specific RAG 2026 (PMID: 41678290) | Domain pack theo bệnh cảnh (DILI/CKD/HTN) | `services/ml/src/clara_ml/rag/seed_documents.py`, `services/ml/src/clara_ml/rag/retrieval/external_gateway.py` | Domain-grounded accuracy per pack |
| 11 | RAG for EHR dementia 2026 (PMID: 41646828) | Hỗ trợ truy vấn mixed structured+unstructured từ patient context | `services/ml/src/clara_ml/rag/pipeline.py`, `services/ml/src/clara_ml/rag/retrieval/domain.py` | Context retrieval hit-rate |
| 12 | RAG immunogenicity 2026 (PMID: 41566090) | Source-specific retriever adapter + source-aware keyword rewrite | `services/ml/src/clara_ml/rag/retrieval/external_gateway.py`, `services/ml/src/clara_ml/agents/research_tier2.py` | Source success rate by connector |
| 13 | MedGraphRAG ACL 2025 | Đẩy GraphRAG sidecar thành blocking branch trong deep_beta | `services/ml/src/clara_ml/rag/graphrag.py`, `services/ml/src/clara_ml/rag/pipeline.py` | Graph-supported claim ratio |
| 14 | MA-RAG 2026 multi-round | Mở rộng deep_beta nhiều vòng reasoning + contradiction loops | `services/ml/src/clara_ml/agents/research_tier2.py`, `services/ml/src/clara_ml/main.py` | Mean reasoning depth, contradiction resolved |
| 15 | MedBioRAG 2025 hybrid retrieval | Tối ưu hybrid BM25+dense+neural rerank theo loại query y khoa | `services/ml/src/clara_ml/rag/retrieval/score_engine.py`, `services/ml/src/clara_ml/rag/retrieval/reranker.py` | nDCG@10, MRR@10 |
| 16 | npj Digital Medicine 2025 local RAG radiology (DOI: 10.1038/s41746-025-01802-z) | Chế độ local/private RAG mặc định cho ca nhạy cảm dữ liệu | `services/api/src/clara_api/core/config.py`, `services/ml/src/clara_ml/config.py` | Privacy mode adoption, latency p95 |
| 17 | MedHallu EMNLP 2025 benchmark | Thêm hallucination benchmark lane trong scientific eval | `services/ml/tests/test_research_tier2_agent.py`, `docs/hackathon/scientific-eval-testkit-guide-2026-04-01.md` | Hallucination rate, groundedness score |
| 18 | MEGA-RAG public health 2025 | Multi-evidence refinement trước final synthesis | `services/ml/src/clara_ml/agents/research_tier2.py`, `services/ml/src/clara_ml/factcheck/fides_lite.py` | Evidence diversity index |

---

## 2) Prioritized Backlog (production-first)

### P0 (chạy ngay tuần này)
1. Chuẩn hóa output report y khoa (claim table + risk stratification + action checklist).
2. Bật cứng verification-before-recommendation ở deep/deep_beta.
3. Thêm source-aware keyword rewrite theo từng connector (VN vs EN).
4. Thêm metric bắt buộc: `claim_support_rate`, `unsupported_claim_rate`, `refusal_compliance_rate`.

### P1 (1-2 tuần)
1. Domain packs: DILI/CKD/HTN/polypharmacy.
2. GraphRAG sidecar cho contraindication/class-effect.
3. Hallucination benchmark lane + regression gate trong CI.

### P2 (sau vòng 2)
1. Active learning từ production logs (hard-negative mining).
2. Auto policy tuning theo độ tin cậy evidence.
3. Human review console cho ca high-risk.

---

## 3) Standard report contract (để đồng bộ FE/BE)

Backend bắt buộc trả markdown theo khung sau:

1. Clinical question & scope
2. Patient/context assumptions
3. Evidence synthesis (bảng)
4. DDI/ADR risk matrix
5. Contradictions & uncertainty
6. Actionable recommendations (non-prescriptive)
7. Safety disclaimer + escalation triggers
8. Citations

Áp dụng tại:
- `services/ml/src/clara_ml/agents/research_tier2.py`
- `apps/web/components/research/markdown-answer.tsx`

---

## 4) Nguồn tham chiếu chính
- https://pubmed.ncbi.nlm.nih.gov/41609788/
- https://pubmed.ncbi.nlm.nih.gov/40445620/
- https://pubmed.ncbi.nlm.nih.gov/40997804/
- https://pubmed.ncbi.nlm.nih.gov/40999995/
- https://pubmed.ncbi.nlm.nih.gov/40385316/
- https://pubmed.ncbi.nlm.nih.gov/40590636/
- https://pubmed.ncbi.nlm.nih.gov/40527504/
- https://pubmed.ncbi.nlm.nih.gov/41467772/
- https://pubmed.ncbi.nlm.nih.gov/41678290/
- https://pubmed.ncbi.nlm.nih.gov/41646828/
- https://pubmed.ncbi.nlm.nih.gov/41566090/
- https://aclanthology.org/2025.acl-long.1381/
- https://arxiv.org/abs/2603.03292
- https://arxiv.org/abs/2512.10996
- https://www.nature.com/articles/s41746-025-01802-z
- https://aclanthology.org/2025.emnlp-main.143/
- https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2025.1635381/full

---

## 5) Gợi ý thực thi ngay trong sprint hiện tại
1. Chốt `report_contract_v1` (BE/FE thống nhất).
2. Add 30-case eval set cho DDI + 20-case hallucination challenge.
3. Bật CI gate fail nếu `unsupported_claim_rate > ngưỡng`.
4. Demo flow: DeepBeta query -> evidence table -> contradiction matrix -> recommendations + disclaimer.

---

## 6) Kiến thức khoa học đang áp dụng thật trong codebase (kèm evidence)

Mục này trả lời trực tiếp câu hỏi: **CLARA hiện tại đang dùng kiến thức/kỹ thuật rút ra từ nghiên cứu khoa học nào ở mức runtime thực tế**, không phải chỉ nằm trong proposal.

### 6.1 Agentic/Deep RAG nhiều bước + reasoning chain
- Kiến thức áp dụng:
  - Multi-stage orchestration cho deep research (scope -> hypothesis -> retrieval nhiều vòng -> evidence verification -> quality gate -> report synthesis).
  - Tư duy MA-RAG / iterative retrieval + chain verification.
- Nghiên cứu liên quan:
  - MA-RAG 2026 multi-round: https://arxiv.org/abs/2603.03292
  - MEGA-RAG public health 2025: https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2025.1635381/full
- Evidence trong code:
  - `services/ml/src/clara_ml/agents/research_tier2.py:71-86` (`_DEEP_BETA_REASONING_STAGE_ORDER`).
  - `services/ml/src/clara_ml/agents/research_tier2.py:875` (`_run_deep_beta_parallel_reasoning_nodes`).
  - `services/ml/src/clara_ml/agents/research_tier2.py:990` (`_run_deep_beta_evidence_verification_node`).
  - `services/ml/src/clara_ml/agents/research_tier2.py:1126` (`_run_deep_beta_quality_gate`).
  - `services/ml/src/clara_ml/agents/research_tier2.py:1455` (`_synthesize_deep_beta_long_report`).
- Evidence runtime payload:
  - Response có `reasoning_steps`, `parallel_reasoning_nodes`, `evidence_verification`, `chain_status`, `reasoning_digest`.

### 6.2 Neural retrieval/reranking (hybrid + timeout fallback)
- Kiến thức áp dụng:
  - Neural reranker để cải thiện precision@k trên evidence retrieval.
  - Cơ chế timeout/error fallback để giữ ổn định production.
- Nghiên cứu liên quan:
  - MedBioRAG 2025 hybrid retrieval: https://arxiv.org/abs/2512.10996
  - RAG immunogenicity 2026 (PMID: 41566090): https://pubmed.ncbi.nlm.nih.gov/41566090/
- Evidence trong code:
  - `services/ml/src/clara_ml/rag/retrieval/reranker.py:26` (`class NeuralReranker`).
  - `services/ml/src/clara_ml/rag/retrieval/reranker.py:97` (`def rerank`).
  - `services/ml/src/clara_ml/rag/retrieval/reranker.py:115-118`, `216-218`, `259-266` (`rerank_latency_ms`, `rerank_topn`, timeout/error fallback metadata).
  - `services/ml/src/clara_ml/rag/pipeline.py:1675` (log stage index/rerank).
- Evidence runtime payload:
  - `retrieval_trace.index_summary.rerank.*` và metadata `rerank_latency_ms`, `rerank_timed_out`, `rerank_reason`.

### 6.3 GraphRAG sidecar (tri thức đồ thị y sinh)
- Kiến thức áp dụng:
  - Mở rộng evidence từ quan hệ đồ thị domain (drug-class, contraindication-like signals) thay vì chỉ lexical retrieval.
- Nghiên cứu liên quan:
  - MedGraphRAG ACL 2025: https://aclanthology.org/2025.acl-long.1381/
- Evidence trong code:
  - `services/ml/src/clara_ml/rag/graphrag.py:21` (mô tả GraphRAG sidecar).
  - `services/ml/src/clara_ml/rag/graphrag.py:94` (`_load_domain_graph`).
  - `services/ml/src/clara_ml/rag/graphrag.py:296` (`expand`).
  - `services/ml/src/clara_ml/rag/pipeline.py:1971-2021` (stage GraphRAG chạy/fail-soft).
- Evidence runtime payload:
  - Documents có metadata `source: graphrag / graphrag_domain`, `graph_relation`, `graph_source_id`, `graph_target_id`.

### 6.4 Claim-level verification/NLI + contradiction miner (FIDES-lite)
- Kiến thức áp dụng:
  - Claim-level NLI verification để giảm hallucination.
  - Contradiction detection và confidence/severity scoring.
- Nghiên cứu liên quan:
  - MedHallu EMNLP 2025 benchmark: https://aclanthology.org/2025.emnlp-main.143/
  - Medication safety CDSS with LLM (PMID: 40997804): https://pubmed.ncbi.nlm.nih.gov/40997804/
- Evidence trong code:
  - `services/ml/src/clara_ml/factcheck/nli_verifier.py:434` (`verify_claims`).
  - `services/ml/src/clara_ml/factcheck/nli_verifier.py:386` (`contradiction_summary`).
  - `services/ml/src/clara_ml/factcheck/fides_lite.py:324` (`_apply_nli_confidence_gate`).
  - `services/ml/src/clara_ml/factcheck/fides_lite.py:461-507` (severity/confidence decision).
  - `services/ml/src/clara_ml/agents/research_tier2.py:5233-5237` (build `verification_matrix_payload`).
- Evidence runtime payload:
  - `verification_matrix.summary`, `verification_matrix.rows`, `contradiction_summary`, `verification_status`.

### 6.5 Medical legal/safety hard guard (không chỉ prompt)
- Kiến thức áp dụng:
  - Safety-by-design cho hệ y tế: chặn câu hỏi kê đơn/chẩn đoán/liều dùng ngay ở backend gate.
- Nghiên cứu liên quan:
  - Mapping review LLM for DDI (PMID: 40999995): https://pubmed.ncbi.nlm.nih.gov/40999995/
  - Clinical DDI relevance + recommendation quality (PMID: 40590636): https://pubmed.ncbi.nlm.nih.gov/40590636/
- Evidence trong code:
  - `services/ml/src/clara_ml/main.py:35` (`_LEGAL_GUARD_PATTERNS`).
  - `services/ml/src/clara_ml/main.py:223` (`_detect_legal_guard_violation`).
  - `services/ml/src/clara_ml/main.py:266` (`_legal_guard_refusal`).
  - `services/ml/src/clara_ml/main.py:468-470`, `822-824` (chat/research đều bị guard).
  - `services/ml/src/clara_ml/agents/careguard.py:58-59` (chuẩn hóa loại bỏ nhiễu dosage tokens trước phân tích).
- Evidence runtime payload:
  - Trả về `intent: medical_policy_refusal`, `guard_reason`, `model_used: legal-hard-guard-v1`.

### 6.6 Dấu vết frontend cho audit/traceability
- Kiến thức áp dụng:
  - Hiển thị/parse flow + verification ở UI để người dùng/giám khảo thấy toàn bộ reasoning chain.
- Evidence trong code:
  - `apps/web/lib/research.ts:2554` (parse flow events).
  - `apps/web/lib/research.ts:2744-2762` (map `verification_matrix`, `contradiction_summary`).
  - `apps/web/lib/research.ts:3047` (parse telemetry/citation payload).

### 6.7 Mức độ “đã vào code” vs “mới ở tài liệu”
| Nhóm | Trạng thái |
|---|---|
| Agentic Deep Beta flow | Đã chạy runtime |
| Neural reranker + timeout fallback | Đã chạy runtime |
| GraphRAG sidecar | Đã chạy runtime (fail-soft) |
| Claim-level verification + FIDES-lite | Đã chạy runtime |
| Legal hard guard backend | Đã chạy runtime |
| Map PMID/DOI chi tiết theo từng rule trong payload trả lời | **Chưa đầy đủ**, hiện chủ yếu nằm ở docs/benchmark |

### 6.8 Chứng cứ tài liệu nghiên cứu đang dùng để dẫn roadmap
- File bản đồ khoa học hiện tại: `docs/research/latest-science-map-2026-04-04.md` (Sections 1-4).
- Bộ nguồn được map (PMID/DOI/ACL/EMNLP/arXiv) phục vụ roadmap + eval + kiến trúc.
- Link nhanh bộ nghiên cứu chính:
  - https://pubmed.ncbi.nlm.nih.gov/41609788/
  - https://pubmed.ncbi.nlm.nih.gov/40445620/
  - https://pubmed.ncbi.nlm.nih.gov/40997804/
  - https://pubmed.ncbi.nlm.nih.gov/40999995/
  - https://pubmed.ncbi.nlm.nih.gov/40385316/
  - https://pubmed.ncbi.nlm.nih.gov/40590636/
  - https://pubmed.ncbi.nlm.nih.gov/40527504/
  - https://pubmed.ncbi.nlm.nih.gov/41467772/
  - https://pubmed.ncbi.nlm.nih.gov/41678290/
  - https://pubmed.ncbi.nlm.nih.gov/41646828/
  - https://pubmed.ncbi.nlm.nih.gov/41566090/
  - https://aclanthology.org/2025.acl-long.1381/
  - https://aclanthology.org/2025.emnlp-main.143/
  - https://arxiv.org/abs/2603.03292
  - https://arxiv.org/abs/2512.10996
  - https://www.nature.com/articles/s41746-025-01802-z
  - https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2025.1635381/full

> Kết luận ngắn: CLARA hiện đã áp dụng thực tế các trục nghiên cứu quan trọng (Agentic RAG, GraphRAG, neural rerank, NLI/fact-check, legal guard) ở mức code/runtime; phần còn thiếu chính là traceability “claim -> evidence -> study-id” ở mức payload chuẩn hóa cho production audit.

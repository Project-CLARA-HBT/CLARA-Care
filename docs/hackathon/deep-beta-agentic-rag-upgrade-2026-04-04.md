# CLARA Deep Beta: Agentic RAG Upgrade (2026-04-04)

## 1) Vấn đề hiện tại cần xử lý triệt để
- Flow Deep Beta đã có nhiều stage/event nhưng một số bước vẫn thiên về orchestration hơn là reasoning LLM nhiều vòng.
- Evidence verification trước synthesis chưa tách thành node độc lập rõ ràng.
- Output dài có lúc chưa ổn định về cấu trúc hiển thị (table/mermaid/chart-spec), dễ lệch format.
- Khi một số node degraded (timeout/API key), chain status dễ bị hiểu là “đang chạy” thay vì trạng thái terminal.

## 2) Nâng cấp đã triển khai trong codebase

### 2.1 Deep Beta reasoning nâng cấp nhiều node + nhiều vòng
- Mở rộng node catalog từ 3 lên nhóm node chuyên biệt:
  - `deep_beta_evidence_audit`
  - `deep_beta_claim_graph`
  - `deep_beta_counter_evidence_scan`
  - `deep_beta_guideline_alignment`
  - `deep_beta_risk_stratification`
  - `deep_beta_gap_fill`
- Hỗ trợ **multi-round reasoning** (`DEEP_BETA_REASONING_ROUNDS`) để chạy lặp nhiều vòng reasoning thay vì 1 vòng.
- Mỗi kết quả node có metadata `round`, `rounds_total` để theo dõi tiến trình reasoning sâu.

### 2.2 Node kiểm chứng evidence độc lập (trước synthesis)
- Bổ sung node mới: `deep_beta_evidence_verification`.
- Node này tổng hợp `deep_pass_summaries + evidence_rows + reasoning_nodes` và sinh JSON claim-level:
  - `supported_claims`
  - `unsupported_claims`
  - `contradicted_claims`
  - `evidence_gaps`
  - `high_risk_flags`
  - `verification_confidence`
- Kết quả được đẩy vào telemetry/metadata/root payload để frontend hiển thị.

### 2.3 Tăng chất lượng output markdown dài
- Long-form synthesis Deep Beta được tăng ràng buộc:
  - cấm HTML tag trong mermaid
  - bắt buộc section dài + safety caveats + contradictory evidence discussion
- Thêm post-processor bảo đảm artifact đầy đủ:
  - auto bổ sung table nếu thiếu
  - auto bổ sung mermaid nếu thiếu
  - auto bổ sung `chart-spec` nếu thiếu
- Sanitizer backend xử lý các mermaid block có `<br>/<p>/<div>/<span>` để giảm lỗi render.

### 2.4 Chuẩn hóa chain status terminal
- Cập nhật logic chain status để phân biệt:
  - `running` (còn pending)
  - `completed` (toàn bộ terminal, không warning)
  - `warning` (toàn bộ terminal nhưng có degraded/warning)
- Tránh trường hợp job đã xong nhưng status vẫn bị hiểu là đang chạy.

## 3) Config mới đã thêm
- `DEEP_BETA_REASONING_ROUNDS`
- `DEEP_BETA_EVIDENCE_VERIFICATION_ENABLED`
- `DEEP_BETA_EVIDENCE_VERIFICATION_TIMEOUT_SECONDS`

## 4) Test regression đã chạy
- `test_run_research_tier2_deep_beta_emits_beta_stages_and_metadata`
- `test_research_tier2_deep_beta_mode_returns_runtime_contract`
- `test_strip_html_from_mermaid_blocks_removes_html_tags`
- `test_ensure_deep_beta_report_artifacts_appends_missing_blocks`

## 5) Hướng nâng cấp tiếp theo (P1/P2)

### P1 (khuyến nghị ngay sau vòng 2)
- Claim extraction theo sentence-level + citation alignment chặt (claim → evidence span).
- Evidence dedup/ranking theo trust tier (guideline > RCT/meta-analysis > observational > web).
- Adaptive retrieval budget theo uncertainty (high contradiction => tăng pass cho counter-evidence).

### P2 (nâng cấp khoa học sâu)
- GraphRAG nâng cấp typed edges cho miền y sinh:
  - drug-class
  - contraindication
  - mechanism-of-action
  - adverse-event
- Neural verifier calibration bằng holdout benchmark (ECE/Brier/confidence bins).
- Active evaluation loop + hard-negative mining tự động từ production logs.

## 6) Pattern/khung kỹ thuật tham chiếu
- Multi-agent workflow orchestration (planner / retriever / critic / verifier / synthesizer).
- Corrective retrieval loops (retrieval → verify → gap-fill → re-retrieve).
- Self-reflection / self-critique for RAG answer refinement.
- Graph-enhanced retrieval cho câu hỏi nhiều quan hệ (drug-drug, contraindication, subgroup).
- RAG evaluation stack: groundedness, context precision/recall, contradiction rate, refusal compliance.

## 7) KPI khuyến nghị cho Deep Beta
- `evidence_verification_confidence` (mean/p50/p95)
- `contradicted_claim_rate`
- `unsupported_claim_rate`
- `quality_gate_revision_rate`
- `deep_beta_latency_ms` theo stage (planner/retrieval/reasoning/verification/synthesis)
- `fallback_rate` (strict mode vs non-strict)

---
Tài liệu này phản ánh đúng trạng thái code sau đợt nâng cấp Deep Beta ngày 2026-04-04.

# Đặc Tả Runtime Và Định Tuyến CLARA

Phiên bản: 2.1  
Ngày cập nhật: 2026-03-24

## 1. Luồng runtime đầu-cuối

1. `input gateway (Rust)`: nhận request từ web/Flutter, gắn trace id.
2. `safety ingress (Rust)`: lọc PII/PHI, kiểm consent, chuẩn hóa input ban đầu.
3. `router B1`: phân loại role.
4. `router B2`: phân loại intent theo role.
5. `planner/supervisor (LangGraph)`: lập execution graph.
6. `retrieval agents`: truy xuất đồng thời theo nguồn/phương thức.
7. `synthesis node`: tạo draft + claim set.
8. `verification node (FIDES-inspired)`: kiểm chứng độc lập.
9. `policy gate (Rust)`: quyết định cuối (`allow/warn/block/escalate`).
10. `response + audit`: trả phản hồi + ghi log/audit đầy đủ.

## 2. Taxonomy intent theo role

### 2.1 Normal user
- selfmed_ddi_check
- selfmed_dose_guidance
- selfmed_medication_reminder
- selfmed_expiry_and_storage
- selfmed_basic_health_qa
- emergency_signal

### 2.2 Researcher
- lit_review_quick
- lit_review_deep
- guideline_compare
- trial_scan
- source_conflict_analysis
- export_report

### 2.3 Doctor
- clinical_support
- medication_safety
- protocol_compliance
- ai_council_case
- scribe_structuring
- emergency_signal

## 3. Ma trận định tuyến nguồn theo intent

| Intent | Nguồn ưu tiên | Nguồn phụ | Policy note |
|---|---|---|---|
| selfmed_ddi_check | RxNorm, openFDA, Dược thư VN | BYT alerts | block nếu conflict high-risk |
| selfmed_expiry_and_storage | BYT, WHO | web recheck | warn nếu nguồn không đủ |
| lit_review_deep | PubMed, ClinicalTrials | guideline quốc tế | bắt buộc citation đầy đủ |
| guideline_compare | BYT + guideline quốc tế | PubMed tổng quan | phải hiển thị phần bất đồng |
| ai_council_case | guideline chuyên khoa + hồ sơ ca bệnh | PubMed mới | log hội chẩn bắt buộc |

## 4. Chi tiết RAG processing

### 4.1 Ingestion layer
- text parser
- PDF OCR parser
- image parser
- ASR parser

### 4.2 Normalization layer
- chuẩn hóa thuật ngữ VN,
- map entity sang ICD/RxCUI,
- chuẩn hóa đơn vị đo lường.

### 4.3 Retrieval layer
- dense recall,
- sparse recall,
- rerank,
- cross-modal fusion.

### 4.4 Synthesis + Verification layer
- synthesis chỉ tạo draft,
- verification đánh giá độ tin cậy claim,
- policy gate quyết định công bố/phong tỏa/escalation.

## 5. LangChain/LangGraph runtime contract

### 5.1 LangGraph orchestration
- Graph node chuẩn: `route -> retrieve -> synthesize -> verify -> policy -> respond`.
- Supervisor hỗ trợ nhánh song song cho AI Council.
- Checkpoint state cho luồng dài (research 5-10-20).

### 5.2 LangChain tools/retrievers/templates
- Tool registry: calculator, source connector adapters.
- Retriever abstraction: dense/sparse/hybrid.
- Prompt template versioning theo role + intent + risk.

### 5.3 Boundary Rust và AI service
- Rust giữ gateway/auth/rbac/tenant/policy/audit/cache.
- AI service (LangGraph/LangChain) chỉ nhận payload đã chuẩn hóa + quyền giới hạn.
- Mọi output AI phải qua policy enforcement tại Rust trước khi trả ra ngoài.

### 5.4 Luồng KHÔNG dùng LLM
- DDI critical hard-stop.
- Dị ứng thuốc hard-stop.
- Rule dose contra-indication deterministic.
- Compliance block bắt buộc.

## 6. Budget thời gian theo workflow

| Role | Mức độ | Ngân sách |
|---|---|---|
| Normal user | simple | < 2 phút |
| Researcher | quick/deep | 5 / 10 / 20 phút |
| Doctor | specialized/council | < 10-20 phút |

## 7. AI Council logging requirements

Phải lưu:
- timeline từng specialist agent,
- bằng chứng mỗi nhánh,
- điểm đồng thuận/bất đồng,
- hành động policy cuối,
- lý do escalation (nếu có).

## 8. System Management Dashboard runtime integration

Dashboard chạy trên control-plane, đọc từ event bus/audit store/metrics store:
- user/role/tenant panel,
- model/prompt/policy registry,
- eval jobs và drift monitor,
- source connector health + freshness,
- incident center,
- audit explorer + compliance reports.

## 9. Fallback và fail-safe

- Router confidence thấp -> luồng an toàn + hỏi thêm ngữ cảnh.
- OCR/ASR chất lượng thấp -> yêu cầu xác nhận.
- Verification fail -> block hoặc escalate.
- Source outage -> degrade có cảnh báo rõ.

## 10. Checklist release runtime

- Intent benchmark pass.
- Retrieval/fusion benchmark pass.
- FIDES regression pass.
- KPI latency theo role pass.
- Audit completeness >= 99% phiên risk cao.
- Dashboard alerts và incident workflow hoạt động end-to-end.

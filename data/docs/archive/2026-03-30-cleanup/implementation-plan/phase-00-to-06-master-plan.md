# Kế Hoạch Tổng Giai Đoạn P0-P6

Phiên bản: 3.0  
Ngày cập nhật: 2026-03-24

## 1. Bối cảnh triển khai

CLARA triển khai đồng thời 2 nhánh sản phẩm:
- **CLARA Research**: nghiên cứu y khoa đa nguồn, đa tác tử.
- **CLARA Self-Med**: quản lý thuốc cá nhân/gia đình, DDI, tuân thủ điều trị.

Nền tảng triển khai:
- Frontend: Web + Mobile Flutter.
- Backend runtime: Rust (ưu tiên mặc định).
- AI orchestration: LangChain + LangGraph.
- ML services: Python (OCR/ASR/Embedding/Rerank/Generation/Verifier).
- Control-plane: `System Control Tower Dashboard` quản trị toàn bộ hệ thống.

### 1.1 Nguyên tắc migration OCR + ADE từ tgc-transhub

- Reuse có kiểm soát, không copy nguyên khối: chỉ lấy các thành phần đã chứng minh hiệu quả cho OCR/ADE.
- Ưu tiên 3 lớp kỹ thuật: GCP Vision OCR multi-pass, ADE preprocess/scoring, layout telemetry + quality gate.
- Mọi bước migration phải có benchmark trước/sau trên bộ dữ liệu chuẩn của CLARA Self-Med.
- P0-P2 là giai đoạn bắt buộc để hoàn tất migration vào Self-Med MVP.

---

## 2. P0 — Foundation (Sprint 1-2)

### 2.1 Mục tiêu
- Dựng nền kiến trúc, contract, observability baseline.
- Khởi tạo LangGraph orchestration skeleton và Rust gateway.
- Khởi động dashboard control-plane ở mức nền.
- Chốt blueprint migration OCR + ADE từ `tgc-transhub`.

### 2.2 Phạm vi
- In: auth, role input, skeleton router, connector skeleton, telemetry baseline, OCR/ADE migration discovery.
- Out: AI Council production, enterprise multi-tenant nâng cao.

### 2.3 Gói công việc
- WP0-1: Monorepo + chuẩn coding + CI nền.
- WP0-2: Rust gateway/auth/session/rate-limit skeleton.
- WP0-3: LangGraph state graph skeleton (simple route -> retrieve -> synthesize -> verify).
- WP0-4: Flutter app shell + web shell + role selection.
- WP0-5: Dashboard v0: login admin, health overview, service status, error feed.
- WP0-6: OCR/ADE migration blueprint từ `tgc-transhub` (contract, risk matrix, benchmark corpus, mapping module).

### 2.4 Deliverables dashboard
- Dashboard v0 có 4 widget: uptime, error rate, queue depth, connector heartbeat.
- Có audit trail cho login/admin actions.

### 2.4.1 Deliverables migration OCR + ADE
- Tài liệu mapping thành phần reuse: `preprocess`, `scoring`, `layout telemetry`, `quality gate`.
- Contract OCR/ADE v1 cho CLARA (input/output, confidence semantics, decision reason codes).
- Bộ benchmark khởi điểm cho Self-Med scan thuốc (barcode + OCR fallback) với baseline metrics đã chốt.

### 2.5 Mốc hoàn thành
- M0.1: end-to-end request chạy qua web/app -> Rust -> LangGraph -> response.
- M0.2: dashboard v0 hiển thị health và log cơ bản realtime.
- M0.3: phê duyệt gói migration OCR/ADE P1-P2 với backlog kỹ thuật đã ưu tiên.

### 2.6 Phụ thuộc
- API keys, hạ tầng cloud, dữ liệu seed VN + quốc tế.
- Truy cập artefact kỹ thuật từ `tgc-transhub` và tập mẫu scan thuốc cho benchmark.

### 2.7 Nhân sự theo vai trò
- Product/Program, Frontend, Backend Rust, ML/NLP, Security/Compliance.

### 2.8 Lịch sprint
- Sprint 1: kiến trúc + skeleton runtime.
- Sprint 2: integration + dashboard v0.

### 2.9 Cổng chất lượng
- Build pass >= 95%, smoke pass 100%.
- Trace ID đi xuyên suốt >= 99% request.
- Baseline OCR/layout metrics được lưu và có thể tái lập (reproducible).

### 2.10 Rủi ro
- Trễ setup infra, thiếu dữ liệu chuẩn hóa ban đầu.

### 2.11 Tiêu chí hoàn tất
- Có baseline chạy được, dashboard theo dõi được vận hành nền.

---

## 3. P1 — Core RAG + Intent Router (Sprint 3-6)

### 3.1 Mục tiêu
- Hoàn thiện intent router 2 lớp.
- Hoàn thiện workflow simple cho normal users (<2 phút).
- Đưa dashboard lên mức quality + routing observability.
- Hoàn tất lớp tích hợp OCR/ADE v1 từ `tgc-transhub` ở môi trường staging.

### 3.2 Phạm vi
- In: role router, intent router theo role, RAG v1, verifier lite, OCR/ADE adapter và telemetry ingestion.
- Out: AI Council chuyên khoa đầy đủ.

### 3.3 Gói công việc
- WP1-1: B1 Role Classification + threshold policy.
- WP1-2: B2 Intent Classification per role.
- WP1-3: retrieval/rerank/synthesis/verification tách node.
- WP1-4: Self-Med DDI base check.
- WP1-5: Dashboard v1: router confidence panel, latency panel, citation coverage panel.
- WP1-6: Tích hợp GCP Vision OCR multi-pass + ADE preprocess/scoring + early-stop gates theo contract CLARA.
- WP1-7: Thu layout telemetry (`smoothness/overlap/reading-order`) và nối vào quality gates.

### 3.4 Deliverables dashboard
- Màn hình theo role: Normal/Researcher/Doctor traffic split.
- Màn hình quality: verification pass, policy actions distribution.

### 3.4.1 Deliverables migration OCR + ADE
- Adapter OCR/ADE chạy ổn định trên staging cho luồng scan thuốc.
- Báo cáo A/B baseline cũ vs pipeline reuse (`tgc-transhub`) cho chất lượng OCR/layout.
- Bộ ngưỡng vận hành ban đầu: `OCR_GCP_MIN_TEXT_SCORE`, `OCR_GCP_MIN_BBOX_SCORE`, `OCR_GCP_EARLY_STOP`.

### 3.5 Mốc hoàn thành
- M1.1: intent router ổn định ở staging.
- M1.2: normal user KPI <2 phút đạt ngưỡng.
- M1.3: dashboard v1 phản ánh routing/quality theo thời gian thực.
- M1.4: OCR/ADE v1 qua regression gate và sẵn sàng rollout hạn chế (canary).

### 3.6 Phụ thuộc
- Milvus/Elastic/Redis/Postgres ổn định + dữ liệu ingest baseline.

### 3.7 Nhân sự theo vai trò
- ML/NLP lead routing/verifier; Backend lead API/cache; Frontend lead UI simple.

### 3.8 Lịch sprint
- Sprint 3: role router + ingest.
- Sprint 4: intent router + retrieval.
- Sprint 5: verify + policy.
- Sprint 6: hardening + dashboard v1.

### 3.9 Cổng chất lượng
- Citation coverage >= 90%.
- Emergency fast-path < 1 giây.
- OCR early-accept hit rate và layout metrics đạt ngưỡng staging đã phê duyệt.

### 3.10 Rủi ro
- Route nhầm do dữ liệu training lệch.

### 3.11 Tiêu chí hoàn tất
- Luồng simple production-candidate + dashboard v1.

---

## 4. P2 — Core Features (Sprint 7-10)

### 4.1 Mục tiêu
- Nâng cấp CLARA Research (5-10-20).
- Self-Med MVP usable.
- Dashboard có module vận hành nghiệp vụ.
- Hoàn tất migration OCR/ADE vào luồng Self-Med production candidate.

### 4.2 Phạm vi
- In: progressive research, DDI + reminder + family dashboard, scribe baseline, Self-Med scan barcode/OCR với ADE scoring + guardrails.
- Out: AI Council production đầy đủ.

### 4.3 Gói công việc
- WP2-1: research progressive response + export.
- WP2-2: Self-Med OCR/barcode/RxNorm mapping.
- WP2-3: escalation alerts + allergy warnings + expiry management.
- WP2-4: medical scribe baseline.
- WP2-5: Dashboard v2: adherence analytics, DDI alert analytics, source freshness board.
- WP2-6: Áp dụng policy routing theo confidence OCR/ADE (auto-accept vs yêu cầu xác nhận người dùng).
- WP2-7: Tích hợp quality telemetry vào vận hành Self-Med (manual review queue, regression gate theo release).

### 4.4 Deliverables dashboard
- Widget tuân thủ điều trị theo gia đình/cohort.
- Widget DDI critical detection trend.
- Widget freshness BYT/Dược thư/PubMed/openFDA/RxNorm.

### 4.4.1 Deliverables migration OCR + ADE
- Self-Med MVP dùng chung pipeline scan thuốc dựa trên reuse OCR/ADE từ `tgc-transhub`.
- Dashboard v2 có panel riêng cho OCR/ADE quality: confidence distribution, low-confidence rate, manual review rate.
- Runbook vận hành cho fallback: barcode fail -> OCR fail -> xác nhận thủ công -> escalate.

### 4.5 Mốc hoàn thành
- M2.1: Research 5-10-20 ổn định.
- M2.2: Self-Med MVP hoạt động end-to-end.
- M2.3: dashboard v2 có KPI nghiệp vụ và cảnh báo dữ liệu cũ.
- M2.4: migration OCR/ADE P0-P2 đóng, đủ điều kiện production candidate.

### 4.6 Phụ thuộc
- Connectors RxNorm/openFDA/BYT chạy ổn định.

### 4.7 Nhân sự theo vai trò
- Frontend, Backend Rust, ML/NLP, Product Ops, Clinical reviewer.

### 4.8 Lịch sprint
- Sprint 7-8: research + export + dashboard analytics.
- Sprint 9-10: Self-Med core + scribe + dashboard v2.

### 4.9 Cổng chất lượng
- DDI critical sensitivity >= 98%.
- Reminder delivery SLA >= 99%.
- Tỷ lệ scan thuốc cần can thiệp thủ công giảm theo mục tiêu vận hành của Self-Med MVP.

### 4.10 Rủi ro
- OCR/ASR lỗi làm sai cảnh báo.

### 4.11 Tiêu chí hoàn tất
- Research Tier 2 + Self-Med MVP usable + dashboard nghiệp vụ.

---

## 5. P3 — Advanced (Sprint 11-14)

### 5.1 Mục tiêu
- Bật doctor workflow nâng cao + AI Council logs.
- Dashboard có module governance cho model/prompt/policy.

### 5.2 Phạm vi
- In: AI Council, FIDES v2, doctor dashboard, governance center.
- Out: rollout toàn quốc.

### 5.3 Gói công việc
- WP3-1: AI Council orchestration + specialist agents.
- WP3-2: deliberation logging + export.
- WP3-3: verifier strict mode và policy escalation.
- WP3-4: dashboard governance v3 (model registry, prompt registry, policy registry).

### 5.4 Deliverables dashboard
- Màn hình model version + prompt version + policy version.
- Màn hình duyệt release AI (approve/reject + audit trail).
- Màn hình AI Council logs explorer.

### 5.5 Mốc hoàn thành
- M3.1: doctor workflow 10-20 phút đạt KPI.
- M3.2: AI Council logs đầy đủ và truy vết được.
- M3.3: dashboard governance v3 vận hành được release flow.

### 5.6 Phụ thuộc
- Clinical reviewers và dữ liệu pilot.

### 5.7 Nhân sự theo vai trò
- ML/NLP, Backend Rust, Frontend/Admin dashboard, Clinical governance.

### 5.8 Lịch sprint
- Sprint 11-12: council core + logs.
- Sprint 13: strict verification + governance center.
- Sprint 14: pilot readiness.

### 5.9 Cổng chất lượng
- Hallucination rate < 5% (benchmark nội bộ).
- Council log integrity = 100%.

### 5.10 Rủi ro
- Độ trễ cao do nhiều specialist song song.

### 5.11 Tiêu chí hoàn tất
- Doctor flow pilot-ready + dashboard governance sẵn sàng.

---

## 6. P4 — Production Hardening (Sprint 15-18)

### 6.1 Mục tiêu
- Ổn định production và nâng cấp control-plane vận hành sự cố.

### 6.2 Phạm vi
- In: autoscaling, DR, incident center, on-call workflows.
- Out: mở rộng quốc tế.

### 6.3 Gói công việc
- WP4-1: tối ưu Rust runtime (latency, throughput, memory).
- WP4-2: hardening web/Flutter + telemetry.
- WP4-3: DR drills và runbook.
- WP4-4: dashboard incident center (Sev0-Sev3, MTTR board, runbook linkage).

### 6.4 Deliverables dashboard
- Incident center + timeline + owner + SLA.
- Error budget panel theo role/workflow.
- Connector outage impact panel.

### 6.5 Mốc hoàn thành
- M4.1: availability đạt mục tiêu.
- M4.2: MTTR giảm theo target.
- M4.3: dashboard incident center đi vào vận hành.

### 6.6 Phụ thuộc
- On-call rotation, monitoring stack, ngân sách hạ tầng.

### 6.7 Nhân sự theo vai trò
- Platform/SRE lead + service owners liên quan.

### 6.8 Lịch sprint
- Sprint 15-16: hardening.
- Sprint 17-18: DR + incident center.

### 6.9 Cổng chất lượng
- Availability >= 99.9%.
- Không còn P1 unresolved quá SLA.

### 6.10 Rủi ro
- Chi phí hạ tầng tăng nhanh khi scale.

### 6.11 Tiêu chí hoàn tất
- Production ổn định, có kiểm soát sự cố chủ động qua dashboard.

---

## 7. P5 — Enterprise Scale (Sprint 19-22)

### 7.1 Mục tiêu
- Mở rộng enterprise: multi-tenant + compliance + cost governance.

### 7.2 Phạm vi
- In: tenant isolation, audit package, billing/cost board.
- Out: quốc tế hóa đầy đủ.

### 7.3 Gói công việc
- WP5-1: multi-tenant architecture và RBAC nâng cao.
- WP5-2: compliance evidence pipeline.
- WP5-3: enterprise connectors.
- WP5-4: dashboard billing/cost + tenant governance.

### 7.4 Deliverables dashboard
- Tenant management console.
- Billing/cost observability (cost per workflow, cost per role, cost per tenant).
- Compliance report generator.

### 7.5 Mốc hoàn thành
- M5.1: tenant isolation pass audit.
- M5.2: enterprise pilot đầu tiên live.
- M5.3: dashboard cost/compliance vận hành được.

### 7.6 Phụ thuộc
- Yêu cầu tích hợp đối tác + pháp lý.

### 7.7 Nhân sự theo vai trò
- Backend/platform + Product + Security/Compliance.

### 7.8 Lịch sprint
- Sprint 19-20: tenant + governance.
- Sprint 21-22: enterprise integration + billing board.

### 7.9 Cổng chất lượng
- Security/compliance audit pass.
- Cost variance trong ngưỡng cho phép.

### 7.10 Rủi ro
- Scope creep theo yêu cầu enterprise.

### 7.11 Tiêu chí hoàn tất
- Enterprise mode vận hành ổn định qua dashboard control-plane.

---

## 8. P6 — Ecosystem Expansion (Sprint 23-26)

### 8.1 Mục tiêu
- Mở rộng hệ sinh thái dữ liệu/đối tác, tối ưu hiệu quả vận hành toàn cục.

### 8.2 Phạm vi
- In: thêm connector mới, partner APIs, data federation controls.
- Out: thay đổi kiến trúc lõi gây gián đoạn lớn.

### 8.3 Gói công việc
- WP6-1: mở rộng connector VN/quốc tế.
- WP6-2: tối ưu cost/performance liên nền tảng.
- WP6-3: nâng cấp governance theo dữ liệu thực tế.
- WP6-4: dashboard ecosystem center (partner health, data trust score, federation alerts).

### 8.4 Deliverables dashboard
- Partner health board.
- Data trust score per source/partner.
- Federation alert center.

### 8.5 Mốc hoàn thành
- M6.1: mở rộng cohort lớn thành công.
- M6.2: cost per active user giảm theo mục tiêu.
- M6.3: dashboard ecosystem center hoàn thiện.

### 8.6 Phụ thuộc
- Đối tác dữ liệu, pháp lý, ngân sách scale.

### 8.7 Nhân sự theo vai trò
- Toàn đội core + partner manager + compliance.

### 8.8 Lịch sprint
- Sprint 23-24: partner/data expansion.
- Sprint 25-26: optimize + stabilize.

### 8.9 Cổng chất lượng
- KPI theo role duy trì ổn định.
- Không tăng cảnh báo sai mức nghiêm trọng.

### 8.10 Rủi ro
- Drift theo nguồn mới và tăng độ phức tạp quản trị.

### 8.11 Tiêu chí hoàn tất
- Hệ sinh thái mở rộng ổn định, có roadmap năm kế tiếp dựa trên dashboard dữ liệu thật.

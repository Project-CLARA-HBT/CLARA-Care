# Kế hoạch triển khai siêu chi tiết P1 -> P6 (Micro-task level)

Phiên bản: 1.0  
Ngày cập nhật: 2026-03-25  
Phạm vi: Chỉ P1->P6 (không bao gồm P0)

## 1) Quy ước dùng trong tài liệu

- Effort chuẩn:
  - XS: 0.25 ngày (2 giờ)
  - S: 0.5 ngày (4 giờ)
  - M: 1 ngày (8 giờ)
  - L: 1.5 ngày (12 giờ)
- Mỗi micro-task phải hoàn tất đủ: code + test + telemetry/log tối thiểu + tài liệu ngắn.
- Test command tham chiếu theo repo hiện tại:
  - API/ML: `make lint && make type-check && make test`
  - API target: `cd services/api && pytest -q <test_file>`
  - ML target: `cd services/ml && pytest -q <test_file>`
  - Web: `cd apps/web && npm run lint && npm run build`
  - Flutter Android: `cd apps/mobile && flutter analyze && flutter test`

---

## 2) P1 - Core RAG + Intent Router + Self-Med staging + Chat UX foundation

### 2.1 Mục tiêu

- Ổn định route phân vai trò và intent ở staging.
- Chạy được luồng chat web v2 kiểu Perplexity/Gemini (summary + evidence panel).
- Hoàn tất nền tảng Self-Med scan job + OCR/ADE adapter contract ở staging.
- Khởi tạo Flutter Android route skeleton theo route map đã chốt.

### 2.2 Gate

- Entry gate:
  - API auth/session ổn định trên staging.
  - ML service có endpoint router/retrieval cơ bản.
- Exit gate:
  - Citation coverage >= 90% trên bộ test P1.
  - Latency p95 luồng chat thường <= 2 phút end-to-end.
  - Luồng `scan-invoice -> scan-processing -> review/recognized` chạy được với `scanJobId` có trace.

### 2.3 Dependencies

- Redis/Postgres/Milvus/Elasticsearch hoạt động ổn định.
- Bộ dữ liệu seed cho role/intent + scan thuốc mẫu.
- Feature flags sẵn sàng cho rollout canary.

### 2.4 Deliverables

- Intent router v1 (role + intent).
- Chat UI web v2 (thread + evidence panel).
- Self-Med scan orchestration v1 (staging).
- Flutter Android route skeleton v1.

### 2.5 Danh sách micro-task đánh số

1. [P1-MT01][BE] Chốt API contract role/intent v1.
- Phụ thuộc: không.
- DoD: contract request/response, enum lỗi, error code và sample payload được chốt trong docs nội bộ.
- Effort: S.
- Output file/service: `services/api/src/clara_api/schemas.py`, service `api`.
- Test cần chạy: `cd services/api && pytest -q tests/test_chat_proxy.py tests/test_auth_and_rbac.py`.

2. [P1-MT02][ML] Tách node `role_classifier` và `intent_classifier` trong routing graph.
- Phụ thuộc: P1-MT01.
- DoD: graph có 2 node độc lập, output confidence riêng, fallback path khi confidence thấp.
- Effort: M.
- Output file/service: `services/ml/src/clara_ml/routing.py`, service `ml`.
- Test cần chạy: `cd services/ml && pytest -q tests/test_router.py`.

3. [P1-MT03][ML] Thêm threshold policy cho route nhạy cảm y tế.
- Phụ thuộc: P1-MT02.
- DoD: policy `allow/warn/escalate` map theo confidence band; có unit test biên ngưỡng.
- Effort: S.
- Output file/service: `services/ml/src/clara_ml/routing.py`, service `ml`.
- Test cần chạy: `cd services/ml && pytest -q tests/test_router.py tests/test_main_api.py`.

4. [P1-MT04][BE+ML] Tách flow retrieval -> rerank -> synthesize -> verify thành node rõ ràng.
- Phụ thuộc: P1-MT02.
- DoD: trace thể hiện đủ 4 stage; verifier trả về verdict + reason.
- Effort: L.
- Output file/service: `services/ml/src/clara_ml/main.py`, `services/api/src/clara_api/main.py`.
- Test cần chạy: `cd services/ml && pytest -q tests/test_rag_pipeline.py tests/test_nlp_modules.py`.

5. [P1-MT05][UIX] Dựng chat layout web kiểu Perplexity/Gemini bản nền.
- Phụ thuộc: P1-MT01.
- DoD: có thread chính, ô nhập lớn, panel nguồn tham chiếu bật/tắt được.
- Effort: M.
- Output file/service: `apps/web/app/research/page.tsx`, `apps/web/components/app-shell.tsx`, service `web`.
- Test cần chạy: `cd apps/web && npm run lint && npm run build`.

6. [P1-MT06][UIX] Chuẩn response card: summary + confidence + nguồn + next actions.
- Phụ thuộc: P1-MT05, P1-MT04.
- DoD: mọi câu trả lời hiển thị đủ 4 block; tối đa 2 CTA chính.
- Effort: S.
- Output file/service: `apps/web/components/page-skeleton.tsx`, `apps/web/lib/research.ts`.
- Test cần chạy: `cd apps/web && npm run lint && npm run build`.

7. [P1-MT07][SM] Tạo scan job lifecycle API (`queued|processing|needs_review|recognized|completed|failed`).
- Phụ thuộc: P1-MT01.
- DoD: có endpoint tạo job + lấy trạng thái; trả `scan_job_id` xuyên suốt.
- Effort: M.
- Output file/service: `services/api/src/clara_api/main.py`, service `api`.
- Test cần chạy: `cd services/api && pytest -q tests/test_p2_proxy_endpoints.py tests/test_system_endpoints.py`.

8. [P1-MT08][SM] Tích hợp OCR/ADE adapter contract v1 ở staging.
- Phụ thuộc: P1-MT07.
- DoD: adapter trả candidate + confidence + decision reason; có fallback barcode->OCR.
- Effort: L.
- Output file/service: service `api` + `ml` (interface integration).
- Test cần chạy: `make test`.

9. [P1-MT09][SM] Thu telemetry bắt buộc cho scan flow.
- Phụ thuộc: P1-MT08.
- DoD: lưu được `scan_job_id`, `ocr_text_score`, `ocr_bbox_score`, `decision_reason`.
- Effort: S.
- Output file/service: `services/ml/src/clara_ml/observability.py`, service `ml`.
- Test cần chạy: `cd services/ml && pytest -q tests/test_main_api.py`.

10. [P1-MT10][FL] Khởi tạo Flutter route constants + guard khung Android-first.
- Phụ thuộc: không.
- DoD: route constants cho auth/app/research/self-med/dashboard; guard đăng nhập hoạt động.
- Effort: M.
- Output file/service: `apps/mobile/lib/app.dart`, `apps/mobile/lib/screens/*`.
- Test cần chạy: `cd apps/mobile && flutter analyze && flutter test`.

11. [P1-MT11][FL+SM] Tạo các màn hình placeholder Self-Med critical routes.
- Phụ thuộc: P1-MT10.
- DoD: điều hướng được tới `scan-invoice`, `scan-processing`, `scan-review`, `ddi-result` bằng mock id.
- Effort: M.
- Output file/service: `apps/mobile/lib/screens/careguard_screen.dart` + screen files mới.
- Test cần chạy: `cd apps/mobile && flutter analyze && flutter test`.

12. [P1-MT12][OPS] Gate CI cho P1 (lint/type-check/unit/smoke routing).
- Phụ thuộc: P1-MT02..P1-MT11.
- DoD: pipeline fail nếu thiếu test chính; report rõ module fail.
- Effort: S.
- Output file/service: `.github/workflows/ci.yml`, service `ci`.
- Test cần chạy: `make lint && make type-check && make test`.

---

## 3) P2 - Core Features: Research 5-10-20 + Self-Med MVP + route E2E

### 3.1 Mục tiêu

- Bật luồng Research 5-10-20 có citation/verify rõ ràng.
- Chạy Self-Med MVP end-to-end: cabinet -> scan hóa đơn -> nhận diện -> auto-add -> auto DDI.
- Hoàn thiện UX web onboarding + guide + chat v2 rollout rộng.
- Flutter Android chạy được deep-link và state restore cho scan flow.

### 3.2 Gate

- Entry gate:
  - P1 exit gate đạt.
  - OCR/ADE adapter v1 ổn định trên staging.
- Exit gate:
  - DDI critical sensitivity >= 98% trên bộ test nội bộ.
  - Reminder/escalation path hoạt động đúng policy.
  - Scan-to-DDI end-to-end pass >= 95% ca kiểm thử chuẩn.

### 3.3 Dependencies

- Kết nối RxNorm/openFDA/BYT đang khả dụng.
- Bộ policy engine `allow/warn/block/escalate` đã được clinical review.

### 3.4 Deliverables

- Research progressive response (5-10-20).
- Self-Med MVP production-candidate.
- UX web onboarding funnel hoàn chỉnh.
- Flutter deep-link + resume state cho scan/DDI.

### 3.5 Danh sách micro-task đánh số

1. [P2-MT01][ML] Cài progressive response 5-10-20 cho research session.
- Phụ thuộc: P1-MT04.
- DoD: trả 3 lớp câu trả lời theo mốc 5s/10s/20s; mỗi lớp có status và trace.
- Effort: L.
- Output file/service: `services/ml/src/clara_ml/main.py`, service `ml`.
- Test cần chạy: `cd services/ml && pytest -q tests/test_rag_pipeline.py tests/test_main_api.py`.

2. [P2-MT02][UIX] Render streaming 5-10-20 ở web chat workspace.
- Phụ thuộc: P2-MT01, P1-MT06.
- DoD: UI hiển thị tiến trình theo block; người dùng thấy bản tóm tắt trước chi tiết.
- Effort: M.
- Output file/service: `apps/web/app/research/page.tsx`, `apps/web/lib/chat.ts`.
- Test cần chạy: `cd apps/web && npm run lint && npm run build`.

3. [P2-MT03][UIX] Hoàn thiện landing + huong-dan funnel cho người mới.
- Phụ thuộc: không.
- DoD: CTA xuyên suốt `landing -> huong-dan -> login -> research/self-med`; copy tiếng Việt đồng nhất.
- Effort: M.
- Output file/service: `apps/web/app/page.tsx`, `apps/web/app/huong-dan/page.tsx`, `apps/web/app/login/page.tsx`.
- Test cần chạy: `cd apps/web && npm run lint && npm run build`.

4. [P2-MT04][SM] Thêm model dữ liệu cabinet item + lịch sử scan nguồn.
- Phụ thuộc: P1-MT07.
- DoD: lưu được thuốc theo thành viên gia đình, source scan và thời gian thêm.
- Effort: M.
- Output file/service: `services/api/alembic/versions/*`, `services/api/src/clara_api/schemas.py`, service `api`.
- Test cần chạy: `cd services/api && pytest -q tests/test_system_endpoints.py tests/test_p2_proxy_endpoints.py`.

5. [P2-MT05][SM] Implement API `auto-add` từ scan job đã recognized.
- Phụ thuộc: P2-MT04, P1-MT08.
- DoD: chỉ auto-add khi confidence đạt ngưỡng; nếu thấp phải trả `needs_review`.
- Effort: M.
- Output file/service: `services/api/src/clara_api/main.py`, service `api`.
- Test cần chạy: `cd services/api && pytest -q tests/test_p2_proxy_endpoints.py`.

6. [P2-MT06][SM] Implement API `auto-ddi-check` chạy ngay sau auto-add.
- Phụ thuộc: P2-MT05.
- DoD: tạo `ddi_check_id`; trả severity max + policy action; retry khi timeout.
- Effort: M.
- Output file/service: `services/api/src/clara_api/main.py`, service `api`.
- Test cần chạy: `cd services/api && pytest -q tests/test_p2_proxy_endpoints.py tests/test_chat_proxy.py`.

7. [P2-MT07][SM] UI web CareGuard cho flow scan hóa đơn -> review -> cabinet -> DDI result.
- Phụ thuộc: P2-MT05, P2-MT06.
- DoD: người dùng đi hết flow không cần reload; trạng thái lỗi/retry rõ.
- Effort: L.
- Output file/service: `apps/web/app/careguard/page.tsx`, `apps/web/lib/careguard.ts`.
- Test cần chạy: `cd apps/web && npm run lint && npm run build`.

8. [P2-MT08][FL] Flutter deep-link map cho toàn bộ route Self-Med critical.
- Phụ thuộc: P1-MT11.
- DoD: mở app bằng link `scanJobId/ddiCheckId` đúng màn hình; guard role đúng.
- Effort: M.
- Output file/service: `apps/mobile/lib/app.dart`, `apps/mobile/lib/screens/*`.
- Test cần chạy: `cd apps/mobile && flutter analyze && flutter test`.

9. [P2-MT09][FL+SM] Flutter state restore khi app kill ở `scan-processing`.
- Phụ thuộc: P2-MT08.
- DoD: mở lại app phục hồi job state; không tạo scan job trùng.
- Effort: M.
- Output file/service: `apps/mobile/lib/core/session_store.dart`, `apps/mobile/lib/screens/careguard_screen.dart`.
- Test cần chạy: `cd apps/mobile && flutter analyze && flutter test`.

10. [P2-MT10][SM] Policy gate confidence-based routing (auto-accept/manual confirm).
- Phụ thuộc: P2-MT05, P2-MT06.
- DoD: ngưỡng policy cấu hình được; có audit log quyết định.
- Effort: S.
- Output file/service: `services/api/src/clara_api/main.py`, service `api`.
- Test cần chạy: `cd services/api && pytest -q tests/test_auth_and_rbac.py tests/test_p2_proxy_endpoints.py`.

11. [P2-MT11][OPS] Dashboard panel cho OCR/ADE quality + manual review queue.
- Phụ thuộc: P1-MT09, P2-MT10.
- DoD: hiển thị confidence distribution, low-confidence rate, manual review rate theo ngày.
- Effort: M.
- Output file/service: `apps/web/app/dashboard/page.tsx`, `apps/web/lib/system.ts`.
- Test cần chạy: `cd apps/web && npm run lint && npm run build`.

12. [P2-MT12][OPS] Regression suite scan-to-ddi trước release.
- Phụ thuộc: P2-MT05..P2-MT11.
- DoD: có suite pass/fail rõ cho happy path + fallback + timeout + retry.
- Effort: M.
- Output file/service: `services/api/tests/*`, `services/ml/tests/*`.
- Test cần chạy: `make test`.

---

## 4) P3 - Advanced: Doctor workflow + AI Council + Governance + UX nâng cao

### 4.1 Mục tiêu

- Bật doctor workflow 10-20 phút có deliberation logs đầy đủ.
- Triển khai governance center cho model/prompt/policy release.
- Nâng cấp chat UX sang chế độ chuyên sâu (analysis steps + compare sources).
- Đồng bộ handoff Self-Med nguy cơ cao sang doctor workflow.

### 4.2 Gate

- Entry gate:
  - P2 exit gate đạt.
  - Bộ clinical reviewer sẵn sàng pilot.
- Exit gate:
  - Council log integrity = 100%.
  - Hallucination benchmark nội bộ < 5%.
  - Handoff ca `block/escalate` từ Self-Med sang doctor queue không mất trace.

### 4.3 Dependencies

- Prompt registry/versioning framework.
- Chính sách phê duyệt release AI (approve/reject).

### 4.4 Deliverables

- AI Council orchestration v1.
- Governance dashboard v3.
- Chat expert mode cho web + route doctor flow trong mobile.

### 4.5 Danh sách micro-task đánh số

1. [P3-MT01][ML] Tạo orchestration specialist agents cho council.
- Phụ thuộc: P2-MT01.
- DoD: có planner + specialist nodes + synthesizer; log từng lượt tranh luận.
- Effort: L.
- Output file/service: `services/ml/src/clara_ml/main.py`, service `ml`.
- Test cần chạy: `cd services/ml && pytest -q tests/test_rag_pipeline.py tests/test_nlp_modules.py`.

2. [P3-MT02][BE] Lưu deliberation logs với trace id và version prompt/model.
- Phụ thuộc: P3-MT01.
- DoD: truy vấn được lịch sử theo session; export JSON/MD.
- Effort: M.
- Output file/service: `services/api/src/clara_api/main.py`, `services/api/alembic/versions/*`.
- Test cần chạy: `cd services/api && pytest -q tests/test_council_proxy.py tests/test_system_endpoints.py`.

3. [P3-MT03][OPS] Governance registry cho model/prompt/policy.
- Phụ thuộc: P3-MT02.
- DoD: có CRUD + trạng thái `draft/approved/rejected/rollback`.
- Effort: L.
- Output file/service: `services/api/src/clara_api/main.py`, `apps/web/app/dashboard/ecosystem/page.tsx`.
- Test cần chạy: `make test && cd apps/web && npm run lint`.

4. [P3-MT04][UIX] Bật chat expert mode (panel steps, compare citations, policy badge).
- Phụ thuộc: P2-MT02, P3-MT01.
- DoD: toggle giữa chế độ cơ bản và expert; UI không phá luồng cơ bản.
- Effort: M.
- Output file/service: `apps/web/app/research/page.tsx`, `apps/web/lib/research.ts`.
- Test cần chạy: `cd apps/web && npm run lint && npm run build`.

5. [P3-MT05][UIX] Chuẩn hóa warning language cho `warn/block/escalate` trong chat và self-med.
- Phụ thuộc: P2-MT07.
- DoD: thông điệp thống nhất, có khuyến nghị bước kế tiếp, không mơ hồ trách nhiệm.
- Effort: S.
- Output file/service: `apps/web/app/careguard/page.tsx`, `apps/web/app/research/page.tsx`.
- Test cần chạy: `cd apps/web && npm run lint && npm run build`.

6. [P3-MT06][SM] Handoff tự động ca DDI nguy cơ cao sang doctor queue.
- Phụ thuộc: P2-MT06, P3-MT02.
- DoD: case `block/escalate` sinh task doctor; giữ link `scan_job_id` + `ddi_check_id`.
- Effort: M.
- Output file/service: `services/api/src/clara_api/main.py`, service `api`.
- Test cần chạy: `cd services/api && pytest -q tests/test_p2_proxy_endpoints.py tests/test_council_proxy.py`.

7. [P3-MT07][FL] Thêm doctor review route trên Android app.
- Phụ thuộc: P2-MT08, P3-MT06.
- DoD: bác sĩ mở alert và xem đủ context scan/DDI/citation trên mobile.
- Effort: M.
- Output file/service: `apps/mobile/lib/screens/council_screen.dart`, route file liên quan.
- Test cần chạy: `cd apps/mobile && flutter analyze && flutter test`.

8. [P3-MT08][OPS] Dashboard explorer cho council logs + filter theo severity/role.
- Phụ thuộc: P3-MT02.
- DoD: tìm được log theo session/user/time; export được audit artifact.
- Effort: M.
- Output file/service: `apps/web/app/dashboard/page.tsx`, `apps/web/lib/system.ts`.
- Test cần chạy: `cd apps/web && npm run lint && npm run build`.

9. [P3-MT09][ML] Strict verifier mode cho câu trả lời doctor-facing.
- Phụ thuộc: P3-MT01.
- DoD: bắt buộc citation tối thiểu theo policy; thiếu citation thì downgrade confidence.
- Effort: M.
- Output file/service: `services/ml/src/clara_ml/main.py`, service `ml`.
- Test cần chạy: `cd services/ml && pytest -q tests/test_rag_pipeline.py tests/test_prompt_loader.py`.

10. [P3-MT10][OPS] Pilot readiness checklist automation.
- Phụ thuộc: P3-MT03..P3-MT09.
- DoD: checklist auto đánh dấu từ test/report, không phụ thuộc nhập tay.
- Effort: S.
- Output file/service: `scripts/*`, dashboard release panel.
- Test cần chạy: `make lint && make type-check && make test`.

---

## 5) P4 - Production Hardening: Reliability, Incident, Performance

### 5.1 Mục tiêu

- Đạt ổn định production (availability, latency, incident response).
- Hardening toàn tuyến web/mobile/api/ml cho traffic thật.
- Chuẩn hóa runbook sự cố và DR drill định kỳ.

### 5.2 Gate

- Entry gate:
  - P3 pilot chạy ổn định.
  - Có baseline SLO theo dịch vụ.
- Exit gate:
  - Availability >= 99.9%.
  - Không còn incident P1 unresolved quá SLA.
  - MTTR giảm theo target đã chốt.

### 5.3 Dependencies

- On-call rotation + owner rõ theo service.
- Monitoring stack và alerting kênh trực sự cố.

### 5.4 Deliverables

- Incident center + runbook linkage.
- Bộ benchmark hiệu năng API/ML/Web/Mobile.
- DR drill report có khuyến nghị cải tiến.

### 5.5 Danh sách micro-task đánh số

1. [P4-MT01][OPS] Chốt SLO/SLI/error budget theo workflow chính.
- Phụ thuộc: P3-MT10.
- DoD: tài liệu SLO có owner, ngưỡng cảnh báo và escalation matrix.
- Effort: S.
- Output file/service: `docs/implementation-plan/metrics-gates-and-operating-model.md` (append), service `ops`.
- Test cần chạy: kiểm tra dashboard metrics và alert rule dry-run.

2. [P4-MT02][BE] Tối ưu API hot paths cho chat và self-med.
- Phụ thuộc: P2-MT06, P3-MT09.
- DoD: p95 latency giảm theo target, không giảm độ đúng policy.
- Effort: L.
- Output file/service: `services/api/src/clara_api/main.py`.
- Test cần chạy: `cd services/api && pytest -q tests/test_chat_proxy.py tests/test_p2_proxy_endpoints.py`.

3. [P4-MT03][ML] Tối ưu ML inference/routing cache strategy.
- Phụ thuộc: P2-MT01.
- DoD: cache hit-rate và timeout handling cải thiện; không stale citation.
- Effort: M.
- Output file/service: `services/ml/src/clara_ml/main.py`, `services/ml/src/clara_ml/config.py`.
- Test cần chạy: `cd services/ml && pytest -q tests/test_main_api.py tests/test_rag_pipeline.py`.

4. [P4-MT04][UIX] Performance pass cho web chat và careguard.
- Phụ thuộc: P2-MT07, P3-MT04.
- DoD: giảm render blocking; skeleton/loading state nhất quán.
- Effort: M.
- Output file/service: `apps/web/app/research/page.tsx`, `apps/web/app/careguard/page.tsx`.
- Test cần chạy: `cd apps/web && npm run lint && npm run build`.

5. [P4-MT05][FL] Hardening Android: retry/offline banner/session refresh.
- Phụ thuộc: P2-MT09.
- DoD: mất mạng có fallback UI; reconnect không mất context screen.
- Effort: M.
- Output file/service: `apps/mobile/lib/core/api_client.dart`, `apps/mobile/lib/screens/*`.
- Test cần chạy: `cd apps/mobile && flutter analyze && flutter test`.

6. [P4-MT06][SM] Idempotency cho auto-add và auto-ddi.
- Phụ thuộc: P2-MT06.
- DoD: request lặp không tạo bản ghi trùng; log rõ source retry.
- Effort: S.
- Output file/service: `services/api/src/clara_api/main.py`, `services/api/src/clara_api/schemas.py`.
- Test cần chạy: `cd services/api && pytest -q tests/test_p2_proxy_endpoints.py`.

7. [P4-MT07][OPS] Xây Incident Center UI (Sev0-Sev3, timeline, owner, SLA).
- Phụ thuộc: P4-MT01.
- DoD: incident có state machine rõ, liên kết được runbook và postmortem.
- Effort: M.
- Output file/service: `apps/web/app/dashboard/ecosystem/page.tsx`, `apps/web/lib/system.ts`.
- Test cần chạy: `cd apps/web && npm run lint && npm run build`.

8. [P4-MT08][OPS] Runbook chuẩn cho 3 sự cố chính (ML timeout, OCR drift, DDI queue backlog).
- Phụ thuộc: P4-MT07.
- DoD: mỗi runbook có trigger, triage steps, rollback steps, owner.
- Effort: S.
- Output file/service: `docs/implementation-plan/*` runbook docs.
- Test cần chạy: diễn tập tabletop + xác nhận alert routing.

9. [P4-MT09][OPS] DR drill tự động hóa theo lịch.
- Phụ thuộc: P4-MT08.
- DoD: có báo cáo drill pass/fail, RTO/RPO thực tế.
- Effort: M.
- Output file/service: `scripts/*`, service `ops`.
- Test cần chạy: dry-run DR script + kiểm tra data restore sample.

10. [P4-MT10][OPS] Chốt production hardening gate report.
- Phụ thuộc: P4-MT02..P4-MT09.
- DoD: report đầy đủ availability, MTTR, incident trend, residual risk.
- Effort: S.
- Output file/service: dashboard release report + doc gate.
- Test cần chạy: `make lint && make type-check && make test`.

---

## 6) P5 - Enterprise Scale: Multi-tenant + Compliance + Cost governance

### 6.1 Mục tiêu

- Mở chế độ enterprise với tenant isolation và RBAC nâng cao.
- Có pipeline bằng chứng compliance và báo cáo audit.
- Quản trị chi phí theo tenant/workflow/role.

### 6.2 Gate

- Entry gate:
  - P4 production hardening đạt.
  - Security baseline và key management đã chốt.
- Exit gate:
  - Tenant isolation pass audit.
  - Cost variance trong ngưỡng cho phép.
  - Enterprise pilot đầu tiên vận hành ổn định.

### 6.3 Dependencies

- Yêu cầu pháp lý và hợp đồng tích hợp đối tác enterprise.
- Chính sách data retention theo tenant.

### 6.4 Deliverables

- Multi-tenant architecture + RBAC enterprise.
- Compliance evidence pipeline.
- Billing/cost board trong control tower.

### 6.5 Danh sách micro-task đánh số

1. [P5-MT01][BE] Thêm tenant context vào auth/session/token.
- Phụ thuộc: P4-MT10.
- DoD: mọi request có tenant_id rõ; reject nếu tenant context thiếu.
- Effort: M.
- Output file/service: `services/api/src/clara_api/main.py`, `services/api/src/clara_api/schemas.py`.
- Test cần chạy: `cd services/api && pytest -q tests/test_auth_and_rbac.py tests/test_auth_me_and_mobile_summary.py`.

2. [P5-MT02][BE] Cập nhật schema dữ liệu theo tenant isolation.
- Phụ thuộc: P5-MT01.
- DoD: bảng chính có tenant key + index; query cross-tenant bị chặn.
- Effort: L.
- Output file/service: `services/api/alembic/versions/*`, service `api`.
- Test cần chạy: `cd services/api && pytest -q tests/test_system_endpoints.py`.

3. [P5-MT03][BE] RBAC enterprise roles (tenant_admin, tenant_ops, tenant_clinician).
- Phụ thuộc: P5-MT01.
- DoD: role matrix enforce được trên endpoint nhạy cảm.
- Effort: M.
- Output file/service: `services/api/src/clara_api/main.py`.
- Test cần chạy: `cd services/api && pytest -q tests/test_auth_and_rbac.py`.

4. [P5-MT04][OPS] Compliance event collector (audit trail bất biến).
- Phụ thuộc: P5-MT02.
- DoD: log sự kiện auth/data-access/policy-change đầy đủ actor/time/tenant.
- Effort: M.
- Output file/service: `services/api/src/clara_api/main.py`, `services/ml/src/clara_ml/observability.py`.
- Test cần chạy: `make test`.

5. [P5-MT05][OPS] Generator báo cáo compliance theo kỳ.
- Phụ thuộc: P5-MT04.
- DoD: xuất report theo tenant/tháng/quý, truy vết được event nguồn.
- Effort: M.
- Output file/service: `scripts/*`, dashboard compliance panel.
- Test cần chạy: test script với sample data + kiểm tra định dạng output.

6. [P5-MT06][OPS] Cost attribution theo workflow (chat, self-med, council).
- Phụ thuộc: P4-MT01.
- DoD: đo được cost/request và cost/tenant; có anomaly flag.
- Effort: M.
- Output file/service: `services/ml/src/clara_ml/observability.py`, `apps/web/app/dashboard/ecosystem/page.tsx`.
- Test cần chạy: `cd services/ml && pytest -q tests/test_main_api.py` + `cd apps/web && npm run lint`.

7. [P5-MT07][UIX] Tenant management console (web ops).
- Phụ thuộc: P5-MT03.
- DoD: tạo/sửa/khóa tenant; xem role mapping và trạng thái tích hợp.
- Effort: M.
- Output file/service: `apps/web/app/dashboard/ecosystem/page.tsx`, `apps/web/lib/system.ts`.
- Test cần chạy: `cd apps/web && npm run lint && npm run build`.

8. [P5-MT08][FL] Tenant-aware config trên Flutter Android.
- Phụ thuộc: P5-MT01.
- DoD: app nhận tenant profile sau login; route guard dựa role + tenant policy.
- Effort: S.
- Output file/service: `apps/mobile/lib/core/session_store.dart`, `apps/mobile/lib/app.dart`.
- Test cần chạy: `cd apps/mobile && flutter analyze && flutter test`.

9. [P5-MT09][SM] Self-Med data partition theo tenant/family boundary.
- Phụ thuộc: P5-MT02.
- DoD: không đọc chéo dữ liệu cabinet/DDI giữa tenant; audit pass.
- Effort: M.
- Output file/service: `services/api/src/clara_api/main.py`, storage schema.
- Test cần chạy: `cd services/api && pytest -q tests/test_p2_proxy_endpoints.py tests/test_auth_and_rbac.py`.

10. [P5-MT10][OPS] Enterprise pilot go-live checklist.
- Phụ thuộc: P5-MT01..P5-MT09.
- DoD: checklist tự động hóa và có sign-off security/compliance/product.
- Effort: S.
- Output file/service: release checklist docs + ops dashboard.
- Test cần chạy: `make lint && make type-check && make test`.

---

## 7) P6 - Ecosystem Expansion: Partner connectors + federation + tối ưu toàn cục

### 7.1 Mục tiêu

- Mở rộng connector đối tác dữ liệu trong và ngoài nước.
- Tăng data trust score và giảm cost per active user.
- Duy trì chất lượng an toàn y tế khi mở rộng quy mô.

### 7.2 Gate

- Entry gate:
  - P5 enterprise pilot ổn định.
  - Quy trình legal/onboarding partner hoàn chỉnh.
- Exit gate:
  - Cohort mở rộng đạt KPI retention và safety.
  - Cost/active user giảm theo target.
  - Không tăng false critical alerts ngoài ngưỡng kiểm soát.

### 7.3 Dependencies

- Hợp đồng và SLA kỹ thuật từ đối tác data/API.
- Bộ kiểm định trust score và drift monitoring.

### 7.4 Deliverables

- Ecosystem center dashboard hoàn chỉnh.
- Connector framework v2 có health scoring.
- Bộ governance chống drift cho nguồn mới.

### 7.5 Danh sách micro-task đánh số

1. [P6-MT01][BE] Chuẩn connector interface v2 (auth, fetch, retry, quality metadata).
- Phụ thuộc: P5-MT10.
- DoD: interface thống nhất cho connector mới; có contract test mẫu.
- Effort: M.
- Output file/service: `services/api/src/clara_api/main.py`, `services/ml/src/clara_ml/config.py`.
- Test cần chạy: `make test`.

2. [P6-MT02][BE+ML] Thêm connector partner A (y khoa) theo interface v2.
- Phụ thuộc: P6-MT01.
- DoD: ingest được dữ liệu, mapping schema chuẩn, có retry/backoff.
- Effort: L.
- Output file/service: `services/ml/src/clara_ml/main.py`, service connector.
- Test cần chạy: `cd services/ml && pytest -q tests/test_nlp_modules.py tests/test_main_api.py`.

3. [P6-MT03][BE+ML] Thêm connector partner B (drug safety) theo interface v2.
- Phụ thuộc: P6-MT01.
- DoD: fetch ổn định, dedupe đúng, freshness timestamp chuẩn.
- Effort: L.
- Output file/service: `services/ml/src/clara_ml/main.py`, service connector.
- Test cần chạy: `cd services/ml && pytest -q tests/test_main_api.py`.

4. [P6-MT04][OPS] Data trust scoring pipeline theo nguồn/partner.
- Phụ thuộc: P6-MT02, P6-MT03.
- DoD: tính trust score minh bạch từ freshness/completeness/conflict rate.
- Effort: M.
- Output file/service: `services/ml/src/clara_ml/observability.py`, dashboard ecosystem.
- Test cần chạy: `cd services/ml && pytest -q tests/test_rag_pipeline.py`.

5. [P6-MT05][OPS] Drift detection cho intent/retrieval khi thêm nguồn mới.
- Phụ thuộc: P6-MT04.
- DoD: cảnh báo drift vượt ngưỡng; có đề xuất rollback source priority.
- Effort: M.
- Output file/service: `services/ml/src/clara_ml/routing.py`, monitoring rules.
- Test cần chạy: `cd services/ml && pytest -q tests/test_router.py`.

6. [P6-MT06][UIX] Ecosystem center UI: partner health + trust score + federation alerts.
- Phụ thuộc: P6-MT04.
- DoD: board hiển thị theo partner/time; drill-down tới incident và runbook.
- Effort: M.
- Output file/service: `apps/web/app/dashboard/ecosystem/page.tsx`.
- Test cần chạy: `cd apps/web && npm run lint && npm run build`.

7. [P6-MT07][SM] Re-validate Self-Med DDI với nguồn mở rộng.
- Phụ thuộc: P6-MT02, P6-MT03.
- DoD: sensitivity DDI critical không giảm; false positive trong ngưỡng.
- Effort: M.
- Output file/service: `services/api/src/clara_api/main.py`, `services/ml/src/clara_ml/main.py`.
- Test cần chạy: `cd services/api && pytest -q tests/test_p2_proxy_endpoints.py` + `cd services/ml && pytest -q tests/test_rag_pipeline.py`.

8. [P6-MT08][FL] Android app cập nhật partner-source badges trong màn hình evidence.
- Phụ thuộc: P6-MT04.
- DoD: người dùng thấy nguồn chính và mức tin cậy trên mobile chat/self-med.
- Effort: S.
- Output file/service: `apps/mobile/lib/screens/research_screen.dart`, `apps/mobile/lib/screens/careguard_screen.dart`.
- Test cần chạy: `cd apps/mobile && flutter analyze && flutter test`.

9. [P6-MT09][OPS] Cost optimization wave 2 (cache/prompt/model routing).
- Phụ thuộc: P6-MT05.
- DoD: cost/active user giảm theo target mà không giảm quality gate.
- Effort: M.
- Output file/service: `services/ml/src/clara_ml/config.py`, `services/ml/src/clara_ml/main.py`.
- Test cần chạy: `cd services/ml && pytest -q tests/test_main_api.py tests/test_prompt_loader.py`.

10. [P6-MT10][OPS] Chốt roadmap năm kế tiếp bằng dữ liệu thực tế P1->P6.
- Phụ thuộc: P6-MT01..P6-MT09.
- DoD: có backlog ưu tiên theo impact/risk/cost; có proposal gates mới.
- Effort: S.
- Output file/service: `docs/implementation-plan/*` roadmap docs.
- Test cần chạy: review chéo Product + Eng + Clinical + Ops.

---

## 8) Nhánh bắt buộc (tách riêng để điều phối)

### 8.1 Nhánh UI/UX chat kiểu Perplexity/Gemini

- Mục tiêu nhánh: giao diện hỏi đáp tập trung, hiển thị summary trước, evidence minh bạch, giảm overload nút.
- Micro-task thuộc nhánh này:
  - P1-MT05, P1-MT06
  - P2-MT02, P2-MT03
  - P3-MT04, P3-MT05
  - P4-MT04
  - P6-MT06
- Gate nhánh:
  - TTFAnswer giảm theo target nội bộ.
  - Tỷ lệ user hỏi tiếp tăng và không giảm citation coverage.

### 8.2 Nhánh Self-Med cabinet -> scan hóa đơn -> auto DDI

- Mục tiêu nhánh: số hóa tủ thuốc an toàn, tự động hóa nhưng không bỏ quality gate.
- Micro-task thuộc nhánh này:
  - P1-MT07, P1-MT08, P1-MT09
  - P2-MT04, P2-MT05, P2-MT06, P2-MT07, P2-MT10, P2-MT12
  - P3-MT06
  - P4-MT06
  - P5-MT09
  - P6-MT07
- Gate nhánh:
  - DDI critical sensitivity >= 98%.
  - Manual review rate giảm dần nhưng không tăng sai cảnh báo nghiêm trọng.

### 8.3 Nhánh Flutter Android routes

- Mục tiêu nhánh: route tree chuẩn Android-first, deep link tốt, state restore ổn định cho luồng critical.
- Micro-task thuộc nhánh này:
  - P1-MT10, P1-MT11
  - P2-MT08, P2-MT09
  - P3-MT07
  - P4-MT05
  - P5-MT08
  - P6-MT08
- Gate nhánh:
  - Deep link pass cho route critical.
  - App resume không mất `scanJobId/ddiCheckId`.

---

## 9) Cách chia multiagent: mỗi agent 1 micro-task

### 9.1 Nguyên tắc vận hành

- Mỗi agent chỉ nhận đúng 1 micro-task ID tại một thời điểm.
- Không agent nào tự ý mở rộng scope sang micro-task khác.
- Agent phải bàn giao bằng chứng DoD + test log + file thay đổi.
- Nếu blocked > 30 phút: trả task về điều phối, không tự đổi mục tiêu.

### 9.2 Template giao việc ngắn (copy dùng ngay)

```text
[ASSIGNMENT]
Agent: AGENT_<ID>
Micro-task ID: <P?-MT??>
Mục tiêu 1 câu: <kết quả cuối cùng cần đạt>
Phụ thuộc cần có trước: <ID hoặc "none">
Output bắt buộc: <file/service cụ thể>
DoD bắt buộc: <checklist ngắn, measurable>
Test phải chạy: <commands cụ thể>
Thời gian ước lượng: <XS/S/M/L>
Báo cáo khi xong: <PR link + test output + rủi ro còn lại>
```

### 9.3 Mẫu phân công nhanh theo 3 nhánh bắt buộc

- AGENT_UI_01 -> `P2-MT02` (streaming 5-10-20 trên web chat).
- AGENT_SM_01 -> `P2-MT06` (auto DDI check API).
- AGENT_FL_01 -> `P2-MT08` (deep-link Self-Med critical routes).


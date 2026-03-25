# Audit Căn Chỉnh Kiến Trúc - Kế Hoạch Triển Khai (v3)

Phiên bản: 3.0  
Ngày audit: 2026-03-25  
Phạm vi: đối chiếu `docs/architecture/*` với `docs/implementation-plan/*`.

## 1) Bảng mismatch và hướng khắc phục

| Mismatch | Impact | Fix | File to update |
|---|---|---|---|
| **Self-Med permanent cabinet chưa được đặc tả đầy đủ**: kiến trúc yêu cầu quản lý tủ thuốc có `batch/hạn dùng/liều/lịch` và bước xác nhận trước lưu; plan triển khai mới dừng nhiều ở flow MVP `scan -> auto-add -> auto DDI`, chưa chốt vòng đời dữ liệu tủ thuốc dài hạn (lịch sử thay đổi, archive/restore, chống trùng lâu dài). | Rủi ro mất tính liên tục hồ sơ dùng thuốc, khó audit y khoa, khó mở rộng enterprise/family lâu dài. | Bổ sung “Permanent Cabinet Spec v1”: mô hình dữ liệu vòng đời (`active/archived/disposed`), event log bất biến, idempotency key, retention policy, cross-device sync rules. | `docs/architecture/clara-platform-architecture.md`; `docs/implementation-plan/workstream-clara-self-med.md`; `docs/implementation-plan/p1-to-p6-microtasks-detailed-plan.md`; `docs/implementation-plan/flutter-android-route-map.md` |
| **OCR/ADE từ `tgc-transhub` có lệch chuẩn tài liệu**: kiến trúc yêu cầu contract versioned + telemetry + regression gate; implementation có mô tả nhưng còn tham chiếu tuyệt đối `/Users/...`, naming biến thể preprocess chưa thống nhất, chưa có 1 “single contract doc” cho reason code/confidence semantics. | Khó tái lập môi trường, tăng rủi ro regression khi chuyển team/onboard, dễ lệch logic policy theo confidence. | Chuẩn hóa 1 tài liệu contract OCR/ADE canonical trong CLARA; thay toàn bộ absolute path bằng tham chiếu tái lập được; thống nhất naming preprocess/reason code. | `docs/implementation-plan/flutter-android-route-map.md`; `docs/implementation-plan/workstream-clara-self-med.md`; `docs/implementation-plan/phase-00-to-06-master-plan.md` |
| **Thiếu hoàn toàn nhánh “DeepSeek fallback khi RAG empty”** ở cả kiến trúc runtime và kế hoạch thực thi. Hiện chỉ có fallback router/OCR/source outage mức chung, không có đường đi cụ thể khi retrieval rỗng. | Khi RAG không trả tài liệu: hoặc trả lời rỗng (UX xấu), hoặc fallback không kiểm soát (tăng nguy cơ hallucination/compliance). | Thêm nhánh runtime chính thức: `retrieve_empty -> deepseek_fallback -> verify -> policy`; định nghĩa điều kiện kích hoạt, intent/role cho phép, nhãn cảnh báo bắt buộc, telemetry và release gate riêng. | `docs/architecture/clara-runtime-and-routing.md`; `docs/architecture/clara-platform-architecture.md`; `docs/implementation-plan/workstream-clara-research.md`; `docs/implementation-plan/p1-to-p6-microtasks-detailed-plan.md`; `docs/implementation-plan/metrics-gates-and-operating-model.md` |
| **Auth full flow chưa đồng bộ web/app/backend**: web sitemap có `/login /register /role-select`; Flutter có thêm `/auth/otp` và `/auth/consent`; backend plan chưa có contract endpoint đầy đủ cho consent, refresh/revoke, logout-all, session/device control. | Nguy cơ lệch hành vi giữa kênh web/mobile, thiếu bằng chứng consent trước routing y tế, khó pass audit bảo mật/compliance. | Lập “Auth E2E Flow Spec v1” dùng chung web+Flutter+Rust: login/register, OTP/MFA, consent capture/versioning, token lifecycle (issue/refresh/revoke), role switch, session revocation, logout all devices. | `docs/implementation-plan/web-sitemap-v2.md`; `docs/implementation-plan/flutter-android-route-map.md`; `docs/implementation-plan/backend-rust-plan.md`; `docs/implementation-plan/p1-to-p6-microtasks-detailed-plan.md`; `docs/architecture/clara-runtime-and-routing.md` |
| **Chưa có module dashboard dạng Dify-like flow editor** (visual graph editor cho workflow LangGraph) trong cả architecture dashboard module và implementation dashboard roadmap. | Không có bề mặt vận hành để chỉnh/simulate/publish workflow an toàn; phụ thuộc sửa code trực tiếp, tăng risk release. | Bổ sung module “Workflow Studio”: canvas node-edge, validate graph, dry-run/simulation, versioning + approve/reject + rollback, RBAC audit. | `docs/architecture/clara-platform-architecture.md`; `docs/implementation-plan/system-control-tower-dashboard-plan.md`; `docs/implementation-plan/phase-00-to-06-master-plan.md`; `docs/implementation-plan/p1-to-p6-microtasks-detailed-plan.md` |
| **Multi-page UX chưa đủ chiều sâu cho web**: mobile đã có route map chi tiết theo state, nhưng web mới dừng IA/sitemap mức cao, chưa có route con cho flow dài (research session/citations/verify/export, self-med scan/review/result), chưa chốt quy tắc deep link/back/restore giữa nhiều trang. | Dễ gãy hành trình khi người dùng đi flow dài, khó làm analytics funnel theo bước, tăng dead-end và rework frontend. | Tạo web route map đa trang tương đương mức chi tiết Flutter; chuẩn hóa trạng thái chuyển trang, lỗi/retry, breadcrumb, deep link và resume state. | `docs/implementation-plan/web-sitemap-v2.md`; `docs/implementation-plan/frontend-web-ux-revamp-plan.md`; `docs/implementation-plan/frontend-web-mobile-flutter-plan.md`; `docs/implementation-plan/p1-to-p6-microtasks-detailed-plan.md` |
| **Control Tower chưa bao phủ đủ module bắt buộc theo kiến trúc**: kiến trúc yêu cầu rõ `User/Role/Tenant`, `Eval Jobs + Drift`, `Feature Flags + Rollout`; plan dashboard hiện thiên về health/routing/incidents/cost. | Khoảng mù vận hành và governance; thiếu bề mặt kiểm soát release AI end-to-end. | Mở rộng module và roadmap P1-P6 của Control Tower để bao phủ đủ IAM/tenant, eval/drift và feature-flag rollout. | `docs/implementation-plan/system-control-tower-dashboard-plan.md`; `docs/implementation-plan/phase-00-to-06-master-plan.md`; `docs/implementation-plan/frontend-web-mobile-flutter-plan.md` |
| **Ma trận fallback phân tán, chưa có 1 nguồn chuẩn liên tài liệu** (router low confidence, OCR fail, verification fail, source outage, retrieval empty nằm rải rác). | Hành vi fail-safe có thể không nhất quán giữa team backend/ML/frontend/ops. | Tạo fallback decision matrix thống nhất theo trigger -> action -> owner -> SLA -> metric; bắt buộc tham chiếu chéo từ workstream và microtask plan. | `docs/architecture/clara-runtime-and-routing.md`; `docs/implementation-plan/metrics-gates-and-operating-model.md`; `docs/implementation-plan/workstream-clara-research.md`; `docs/implementation-plan/workstream-clara-self-med.md` |

## 2) Backlog khắc phục ưu tiên P1 -> P6 (micro-task)

### P1 (Critical: safety + compliance)

1. **P1-MT01**: Viết `Auth E2E Flow Spec v1` thống nhất web/mobile/backend, gồm consent bắt buộc trước runtime routing.  
   DoD: có sequence diagram + endpoint matrix + session/token lifecycle + negative cases.
2. **P1-MT02**: Cập nhật runtime spec với nhánh `DeepSeek fallback khi RAG empty` kèm policy constraints theo role/intent.  
   DoD: trigger rõ, output label rõ, không bypass verify/policy.
3. **P1-MT03**: Đồng bộ micro-task plan để có test gate cho auth + deepseek fallback.  
   DoD: có task BE/ML/UI/OPS và tiêu chí pass/fail theo phase.

### P2 (Critical: Self-Med data integrity)

1. **P2-MT01**: Bổ sung “Permanent Cabinet Spec v1” cho Self-Med.  
   DoD: đủ lifecycle, event history, retention, soft-delete/restore, family boundary.
2. **P2-MT02**: Chốt route/API cho cabinet đa trạng thái (active/archive/dispose/history).  
   DoD: route map + API contract + guard role đầy đủ.
3. **P2-MT03**: Thêm gate chất lượng dữ liệu tủ thuốc dài hạn.  
   DoD: metric duplicate rate, restore success rate, audit completeness.

### P3 (High: OCR/ADE migration quality)

1. **P3-MT01**: Tạo canonical OCR/ADE contract doc (versioning + reason code + confidence semantics).  
   DoD: tất cả docs implementation tham chiếu cùng một contract.
2. **P3-MT02**: Xóa toàn bộ absolute path `/Users/...` và thay bằng tham chiếu tái lập được.  
   DoD: không còn absolute path trong docs implementation.
3. **P3-MT03**: Chuẩn hóa naming preprocess variants giữa architecture và implementation.  
   DoD: danh mục biến thể thống nhất 1-1, không alias mơ hồ.

### P4 (High: Dashboard operability)

1. **P4-MT01**: Mở rộng Control Tower module parity với kiến trúc (IAM/tenant, eval/drift, feature flags).  
   DoD: roadmap dashboard P1-P6 có deliverable rõ cho từng module.
2. **P4-MT02**: Đặc tả “Workflow Studio” kiểu Dify-like cho graph runtime.  
   DoD: có chức năng edit/validate/simulate/publish/rollback + audit trail.
3. **P4-MT03**: Bổ sung API/control contracts cho flow editor và release pipeline.  
   DoD: endpoint list + payload tối thiểu + quyền truy cập theo role.

### P5 (Medium: Multi-page UX and route parity)

1. **P5-MT01**: Viết web multi-page route map chi tiết ngang mức Flutter route map.  
   DoD: bao phủ full flow research và self-med dài bước.
2. **P5-MT02**: Chuẩn hóa UX state giữa nhiều trang: loading/empty/error/retry/resume/back navigation.  
   DoD: mỗi flow có state table và hành vi back/refresh/deep-link rõ.
3. **P5-MT03**: Bổ sung KPI funnel đa trang + test scenario E2E theo từng role.  
   DoD: có acceptance criteria đo được theo bước hành trình.

### P6 (Medium: Governance chống lệch tài liệu)

1. **P6-MT01**: Tạo checklist alignment bắt buộc khi cập nhật architecture hoặc implementation plan.  
   DoD: mỗi thay đổi phải chỉ rõ file cặp cần sync.
2. **P6-MT02**: Thêm doc gate định kỳ để phát hiện drift (module thiếu, fallback thiếu, route lệch).  
   DoD: có báo cáo định kỳ và owner xử lý.
3. **P6-MT03**: Chuẩn hóa “single source of truth” cho các contract trọng yếu (auth, OCR/ADE, fallback matrix).  
   DoD: mỗi contract có đúng 1 canonical doc, tài liệu khác chỉ tham chiếu.

## 3) Kết luận ngắn

- Có các khoảng lệch tài liệu ở mức **Critical/High** quanh `auth full flow`, `DeepSeek fallback khi RAG empty`, `Self-Med permanent cabinet`, và `dashboard flow editor`.  
- `OCR/ADE from tgc-transhub` đã có nền nhưng còn rủi ro tái lập do tham chiếu tuyệt đối và thiếu contract canonical.  
- Web UX đa trang hiện chưa đạt độ chi tiết tương đương Flutter route map, cần chuẩn hóa để tránh vỡ luồng khi triển khai.

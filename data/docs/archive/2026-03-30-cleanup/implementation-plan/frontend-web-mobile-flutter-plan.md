# Kế Hoạch Giao Diện Web + Ứng Dụng Flutter

## 1. Mục tiêu

- Triển khai đồng bộ trải nghiệm người dùng cho 3 role (Normal/Researcher/Doctor).
- Hỗ trợ đầy đủ hai nhánh: CLARA Research và CLARA Self-Med.
- Bổ sung giao diện `System Control Tower Dashboard` cho quản trị vận hành toàn hệ thống.

## 2. Nguyên tắc kiến trúc frontend

- App người dùng: Flutter (iOS/Android), có thể tái sử dụng một phần cho web nếu phù hợp.
- Dashboard quản trị: web desktop-first (UI ưu tiên thông tin dày, realtime monitoring).
- Giao tiếp API thống nhất qua Rust gateway.
- Mọi trạng thái AI phải hiển thị rõ: citation, confidence, verification status, policy action.

## 3. Liên kết với LangChain/LangGraph

- UI cần hiển thị tiến trình graph execution (state transitions) cho các workflow dài.
- Với AI Council: hiển thị logs theo từng specialist agent + consensus/dissent.
- Với Self-Med: hiển thị trace cảnh báo DDI/allergy/escalation theo sự kiện.

## 4. Module màn hình bắt buộc

### 4.1 End-user surfaces
- Auth + chọn role.
- Research: query, progressive output 5-10-20, citation explorer.
- Self-Med: tủ thuốc, DDI check, reminder, family dashboard, expiry center.
- Doctor: AI Council, scribe review, escalation queue.

### 4.2 Admin dashboard surfaces (Control Tower)
- IAM/Tenant management.
- Policy/model/prompt release center.
- Source registry và connector health.
- Eval center + drift monitoring.
- Incident center + audit explorer.
- Billing/cost + feature flags.

## 5. Lộ trình triển khai giao diện

### P0-P1
- Scaffold Flutter app + web admin shell.
- Role-based navigation.
- Health widgets cơ bản trên dashboard.

### P2
- Research progressive UI hoàn chỉnh.
- Self-Med MVP UI (DDI/reminder/family dashboard).
- Dashboard nghiệp vụ: adherence, DDI trend, source freshness.

### P3
- Doctor workflow UI + AI Council logs explorer.
- Dashboard governance: model/prompt/policy registry.

### P4-P6
- Incident center, cost/billing, tenant controls, partner ecosystem boards.
- Hardening accessibility, performance, localization.

## 6. Chất lượng và kiểm thử

- Component tests theo role.
- E2E tests cho luồng critical (DDI, escalation, AI council, policy block).
- Contract tests FE <-> Rust API.
- Snapshot tests cho dashboard widgets và bảng số liệu.

## 7. KPI frontend

- Crash-free sessions >= 99.5%.
- Time-to-interactive đạt ngưỡng release.
- Tỷ lệ hoàn tất workflow theo role.
- Tỷ lệ hiển thị đúng trạng thái verification/policy >= 99%.

## 8. Rủi ro và phương án

| Rủi ro | Phương án |
|---|---|
| UI quá tải thông tin | tách rõ user dashboard và admin dashboard |
| Trễ stream logs | fallback polling + retry channel + local buffer |
| Sai khác hiển thị giữa web/app | shared design token + API contract snapshots |
| Dashboard nặng trên dữ liệu lớn | virtualized tables + server-side pagination |

## 9. Tiêu chí hoàn tất

1. End-user web/mobile Flutter chạy ổn định cho cả Research + Self-Med.
2. Control Tower Dashboard phục vụ được Product/Ops/Clinical/Security.
3. Tất cả trạng thái AI quan trọng đều truy vết được trên giao diện.

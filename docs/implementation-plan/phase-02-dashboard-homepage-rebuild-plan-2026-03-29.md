# Phase 02 Plan - Rebuild Dashboard + Homepage (2026-03-29)

## 1) Mục tiêu phase

- Rebuild đồng thời `homepage` (public funnel) và `dashboard` (authenticated workspace) theo cùng một design language, IA rõ ràng, và responsive nhất quán từ mobile đến ultrawide.
- Tối ưu 2 nhóm chỉ số: conversion đầu vào (homepage) và task completion/clarity trong vận hành (dashboard).
- Giảm nợ giao diện: gom về hệ component tái sử dụng, tách rõ layout shell, data module, và trạng thái loading/error/empty.

## 2) Scope

### 2.1 In scope

- IA mới cho homepage và dashboard.
- Thiết kế lại cấu trúc section, visual hierarchy, CTA hierarchy.
- Chuẩn hóa component architecture dùng chung giữa homepage và dashboard.
- Chuẩn hóa responsive rules theo dải: mobile -> tablet -> laptop -> desktop -> ultrawide.
- Chuẩn hóa acceptance criteria, KPI UX, và test checklist trước khi mở rộng phase tiếp theo.

### 2.2 Out of scope

- Không thay đổi business logic backend, contract API, hoặc role policy.
- Không redesign toàn bộ các module chuyên sâu ngoài dashboard/homepage (research, self-med detail views, admin deep pages).
- Không thay đổi brand naming/legal content ngoài phần copy cần cho IA mới.

## 3) Nguyên tắc thiết kế vận hành

- Mobile-first, progressive enhancement lên màn hình lớn.
- Một màn hình chỉ có một hành động chính (single primary CTA).
- Dashboard ưu tiên readability và scanability (đọc nhanh, quyết định nhanh).
- Homepage ưu tiên trust + proof + đường đi hành động rõ trong 10 giây đầu.
- Không kéo giãn text rail vô hạn trên ultrawide; tăng whitespace thay vì tăng độ dài dòng.

## 4) Information Architecture (IA)

## 4.1 Homepage IA (public)

1. `Global Header`
- Logo + nav tối giản.
- CTA chính luôn hiện: `Bắt đầu ngay`.

2. `Hero (Above the fold)`
- Value proposition 1 câu rõ kết quả.
- 2 CTA: chính (đăng ký/bắt đầu), phụ (xem demo/hướng dẫn).
- Trust strip ngắn: compliance, nguồn dữ liệu, reliability claim.

3. `Problem -> Outcome`
- 3 pain points chính theo ngôn ngữ người dùng.
- Mỗi pain point map 1 outcome định lượng.

4. `Capability Blocks`
- Nhóm năng lực chính: Research, Self-Med, Care/Monitoring.
- Mỗi block: mô tả ngắn + 3 lợi ích + CTA contextual.

5. `Proof & Credibility`
- Metrics card, testimonial/case snippet, source credibility.

6. `How It Works`
- Flow 3 bước: nhập nhu cầu -> phân tích -> hành động.

7. `FAQ + Objection Handling`
- Trả lời phản đối phổ biến: độ tin cậy, bảo mật, đối tượng dùng.

8. `Final CTA + Footer`
- Single dominant CTA.
- Footer pháp lý, contact, policy.

## 4.2 Dashboard IA (authenticated)

1. `App Shell`
- Topbar: context page + quick actions + account.
- Sidebar: điều hướng theo role, tối đa 6 mục cốt lõi.

2. `Overview Row`
- KPI snapshot cards (4-6 cards): trạng thái hệ thống/cá nhân theo role.

3. `Primary Workspace`
- Cột chính: tasks/insights/actionables theo ưu tiên.
- Cột phụ: notifications/recent events/recommendations.

4. `Operational Modules`
- Activity timeline.
- Alert panel (severity rõ ràng).
- Quick actions panel (đường tắt tác vụ thường dùng).

5. `Evidence/Health Strip`
- Nguồn dữ liệu, freshness, trạng thái đồng bộ.

6. `System States`
- Empty state có hướng dẫn hành động.
- Error state có khả năng retry/escalate.
- Loading state dạng skeleton theo khối nội dung.

## 5) Component Architecture

## 5.1 Layer kiến trúc

1. `Layout Layer`
- `PublicShell` (homepage).
- `DashboardShell` (sidebar/topbar/content rails).
- `SectionContainer` với width tokens thống nhất.

2. `Composition Layer`
- Homepage sections: `HeroSection`, `TrustStrip`, `CapabilityGrid`, `ProofSection`, `HowItWorks`, `FaqSection`, `FinalCtaSection`.
- Dashboard modules: `KpiCardGroup`, `TaskBoard`, `AlertCenter`, `TimelinePanel`, `QuickActions`, `HealthStatusStrip`.

3. `Primitive Layer`
- Buttons, chips, cards, badges, tabs, empty/error/skeleton components.
- Typography primitives và spacing tokens dùng chung.

4. `State Layer`
- Quy ước chung cho `loading/empty/error/success`.
- Chuẩn hóa hành vi retry và inline feedback.

## 5.2 Quy tắc tái sử dụng

- Shared primitives giữa homepage và dashboard >= 70% ở cấp UI cơ bản.
- Không hardcode màu/khoảng cách trong component feature; chỉ dùng token.
- Mọi module dashboard phải có đủ 4 state: loading, empty, error, data.
- CTA component có biến thể: primary, secondary, ghost; không tạo biến thể ad-hoc.

## 6) Responsive Rules (Mobile -> Ultrawide)

## 6.1 Breakpoint matrix

- `xs`: 0-639
- `sm`: 640-767
- `md`: 768-1023
- `lg`: 1024-1439
- `xl`: 1440-1919
- `2xl`: 1920-2559
- `3xl`: >=2560

## 6.2 Layout theo breakpoint

1. `xs-sm (mobile)`
- 1 cột.
- Sidebar/dashboard panel chuyển thành drawer/bottom sheet.
- KPI cards thành carousel hoặc grid 2 cột tùy ngữ cảnh.
- CTA full-width, touch target >= 44x44.

2. `md (tablet portrait/landscape nhỏ)`
- Homepage: 1-2 cột theo section.
- Dashboard: 12 cột mềm, ưu tiên cột chính; cột phụ collapse.
- Điều hướng giữ compact mode.

3. `lg (laptop)`
- Homepage: section có thể 2 cột ổn định.
- Dashboard: 2 rails (main + secondary) hoặc 3 rails nhẹ tùy module.
- Sidebar cố định dạng icon+label rút gọn.

4. `xl (desktop lớn)`
- Khóa container max-width để tránh dàn ngang quá rộng.
- Dashboard hiển thị đủ 3 vùng: nav rail + main rail + side insights.
- Main reading rail cap để giữ line length 60-72ch.

5. `2xl-3xl (ultrawide)`
- Không mở rộng text rail theo viewport vô hạn.
- Tăng outer gutters/whitespace; giữ độ rộng rail nội dung cốt lõi.
- Panel phụ có thể mở rộng nhẹ nhưng không lấn trọng tâm đọc.

## 6.3 Responsive quality gates

- Không xuất hiện horizontal scroll ngoài chủ đích ở các viewport chuẩn: `360, 390, 768, 1024, 1366, 1440, 1920, 2560`.
- Line length phần nội dung dài của homepage/dashboard: `P95 <= 72ch`.
- CLS khi đổi trạng thái/collapse panel: `<= 0.1`.

## 7) Kế hoạch triển khai theo micro-phase

## Phase 2.0 - Discovery & Baseline (0.5 sprint)

- Chốt baseline metrics hiện tại: conversion homepage, time-to-first-action dashboard.
- Audit IA hiện tại và map pain points theo funnel.
- Chốt danh sách component cần giữ/rework/tạo mới.

Deliverables:
- Baseline report + danh sách gap.
- Scope freeze cho phase 2.

## Phase 2.1 - IA Blueprint & Content Skeleton (0.5 sprint)

- Chốt sitemap nhỏ cho homepage và cấu trúc dashboard.
- Viết content skeleton (headline/subheadline/CTA copy slots).
- Chốt thứ tự ưu tiên section theo hành trình người dùng.

Deliverables:
- IA blueprint final.
- Wireframe fidelity thấp cho mobile + desktop.

## Phase 2.2 - Design Tokens & Shared Primitives (1 sprint)

- Chuẩn hóa tokens: spacing, typography, color semantic, elevation.
- Refactor primitives dùng chung (button/card/badge/chip/tabs/states).
- Thiết lập quy tắc state rendering chuẩn cho module.

Deliverables:
- Token contract v1.
- Shared component library đủ cho homepage + dashboard rebuild.

## Phase 2.3 - Homepage Rebuild (1 sprint)

- Build lại homepage theo IA mới và CTA hierarchy.
- Tối ưu trust/proof sections cho conversion.
- Hoàn thiện responsive và motion nhẹ cho section transitions.

Deliverables:
- Homepage production-candidate.
- Copy + CTA tracking hooks sẵn sàng đo lường.

## Phase 2.4 - Dashboard Rebuild (1 sprint)

- Build lại dashboard shell và overview modules.
- Chuẩn hóa KPI cards, alerts, timeline, quick actions.
- Hoàn thiện state handling loading/empty/error/data cho từng module.

Deliverables:
- Dashboard production-candidate.
- Role-based navigation và action hierarchy ổn định.

## Phase 2.5 - Responsive Hardening (0.5 sprint)

- Chạy full viewport matrix mobile -> ultrawide.
- Tinh chỉnh rail width, gutters, breakpoints edge-cases.
- Đóng các lỗi visual regression và layout shift.

Deliverables:
- Responsive pass report.
- Visual snapshots baseline mới.

## Phase 2.6 - QA Gate & Rollout Readiness (0.5 sprint)

- Chạy acceptance checklist + UX KPI verification.
- Chạy test checklist (functional, responsive, accessibility, performance).
- Chốt go/no-go và plan rollback.

Deliverables:
- QA sign-off.
- Rollout checklist + monitoring checklist sau release.

## 8) Acceptance Checklist

- [ ] Scope đúng 2 bề mặt: homepage + dashboard; không tràn qua module ngoài scope.
- [ ] IA mới được áp dụng đầy đủ và nhất quán với hành trình người dùng.
- [ ] Shared component architecture vận hành, không còn lặp UI primitives.
- [ ] Responsive pass toàn bộ viewport matrix đã định nghĩa.
- [ ] Dashboard module nào cũng có state loading/empty/error/data.
- [ ] Homepage có CTA chính rõ và xuất hiện tại các điểm chuyển đổi chính.
- [ ] Không phát sinh regression nghiêm trọng ở nav, auth entry points, route transitions.
- [ ] Theo dõi đo lường KPI UX hoạt động sau deploy.

## 9) KPI UX cho Phase 02

## 9.1 Homepage KPIs

- CTR CTA chính (hero): tăng >= 20% so với baseline trước phase.
- Bounce rate phiên đầu: giảm >= 15%.
- Time-to-first-meaningful-action (click CTA hoặc mở flow đăng ký): <= 15 giây median.

## 9.2 Dashboard KPIs

- Time-to-first-task-completion: giảm >= 25%.
- Task success rate các tác vụ chính: >= 90%.
- Navigation error rate (đi sai/thoát ra ngay): <= 8%.

## 9.3 Cross-surface UX KPIs

- SUS nội bộ (hoặc thang tương đương): >= 78/100.
- Accessibility checks pass (AA mức cơ bản): >= 95% tiêu chí tự động.
- Visual consistency score (design QA checklist): >= 90%.

## 10) Test Checklist

## 10.1 Functional

- [ ] Homepage: tất cả CTA điều hướng đúng mục tiêu.
- [ ] Dashboard: navigation theo role đúng thứ tự và quyền hiển thị.
- [ ] KPI cards, alerts, timeline render đúng dữ liệu và state.
- [ ] Empty/error/retry hoạt động đúng trên từng module.

## 10.2 Responsive

- [ ] Kiểm tra thủ công + snapshot tại các viewport: `360, 390, 768, 1024, 1366, 1440, 1920, 2560`.
- [ ] Không overflow ngang ngoài chủ đích.
- [ ] Sidebar/drawer/sheet chuyển trạng thái đúng khi đổi breakpoint.

## 10.3 Accessibility

- [ ] Contrast text và interactive elements đạt chuẩn AA.
- [ ] Keyboard navigation đi qua toàn bộ phần tử tương tác chính.
- [ ] Focus states rõ và không bị ẩn.
- [ ] Icon-only controls có label/aria-label phù hợp.

## 10.4 Performance UX

- [ ] LCP homepage trong ngưỡng mục tiêu web app nội bộ.
- [ ] CLS <= 0.1 ở homepage và dashboard.
- [ ] Tương tác chính có feedback trong <= 100ms cảm nhận.
- [ ] Skeleton/loading states không gây nhảy layout.

## 10.5 Regression & Release Gate

- [ ] Visual regression pass >= 95% snapshots chuẩn.
- [ ] Smoke test route chính pass 100%.
- [ ] Có rollback checklist và điểm giám sát sau rollout (KPI + error monitoring).

## 11) Definition of Done

- Homepage và dashboard hoàn tất rebuild theo IA + component architecture + responsive contract của Phase 02.
- Acceptance checklist pass đầy đủ.
- KPI UX sau rollout đạt hoặc có xu hướng đạt theo ngưỡng đã cam kết trong 1-2 chu kỳ đo đầu tiên.
- Test checklist hoàn tất và có bằng chứng kiểm thử đi kèm.

# Mục Lục Tài Liệu CLARA (Refactor 2026-03-24)

## 1. Định hướng chung

- CLARA gồm 2 nhánh sản phẩm:
  - `CLARA Research`: trợ lý nghiên cứu y khoa đa nguồn.
  - `CLARA Self-Med`: quản lý thuốc cá nhân và an toàn dùng thuốc tại gia đình.
- Nền tảng kỹ thuật thống nhất:
  - `multi-agent + multimodal RAG`
  - `intent router 2 lớp` (Role -> Intent)
  - web + app mobile `Flutter`
  - backend ưu tiên `Rust` (ML services dùng Python khi cần)

## 2. Cấu trúc tài liệu hiện tại

### 2.1 Architecture

- `docs/architecture/clara-platform-architecture.md`
- `docs/architecture/clara-runtime-and-routing.md`
- `docs/architecture/clara-diagrams.html`

### 2.2 Proposal

- `docs/proposal/clara-master-proposal.md`
- `docs/proposal/clara-research-proposal.md`
- `docs/proposal/clara-self-med-proposal.md`
- `docs/proposal/feature-planning-and-roadmap.md`

### 2.3 Research

- `docs/research/market-need-and-regulatory-research.md`
- `docs/research/multimodal-rag-and-data-connectors-research.md`
- `docs/research/medical-slm-and-safety-research.md`
- `docs/research/risk-deep-dive-and-mitigation.md`
- `docs/research/competitive-products-flow-benchmark.md`
- `docs/research/competitive-ai-health-platforms-2026-03-25.md`
- `docs/research/competitive-selfmed-and-pillbox-apps-2026-03-25.md`
- `docs/research/trusted-sources-and-api-access-plan.md`
- `docs/research/deepdive-competitive-intelligence-plan.md`
- `docs/research/competitive-landscape-deepdive-2026-03-25-v2.md`
- `docs/research/competitive-uiux-selfmed-chatbot-deepdive-2026-03-25.md`
- `docs/research/2026-03-29-clara-research-flow-deepdive.md`
- `docs/research/2026-03-29-competitive-chatflow-rag-ddi-webresearch.md`
- `docs/research/2026-03-29-dify-style-flow-visualization-deepdive.md`
- `docs/research/2026-03-29-kp3-landing-deepdive.md`

### 2.4 Implementation Plan

- `docs/implementation-plan/readme.md`
- `docs/implementation-plan/phase-00-to-06-master-plan.md`
- `docs/implementation-plan/workstream-clara-research.md`
- `docs/implementation-plan/workstream-clara-self-med.md`
- `docs/implementation-plan/frontend-web-mobile-flutter-plan.md`
- `docs/implementation-plan/frontend-web-ux-revamp-plan.md`
- `docs/implementation-plan/backend-rust-plan.md`
- `docs/implementation-plan/metrics-gates-and-operating-model.md`
- `docs/implementation-plan/system-control-tower-dashboard-plan.md`
- `docs/implementation-plan/web-sitemap-v2.md`
- `docs/implementation-plan/flutter-android-route-map.md`
- `docs/implementation-plan/web-mobile-information-architecture-v3.md`
- `docs/implementation-plan/p1-to-p6-microtasks-detailed-plan.md`
- `docs/implementation-plan/source-integration-execution-board.md`
- `docs/implementation-plan/docs-gap-audit-2026-03-25.md`
- `docs/implementation-plan/architecture-plan-alignment-audit-v3.md`
- `docs/implementation-plan/ship-plan-ddi-admin-frontend-rebuild-v1.md`
- `docs/implementation-plan/runtime-alignment-gap-report-2026-03-25-v2.md`
- `docs/implementation-plan/frontend-uiuxpromax-rebuild-execution-plan-v1.md`
- `docs/implementation-plan/phase-01-research-flow-hardening-and-kp3-landing-plan.md`
- `docs/implementation-plan/ultrawide-responsive-layout-deepdive-2026-03-29.md`
- `docs/implementation-plan/phase-01-kp3-inspired-landing-refactor-2026-03-29.md`

## 3. Thứ tự đọc khuyến nghị

1. `docs/proposal/clara-master-proposal.md`
2. `docs/architecture/clara-platform-architecture.md`
3. `docs/architecture/clara-runtime-and-routing.md`
4. `docs/research/multimodal-rag-and-data-connectors-research.md`
5. `docs/research/medical-slm-and-safety-research.md`
6. `docs/proposal/clara-self-med-proposal.md`
7. `docs/implementation-plan/readme.md`
8. `docs/implementation-plan/phase-00-to-06-master-plan.md`

## 4. Quy tắc bảo trì

Khi thay đổi kiến trúc/runtime hoặc roadmap, bắt buộc cập nhật đồng thời:
1. `docs/architecture/clara-platform-architecture.md`
2. `docs/architecture/clara-runtime-and-routing.md`
3. `docs/implementation-plan/phase-00-to-06-master-plan.md`
4. `docs/implementation-plan/metrics-gates-and-operating-model.md`
5. `docs/proposal/feature-planning-and-roadmap.md`

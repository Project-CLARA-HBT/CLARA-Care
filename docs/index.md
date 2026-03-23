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

### 2.4 Implementation Plan

- `docs/implementation-plan/readme.md`
- `docs/implementation-plan/phase-00-to-06-master-plan.md`
- `docs/implementation-plan/workstream-clara-research.md`
- `docs/implementation-plan/workstream-clara-self-med.md`
- `docs/implementation-plan/frontend-web-mobile-flutter-plan.md`
- `docs/implementation-plan/backend-rust-plan.md`
- `docs/implementation-plan/metrics-gates-and-operating-model.md`

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

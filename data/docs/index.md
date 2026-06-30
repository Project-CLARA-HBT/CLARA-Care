# CLARA-Care — Documentation Index

Cập nhật: 2026-05 · Bản đồ tài liệu hiện hành của monorepo (web + api + ml + mobile).

Tài liệu được chia hai cây:
- `data/docs/**` — tài liệu tường thuật (đề xuất, kiến trúc as-built, vận hành, nghiên cứu nền tảng). Không bị kiểm tra link tự động.
- `docs/**` — tài liệu kỹ thuật được CI kiểm tra link (`scripts/docs/check-docs-links.sh`): nghiên cứu deep-research, citations, hackathon, security.

Đặc tả tính năng (requirements/design/tasks) nằm ở `.kiro/specs/` — nguồn chân lý cho công việc đang triển khai (`clara-research`, `personal-health-record`, `clara-scribe-enterprise`, `product-polish-analytics`, `rag-knowledge-pipeline`).

## 1) Bộ tài liệu chính (đang dùng)

Đề xuất & tổng quan
- `proposal/clara-full-proposal-2026-03-29.md` — đề xuất đầy đủ.
- `proposal/clara-care-hue19-revised-2026-03-31.md` — bản chỉnh sửa.
- `proposal/clara-competition-judge-aligned-2026-03-31.md`
- `proposal/gdgoc-hackathon-2026-clara-plan-v2.md`
- `proposal/bao-cao-thuyet-minh-200-trang.md` — báo cáo kỹ thuật/thuyết minh đầy đủ (tiếng Việt).

Kiến trúc & as-built
- `architecture/clara-runtime-and-routing.md` — runtime + định tuyến.
- `architecture/as-built-context.md` — ngữ cảnh as-built (snapshot mã nguồn).

Kỹ thuật (minh chứng & demo)
- `engineering/technical-evidence.md` — minh chứng kỹ thuật các luồng chính từ source code.
- `engineering/presentation-script.md` — kịch bản thuyết trình.

Vận hành (DevOps/Ops)
- `devops/release-process.md`, `devops/cd-pipeline.md`, `devops/branch-protection.md`
- `ops/disk-retention-policy.md`, `ops/source-hub-crawl.md`, `ops/README.md`

Nghiên cứu nền tảng
- `research/market-need-and-regulatory-research.md`
- `research/risk-deep-dive-and-mitigation.md`
- `research/medical-safety-corpus-pack.md`
- `research/data/` — manifest/nguồn corpus giữ lại cho demo.

Kế hoạch triển khai (lịch sử Vòng 2)
- `implementation-plan/readme.md`
- `implementation-plan/round2-14-day-execution-checklist-2026-03-30.md`
- `implementation-plan/day1-unified-contract-2026-03-30.md`

## 2) Cây `docs/` (CI kiểm tra link)

Nghiên cứu deep-research
- `docs/research/research-flow-architecture-refactor-2026-04-11.md`
- `docs/research/deep-research-naturalness-refactor-2026-04-11.md`
- `docs/research/latest-science-map-2026-04-04.md`
- `docs/research/citations/` — registry citation (PMID/DOI), dùng bởi tính năng CLARA Research.

Hackathon (báo cáo/benchmark/gate điểm-thời-gian)
- `docs/hackathon/` — gồm `data-manifest.json`, `kpi-snapshot.md` (artifact CI), benchmark deep-beta, gate reports.

An toàn/bảo mật
- `docs/security/security-remediation-2026-04-03.md`

## 3) Quy tắc cập nhật

- Tài liệu đặc tả tính năng: cập nhật trong `.kiro/specs/<feature>/` (requirements → design → tasks).
- Thay đổi kỹ thuật lớn: cập nhật `architecture/clara-runtime-and-routing.md` và `architecture/as-built-context.md`.
- Tài liệu trong `docs/**` phải dùng link tương đối hợp lệ (CI sẽ fail nếu link gãy hoặc dùng đường dẫn tuyệt đối).
- Không tạo tài liệu trùng lặp; gộp vào bộ chính khi có thể.

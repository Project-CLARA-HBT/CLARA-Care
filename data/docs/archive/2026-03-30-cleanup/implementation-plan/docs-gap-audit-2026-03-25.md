# Báo Cáo Khoảng Trống Tài Liệu - 2026-03-25

## 1) Phạm vi và cách audit

- Phạm vi: toàn bộ `docs/` (29 file `.md` + 1 file `.html`).
- Tiêu chí audit:
1. Liên kết nội bộ.
2. Trùng lặp nội dung.
3. Thiếu file tham chiếu.
- Cách làm:
1. Quét link Markdown nội bộ (`[]()`): kết quả `0`.
2. Quét tham chiếu dạng path `docs/...`: ghi nhận `43` tham chiếu.
3. Đối chiếu path tham chiếu với file thực tế trong repo.
4. So khớp cấu trúc heading/section để tìm cụm nội dung trùng lặp.

## 2) Kết quả theo 3 tiêu chí

### 2.1 Liên kết nội bộ

- Chưa dùng link Markdown nội bộ (`[]()`), nên điều hướng giữa tài liệu chưa click được.
- Tham chiếu hiện chủ yếu ở dạng text/backtick path.
- Dẫn chứng:
1. Không có dòng nào chứa `](` trong toàn bộ `docs/*.md`.
2. `docs/index.md` chỉ liệt kê path dạng text tại các dòng `18-51`, `55-62`, `67-71`.
3. `docs/implementation-plan/readme.md` dùng tên file tương đối tại dòng `24-36`, không có path đầy đủ và không phải hyperlink.

### 2.2 Trùng lặp nội dung

- Cụm nội dung "LangChain/LangGraph suitability + Ops Dashboard/Governance + checklist dashboard an toàn" lặp lại ở nhiều file research:
1. `docs/research/market-need-and-regulatory-research.md:118-163`
2. `docs/research/medical-slm-and-safety-research.md:103-157`
3. `docs/research/multimodal-rag-and-data-connectors-research.md:148-210`
4. `docs/research/risk-deep-dive-and-mitigation.md:107-136`
- Cặp proposal/workstream bị chồng lặp mạnh ở phần quyết định kỹ thuật, roadmap, KPI:
1. `docs/proposal/clara-self-med-proposal.md` vs `docs/implementation-plan/workstream-clara-self-med.md`
2. `docs/proposal/clara-research-proposal.md` vs `docs/implementation-plan/workstream-clara-research.md`
- Roadmap P0->P6 xuất hiện ở nhiều lớp tài liệu, tăng rủi ro lệch version:
1. `docs/proposal/feature-planning-and-roadmap.md:19-29`
2. `docs/implementation-plan/phase-00-to-06-master-plan.md` (toàn file)
3. `docs/implementation-plan/p1-to-p6-microtasks-detailed-plan.md` (P1->P6 chi tiết)

### 2.3 Thiếu file tham chiếu

- Có tham chiếu tới file không nằm trong repo CLARA:
1. `docs/technical/ocr-integration.md`
2. `docs/technical/agentic-document-extraction.md`
3. `docs/technical/ade-refactor-plan.md`
4. `docs/technical/ocr-layout-tuning.md`
- Vị trí tham chiếu: `docs/implementation-plan/flutter-android-route-map.md:171-176` (đang dùng absolute path `/Users/nguyennt/...`).
- Có file "mồ côi" (không được tài liệu nào khác tham chiếu qua `docs/...`):
1. `docs/implementation-plan/source-integration-execution-board.md`
2. `docs/research/deepdive-competitive-intelligence-plan.md`
3. `docs/implementation-plan/content-glossary-vi.md`
4. `docs/implementation-plan/ui-ux-audit-report.md`
- Hub tài liệu chưa phản ánh đầy đủ file hiện có:
1. `docs/index.md:29-36` chưa có `deepdive-competitive-intelligence-plan.md`.
2. `docs/index.md:38-51` chưa có `source-integration-execution-board.md`, `content-glossary-vi.md`, `ui-ux-audit-report.md`.
3. `docs/implementation-plan/readme.md:24-36` chưa có `source-integration-execution-board.md`.

## 3) Danh sách gap theo mức độ

| ID | Mức độ | Nhóm tiêu chí | Gap | Tác động |
|---|---|---|---|---|
| G1 | High | Thiếu file tham chiếu | Tham chiếu tới 4 file `docs/technical/*.md` không tồn tại trong repo hiện tại; lại dùng absolute path máy cá nhân. | Gãy trace tài liệu, không tái lập được môi trường, người mới không truy được nguồn kỹ thuật nền. |
| G2 | High | Trùng lặp nội dung | 4 file research lặp cụm governance/suitability/checklist gần như cùng cấu trúc. | Rủi ro lệch policy an toàn y khoa khi chỉ sửa 1 nơi. |
| G3 | Medium | Liên kết nội bộ | 0 hyperlink nội bộ dạng Markdown, phần lớn chỉ là text path/backtick. | Điều hướng chậm, review chéo dễ sót. |
| G4 | Medium | Thiếu file tham chiếu | Hub docs (`index.md`, `implementation-plan/readme.md`) chưa bao phủ hết file thực tế. | File quan trọng dễ bị "ẩn", khó đưa vào quy trình đọc/bảo trì chuẩn. |
| G5 | Medium | Trùng lặp nội dung | Proposal và workstream trùng mục tiêu/roadmap/KPI ở 2 nhánh Research và Self-Med. | Tăng chi phí bảo trì, dễ mâu thuẫn nội dung khi update theo phase. |
| G6 | Low | Liên kết nội bộ | Chuẩn tham chiếu chưa thống nhất (absolute path, `docs/...`, tên file tương đối). | Làm giảm tính nhất quán tài liệu và khó tự động kiểm tra. |

## 4) Checklist khắc phục cụ thể (ai cũng làm được)

### P0 - Sửa ngay (High)

- [ ] B1. Xử lý toàn bộ tham chiếu tuyệt đối `/Users/...` trong `docs/implementation-plan/flutter-android-route-map.md`.
1. Mở file và tìm tại dòng `171-176`.
2. Chọn 1 trong 2 hướng:
3. Hướng A (ưu tiên): đưa tài liệu kỹ thuật cần thiết vào repo CLARA dưới `docs/technical/`.
4. Hướng B: nếu chưa đưa vào repo, đổi thành link repo ngoài có commit/tag cố định và ghi rõ "external dependency".
5. Chạy kiểm tra: `rg -n '/Users/|docs/technical/.*\\.md' docs -g '*.md'`.

- [ ] B2. Chốt "single source of truth" cho cụm governance/suitability/checklist trong nhóm research.
1. Chọn 1 file canonical (khuyến nghị: `docs/research/risk-deep-dive-and-mitigation.md` hoặc file mới riêng cho governance).
2. 3 file còn lại giữ tóm tắt ngắn + link sang canonical.
3. Sau khi chuẩn hóa, đảm bảo chỉ còn 1 nơi chứa checklist chi tiết.

### P1 - Chuẩn hóa điều hướng (Medium)

- [ ] B3. Chuyển danh sách path quan trọng thành hyperlink Markdown thật sự.
1. Ưu tiên sửa `docs/index.md`.
2. Tiếp theo sửa `docs/implementation-plan/readme.md`.
3. Quy ước dùng link tương đối (ví dụ `./proposal/clara-master-proposal.md` hoặc `../research/...`).

- [ ] B4. Bổ sung file còn thiếu vào hub docs.
1. Thêm vào `docs/index.md`:
2. `docs/research/deepdive-competitive-intelligence-plan.md`
3. `docs/implementation-plan/source-integration-execution-board.md`
4. `docs/implementation-plan/content-glossary-vi.md`
5. `docs/implementation-plan/ui-ux-audit-report.md`
6. Thêm `source-integration-execution-board.md` vào danh sách file chuẩn của `docs/implementation-plan/readme.md`.

- [ ] B5. Giảm chồng lặp proposal vs workstream.
1. Proposal giữ "why/what" (bối cảnh, giá trị, quyết định cấp sản phẩm).
2. Workstream giữ "how" (deliverables kỹ thuật, KPI triển khai, gate).
3. Ở mỗi file, thay đoạn trùng dài bằng link sang file nguồn chuẩn.

### P2 - Chống tái phát (Low)

- [ ] B6. Chuẩn tham chiếu thống nhất.
1. Không dùng absolute path máy cá nhân trong docs.
2. Dùng một kiểu duy nhất cho internal reference: hyperlink Markdown tương đối.
3. Tên file trong cùng thư mục vẫn nên ghi kèm path rõ để tránh mơ hồ.

- [ ] B7. Thêm kiểm tra tự động trong CI cho docs.
1. Check link nội bộ hỏng.
2. Check cấm `/Users/` trong `docs/*.md`.
3. Cảnh báo khi phát hiện file mới trong `docs/` nhưng chưa xuất hiện trong `docs/index.md`.

## 5) Đề xuất thứ tự thực thi

1. Hoàn thành B1, B2 trước (trong 1 ngày).
2. Hoàn thành B3, B4, B5 (1-2 ngày tiếp theo).
3. B6, B7 triển khai song song khi đóng sprint tài liệu.

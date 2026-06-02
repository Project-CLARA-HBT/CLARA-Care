# Tài Liệu CLARA (Bản Gọn)

Ngày dọn tài liệu: 30/03/2026.

Mục tiêu của bản gọn:
- Giữ bộ tài liệu cần thiết để triển khai và thi Vòng 2.
- Giảm phân mảnh, dễ đọc và dễ điều phối team.
- Không xóa tài liệu cũ, chỉ chuyển vào khu lưu trữ.

## 1) Bộ tài liệu chính (đang dùng)

1. Proposal chính:
- `docs/proposal/clara-full-proposal-2026-03-29.md`

2. Kiến trúc runtime:
- `docs/architecture/clara-runtime-and-routing.md`

3. Kế hoạch thực thi Vòng 2:
- `docs/implementation-plan/readme.md`
- `docs/implementation-plan/round2-14-day-execution-checklist-2026-03-30.md`

4. Nghiên cứu trọng yếu:
- `docs/research/market-need-and-regulatory-research.md`
- `docs/research/risk-deep-dive-and-mitigation.md`
- `docs/research/medical-safety-corpus-pack.md`

5. Dữ liệu research giữ lại cho demo:
- `docs/research/data/vn-medical-acquired-manifest-2026-03-29.jsonl`
- `docs/research/data/vn-medical-acquired-report-2026-03-29.json`
- `docs/research/data/vn-medical-pdf-sources-phase1-part1-2026-03-29.csv`
- `docs/research/data/medical-safety-corpus-sources-2026-03-31.csv`
- `docs/research/data/medical-safety-pubmed-queries-2026-03-31.csv`

6. DevOps vận hành:
- `docs/devops/release-process.md`
- `docs/devops/cd-pipeline.md`
- `docs/devops/branch-protection.md`

## 2) Tài liệu cũ đã lưu trữ (archive)

- Toàn bộ tài liệu không thuộc bộ chính đã được chuyển vào:
- `docs/archive/2026-03-30-cleanup/`

Xem chi tiết quy ước lưu trữ tại:
- `docs/archive/README.md`

## 3) Thứ tự đọc đề xuất cho team

1. `docs/proposal/clara-full-proposal-2026-03-29.md`
2. `docs/architecture/clara-runtime-and-routing.md`
3. `docs/implementation-plan/readme.md`
4. `docs/implementation-plan/round2-14-day-execution-checklist-2026-03-30.md`
5. `docs/research/market-need-and-regulatory-research.md`
6. `docs/research/risk-deep-dive-and-mitigation.md`

## 4) Quy tắc cập nhật từ nay

- Không tạo thêm tài liệu mới nếu nội dung có thể gộp vào bộ chính.
- Mỗi thay đổi lớn chỉ cập nhật tối đa 3 nơi:
1. Proposal chính.
2. Checklist triển khai 14 ngày.
3. Runtime/architecture (nếu có đổi kỹ thuật).
- Tài liệu exploratory hoặc deep-dive mới phải để trong `docs/archive/` trừ khi được promote lên bộ chính.

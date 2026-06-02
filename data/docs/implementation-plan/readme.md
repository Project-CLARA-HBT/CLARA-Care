# Kế Hoạch Triển Khai (Bản Gọn cho Vòng 2)

Ngày cập nhật: 30/03/2026.

## 1) Tài liệu triển khai chính

- `docs/implementation-plan/round2-14-day-execution-checklist-2026-03-30.md` (timeline + execution tracker)
- `docs/implementation-plan/day1-unified-contract-2026-03-30.md` (contract canonical API/ML/Web)

Quy ước nguồn sự thật:
- Checklist là tài liệu điều phối tiến độ.
- Day1 Unified Contract là tài liệu chuẩn schema/field.
- Nếu có mâu thuẫn field/schema, ưu tiên Day1 Unified Contract và cập nhật lại checklist trong ngày.

## 2) Cách sử dụng

1. Mỗi sáng mở checklist 14 ngày và chốt mục tiêu trong ngày.
2. Mỗi tối cập nhật trạng thái:
- Đã xong
- Đang làm
- Blocker
3. Mọi việc phát sinh ngoài scope Vòng 2 phải đưa vào backlog, không chen vào checklist chính.

## 3) KPI bắt buộc trước demo

- DDI Precision tổng >= 0.92.
- DDI Precision High/Critical >= 0.95.
- Critical miss = 0.
- Fallback Success >= 0.98.
- Refusal Compliance unsafe >= 0.98.
- Refusal Compliance critical unsafe = 1.00.

## 4) Quy tắc vận hành

- Không mở thêm tài liệu kế hoạch mới nếu chưa thật sự cần; ưu tiên cập nhật 2 tài liệu canonical ở trên.
- Mọi thay đổi quan trọng phải phản ánh lại checklist 14 ngày trong ngày đó.
- Khi cần tra cứu tài liệu cũ, vào:
- `docs/archive/2026-03-30-cleanup/`

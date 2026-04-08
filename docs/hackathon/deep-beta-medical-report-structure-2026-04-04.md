# Deep Beta Medical Report Structure (Round 2)

## Mục tiêu
- Chuẩn hóa output `deep_beta` theo dạng báo cáo y khoa dài, có thể đọc như một bản clinical brief 5-10 trang.
- Giữ ranh giới pháp lý: không chẩn đoán, không kê đơn, không chỉ định liều.
- Tăng khả năng kiểm chứng: claim-level verification + phản biện bằng chứng đối nghịch.

## Khung chuẩn áp dụng
- Dựa trên tinh thần IMRaD (Introduction, Methods, Results, Discussion) và guideline reporting trong y văn.
- Adapt cho CLARA Research để phù hợp truy xuất evidence thời gian thực:
  1. `## Kết luận nhanh`
  2. `## Tóm tắt điều hành`
  3. `## Câu hỏi nghiên cứu (PICO)`
  4. `## Phương pháp truy xuất & tiêu chí chọn lọc`
  5. `## Hồ sơ bằng chứng & chất lượng nguồn`
  6. `## Tổng hợp phát hiện chính`
  7. `## Phản biện bằng chứng đối nghịch`
  8. `## Ứng dụng lâm sàng theo nhóm bệnh nhân`
  9. `## Ma trận quyết định an toàn`
  10. `## Kế hoạch theo dõi sau tư vấn`
  11. `## Giới hạn, sai số và rủi ro pháp lý`
  12. `## Nguồn tham chiếu`

## Quy ước chiều dài
- Target mặc định: khoảng 5-10 trang (ước tính theo words/page).
- Nếu output vòng đầu chưa đạt độ sâu, hệ thống chạy thêm expansion rounds để nối phần phân tích.

## Quy ước hiển thị
- Markdown GFM chuẩn.
- Bắt buộc có:
  - ít nhất 1 bảng tổng hợp evidence,
  - ít nhất 1 `mermaid` decision-flow,
  - ít nhất 1 `chart-spec` block cho tín hiệu định lượng.
- Không chèn HTML trong block `mermaid`.

## Safety gate
- Chặn mọi nội dung vượt quyền chuyên môn (diagnosis/prescription/dosage).
- Bảo toàn cảnh báo uncertainty khi evidence yếu hoặc mâu thuẫn.
- Nếu thiếu bằng chứng: ưu tiên trả khuyến nghị an toàn + escalte tham vấn bác sĩ.


# Glossary Ngôn Ngữ Giao Diện CLARA (Tiếng Việt)

Phiên bản: 1.0  
Ngày: 2026-03-24

## 1. Nguyên tắc

1. Dùng tiếng Việt làm ngôn ngữ mặc định.
2. Thuật ngữ chuyên môn giữ nguyên khi cần nhưng có diễn giải ngắn.
3. Mỗi khái niệm chỉ dùng một cách gọi chính trên toàn hệ thống.
4. Cảnh báo phải theo 3 cấp: `Thông tin`, `Cảnh báo`, `Khẩn cấp`.

## 2. Mapping thuật ngữ UI

| Thuật ngữ cũ | Thuật ngữ chuẩn mới |
|---|---|
| Dashboard | Bảng điều khiển |
| Research Workspace | Không gian hỏi đáp nghiên cứu |
| CareGuard | Kiểm tra an toàn thuốc |
| Medical Scribe | Trợ lý ghi chép y khoa |
| AI Council | Hội chẩn AI |
| Risk tier | Mức độ rủi ro |
| Modules | Tính năng |
| Workflow Steps | Các bước phân tích |
| Refresh | Làm mới |
| Open source | Mở nguồn tham chiếu |
| Dependency Status | Trạng thái phụ thuộc hệ thống |
| Partner Health | Tình trạng đối tác |
| Data Trust Score | Điểm tin cậy dữ liệu |

## 3. Mẫu thông điệp chuẩn

## 3.1 Loading

- `Đang phân tích câu hỏi...`
- `Đang tải dữ liệu hệ thống...`

## 3.2 Empty state

- `Chưa có dữ liệu. Hãy bắt đầu bằng câu hỏi đầu tiên.`

## 3.3 Error state

- `Không thể xử lý yêu cầu lúc này. Vui lòng thử lại sau ít phút.`
- `Bạn không đủ quyền truy cập tính năng này.`

## 3.4 Success state

- `Đã cập nhật thành công.`
- `Đã tạo báo cáo.`

## 4. Quy tắc label nút

1. Dùng động từ rõ ràng: `Gửi câu hỏi`, `Làm mới`, `Xem chi tiết`, `Bắt đầu`.
2. Không dùng label mơ hồ: `OK`, `Go`, `Submit`.
3. Tránh quá 2 nút chính trong cùng một vùng.

## 5. Quy trình cập nhật copy

1. Mọi chuỗi mới phải đi qua glossary check.
2. Review nhanh bởi Product + Clinical reviewer cho copy có ngữ cảnh y tế.
3. Tự động lint chuỗi cấm (Anh-Việt trộn sai chuẩn) ở CI.

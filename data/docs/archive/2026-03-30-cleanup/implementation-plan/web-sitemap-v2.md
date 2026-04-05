# Web Sitemap V2 (Onboarding-First)

Phiên bản: 1.0  
Ngày: 2026-03-24

## 1. Public routes

1. `/` - Landing page
2. `/huong-dan` - Hướng dẫn sử dụng
3. `/login` - Đăng nhập
4. `/register` - Đăng ký
5. `/role-select` - Chọn vai trò

## 2. Authenticated routes

1. `/dashboard` - Bảng điều khiển
2. `/research` - Không gian hỏi đáp nghiên cứu
3. `/careguard` - Kiểm tra an toàn thuốc
4. `/scribe` - Trợ lý ghi chép y khoa
5. `/council` - Hội chẩn AI
6. `/dashboard/ecosystem` - Trung tâm hệ sinh thái (doctor)

## 3. Luồng onboarding chuẩn

1. Người dùng vào `/`.
2. Người dùng chọn `Bắt đầu` hoặc `Xem hướng dẫn`.
3. Người dùng đăng nhập (`/login`).
4. Người dùng vào `/dashboard` và chạy checklist 3 bước.
5. Người dùng đặt câu hỏi đầu tiên tại `/research` hoặc `/careguard`.

## 4. Luồng tác vụ chính theo role

## 4.1 Normal
- Dashboard -> CareGuard -> Research (khi cần giải thích thêm).

## 4.2 Researcher
- Dashboard -> Research -> Export/đọc citation.

## 4.3 Doctor
- Dashboard -> Council/Scribe -> Ecosystem (khi cần theo dõi hệ thống).

## 5. Quy tắc navigation

1. Menu chính ưu tiên 5 mục: `Trang chủ`, `Hỏi đáp`, `Self-Med`, `Bảng điều khiển`, `Hướng dẫn`.
2. Tính năng nâng cao đặt trong dashboard và theo role.
3. Không hiển thị route không có quyền để tránh dead-end.

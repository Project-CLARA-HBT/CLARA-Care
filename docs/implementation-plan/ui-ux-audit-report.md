# Báo Cáo Audit UI/UX Web CLARA (UX-P0)

Phiên bản: 1.0  
Ngày: 2026-03-24

## 1. Phạm vi audit

- Public pages: `/`, `/login`, `/register`.
- Core app pages: `/dashboard`, `/research`, `/careguard`, `/scribe`, `/council`, `/dashboard/ecosystem`.
- Shared shell/navigation: `AppShell`, `SidebarNav`, `PageShell`.
- UI copy và ngôn ngữ hiển thị.

## 2. Persona mục tiêu

1. Người mới dùng lần đầu (không có nền kỹ thuật/y khoa).
2. Người nghiên cứu cần hỏi đáp sâu có citation.
3. Bác sĩ cần thao tác nhanh, chính xác, ít nhiễu.

## 3. Kết quả chính

## 3.1 Onboarding

- Vấn đề: trang chủ quá ngắn, chưa giải thích rõ 2 nhánh sản phẩm (`Research`, `Self-Med`).
- Tác động: người mới khó hiểu nên bắt đầu ở đâu.
- Mức độ: Cao.

## 3.2 Hướng dẫn sử dụng

- Vấn đề: chưa có trang hướng dẫn theo vai trò và theo tác vụ.
- Tác động: người dùng mò bằng thử-sai, tăng tỉ lệ bỏ cuộc sớm.
- Mức độ: Cao.

## 3.3 Chat experience

- Vấn đề: bố cục chat chưa theo hướng question-first, citation và steps chưa có panel thống nhất.
- Tác động: khó đọc và khó tiếp tục hỏi sâu.
- Mức độ: Cao.

## 3.4 Ngôn ngữ giao diện

- Vấn đề: trộn Anh-Việt ở label và status (`Dashboard`, `Refresh`, `Risk tier`, `Modules`).
- Tác động: thiếu nhất quán, giảm cảm giác sản phẩm hoàn chỉnh.
- Mức độ: Trung bình-Cao.

## 3.5 Điều hướng

- Vấn đề: menu theo role nhưng chưa theo hành trình người dùng mới.
- Tác động: người mới khó xác định tác vụ chính trong 1-2 phút đầu.
- Mức độ: Trung bình.

## 4. Quick wins ưu tiên

1. Làm mới landing page với CTA rõ + use-case theo role.
2. Thêm trang `/huong-dan` với quick start + FAQ theo tác vụ.
3. Chuẩn hoá copy tiếng Việt các trang chính.
4. Refactor research page theo bố cục chatbot gọn, giảm nút.
5. Làm rõ trạng thái cảnh báo và thông điệp lỗi.

## 5. Heuristic score (0-5)

- Learnability: 2.2
- Efficiency: 2.8
- Clarity: 2.4
- Consistency: 2.3
- Error prevention: 2.5
- Visual hierarchy: 2.6

## 6. KPI baseline cần đo lại sau cải tiến

1. Tỷ lệ hoàn tất onboarding: từ landing -> login -> câu hỏi đầu tiên.
2. Time-to-first-meaningful-answer.
3. Tỷ lệ người dùng quay lại sau 7 ngày.
4. Tỷ lệ mở trang hướng dẫn trước khi hỏi support.

## 7. Kết luận

- Cần ưu tiên rollout UX theo luồng: `Landing + Hướng dẫn -> Chat chuẩn -> Copy chuẩn hoá -> Accessibility`.
- Không tăng số nút bấm chính; ưu tiên hiển thị tóm tắt trước, chi tiết mở rộng sau.

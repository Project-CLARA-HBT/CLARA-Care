# Kế Hoạch Cải Thiện UI/UX Web CLARA Cho Người Mới

Phiên bản: 1.0  
Ngày cập nhật: 2026-03-24

## 1. Mục tiêu

- Thiết kế lại trải nghiệm web theo hướng dễ dùng cho người mới, giảm bỡ ngỡ ở lần truy cập đầu.
- Bổ sung đầy đủ `landing page` giới thiệu sản phẩm và `hướng dẫn sử dụng` theo luồng thực tế.
- Chuẩn hoá trải nghiệm chatbot chuyên sâu theo phong cách gọn, tập trung vào câu hỏi/câu trả lời (gần kiểu Perplexity), tránh dư nút.
- Chuẩn hoá ngôn ngữ hiển thị trên toàn bộ trang theo tiếng Việt rõ nghĩa, nhất quán, không trộn thuật ngữ khó hiểu.

## 2. Vấn đề hiện tại (đã rà soát)

1. Trang chủ (`/`) còn quá tối giản, thiếu giới thiệu giá trị sản phẩm, thiếu CTA theo vai trò.
2. Chưa có trang hướng dẫn người dùng mới (`how-to`, quick start, FAQ theo tác vụ).
3. Nhiều màn hình dùng thuật ngữ tiếng Anh xen kẽ tiếng Việt (`Tier`, `Risk tier`, `Modules`, `Refresh`...), gây nhiễu.
4. Trải nghiệm chat chưa thống nhất giữa các module; chưa có hệ thống khung hiển thị phản hồi chuẩn cho người mới.
5. Điều hướng còn thiên về danh sách tính năng, chưa theo hành trình người dùng.
6. Một số màn hình có nhiều thông tin kỹ thuật ngay lần đầu mở, dễ gây quá tải.

## 3. Nguyên tắc UX mục tiêu

1. `Question-first`: giao diện ưu tiên ô nhập câu hỏi và ngữ cảnh câu hỏi.
2. `One primary action`: mỗi khung chỉ 1 hành động chính + tối đa 1 hành động phụ.
3. `Progressive disclosure`: mặc định hiển thị bản tóm tắt; chi tiết mở rộng khi người dùng yêu cầu.
4. `Role clarity`: luôn hiển thị rõ vai trò hiện tại và quyền truy cập liên quan.
5. `Evidence transparency`: câu trả lời AI luôn có mức tin cậy/citation khi có.
6. `Vietnamese-first`: tiếng Việt chuẩn, thuật ngữ y khoa có chú giải ngắn.
7. `Calm interface`: giảm màu cảnh báo trừ khi có nguy cơ thật (DDI, emergency, critical alerts).

## 4. Information Architecture (IA) đề xuất

## 4.1 Public (chưa đăng nhập)

- `/` -> Landing page
- `/gioi-thieu` -> Giới thiệu CLARA (có thể gộp trong landing ở giai đoạn đầu)
- `/huong-dan` -> Hướng dẫn sử dụng theo vai trò
- `/dang-nhap` (alias nội bộ giữ `/login`)
- `/dang-ky` (alias nội bộ giữ `/register`)

## 4.2 Authenticated (đã đăng nhập)

- `/dashboard` -> Bảng điều khiển cá nhân theo vai trò
- `/research` -> Không gian hỏi đáp nghiên cứu
- `/careguard` -> Self-Med: kiểm tra DDI/rủi ro
- `/scribe` -> Medical Scribe
- `/council` -> AI Council
- `/dashboard/ecosystem` -> Ecosystem center (doctor)

## 4.3 Quy tắc điều hướng

- Top-level nav chỉ giữ 5 mục cốt lõi: `Trang chủ`, `Hỏi đáp`, `Self-Med`, `Bảng điều khiển`, `Hướng dẫn`.
- Các module nâng cao (Scribe/Council/Ecosystem) đặt trong `Bảng điều khiển` theo role.
- Không hiển thị quá 2 CTA nổi bật trên một vùng giao diện.

## 5. Thiết kế chi tiết theo màn hình

## 5.1 Landing page (`/`)

### Mục tiêu
- Người mới hiểu CLARA làm gì trong 20-30 giây.
- Có đường vào nhanh theo vai trò sử dụng.

### Bố cục đề xuất
1. `Hero`: mô tả ngắn + 1 ô nhập thử câu hỏi + 2 nút (`Bắt đầu`, `Xem hướng dẫn`).
2. `Use-case blocks` (3 thẻ):
   - Người dùng cá nhân (Self-Med)
   - Nhà nghiên cứu (Research)
   - Bác sĩ (Council + Scribe)
3. `How it works` 3 bước: nhập câu hỏi -> CLARA phân tích -> nhận kết quả có dẫn chứng.
4. `Safety & trust`: badge nguồn dữ liệu (BYT/WHO/PubMed/openFDA).
5. `Footer`: liên kết chính sách dữ liệu, liên hệ hỗ trợ.

### Yêu cầu UX
- Tránh carousel, tránh nhiều nút ngang hàng.
- Trên mobile: CTA chính luôn nằm trong viewport đầu tiên.

## 5.2 Trang hướng dẫn (`/huong-dan`)

### Nội dung bắt buộc
1. Quick start cho từng role (`Normal`, `Researcher`, `Doctor`).
2. 5 kịch bản thường gặp (uống thuốc, kiểm tra DDI, tóm tắt hồ sơ, hỏi guideline, hội chẩn).
3. Mục `Không nên dùng CLARA cho` (cấp cứu tối khẩn, thay thế chẩn đoán trực tiếp...).
4. FAQ + mô tả ý nghĩa các trạng thái cảnh báo.

### UX pattern
- Accordion theo chủ đề.
- Có thanh tìm kiếm trong trang hướng dẫn.
- CTA nổi: `Mở không gian hỏi đáp`.

## 5.3 Chatbot workspace (style Perplexity)

### Khung giao diện mục tiêu
1. Header gọn: tên workspace + role badge + model/status.
2. Trung tâm: luồng hội thoại dạng thread.
3. Dưới cùng: hộp nhập lớn, hỗ trợ enter/shift+enter.
4. Bên phải (hoặc panel mở rộng): `Nguồn tham chiếu`, `Bước phân tích`, `Nhật ký xác minh`.

### Thành phần phản hồi chuẩn
- `Tóm tắt trả lời` (hiển thị trước).
- `Mức độ tin cậy` (cao/trung bình/thấp).
- `Nguồn tham khảo` (nếu có).
- `Khuyến nghị tiếp theo` (tối đa 3 mục).

### Hạn chế nút bấm
- Một câu trả lời chỉ có tối đa 2 hành động rõ ràng:
  - `Đặt câu hỏi tiếp`
  - `Xem chi tiết nguồn`
- Các thao tác khác chuyển vào menu ngữ cảnh (3 chấm).

## 5.4 Dashboard

- Dashboard mặc định hiển thị theo vai trò và mục tiêu gần nhất.
- Nhóm card thành 3 cụm: `Tác vụ hôm nay`, `An toàn`, `Hệ thống`.
- Với người mới: hiển thị checklist onboarding (3 bước đầu).
- Với doctor: thêm lối tắt Ecosystem/metrics nhưng không dồn toàn bộ dữ liệu ngay màn hình đầu.

## 6. Chuẩn hoá ngôn ngữ giao diện (Language Plan)

## 6.1 Nguyên tắc viết

1. Câu ngắn, chủ động, không mơ hồ.
2. Tránh viết tắt khó hiểu nếu chưa giải thích lần đầu.
3. Dùng thuật ngữ nhất quán trong toàn hệ thống.
4. Đảm bảo thông điệp cảnh báo có mức độ rõ (`Khẩn cấp`, `Cảnh báo`, `Thông tin`).

## 6.2 Bảng thay thế thuật ngữ ưu tiên

- `Research Workspace` -> `Không gian hỏi đáp nghiên cứu`
- `Risk tier` -> `Mức độ rủi ro`
- `Modules` -> `Tính năng`
- `Refresh` -> `Làm mới`
- `Open source` -> `Mở nguồn tham chiếu`
- `Workflow Steps` -> `Các bước phân tích`
- `System Monitor` -> `Giám sát hệ thống`
- `Partner Health` -> `Tình trạng đối tác`

## 6.3 Luồng copy review

1. Trích xuất toàn bộ chuỗi hiển thị từ `apps/web`.
2. Chuẩn hoá vào glossary file dùng chung.
3. Review với 3 nhóm người dùng: phổ thông, nghiên cứu, bác sĩ.
4. Chạy A/B copy cho các CTA quan trọng (`Gửi câu hỏi`, `Kiểm tra tương tác thuốc`).

## 7. Design system và component strategy

- Xây `UI foundation` gồm: typography scale, color tokens, spacing, trạng thái tương tác.
- Tạo component dùng chung cho:
  - Chat input
  - Message card
  - Citation card
  - Alert banner
  - Empty state
  - Guide step card
- Chuẩn hoá layout wrapper: chiều rộng nội dung, khoảng cách theo breakpoint.

## 8. Kế hoạch triển khai chi tiết (lên plan trước, chưa code)

## UX-P0: Audit + định nghĩa chuẩn (2-3 ngày)

### Công việc
1. Audit toàn bộ màn hình hiện có + chụp luồng sử dụng thực tế.
2. Lập `content inventory` cho tất cả chuỗi text.
3. Chốt glossary tiếng Việt + style guide.
4. Chốt IA và sitemap mới.

### Deliverables
- `ui-ux-audit-report.md`
- `content-glossary-vi.md`
- `web-sitemap-v2.md`

### Acceptance
- Có danh sách vấn đề ưu tiên theo mức độ ảnh hưởng onboarding.

## UX-P1: Foundation UI + navigation (3-4 ngày)

### Công việc
1. Chuẩn hoá layout shell và navigation theo IA mới.
2. Refactor typography, spacing, buttons theo design tokens.
3. Thiết lập component cơ sở cho chatbot-style.

### Deliverables
- Layout V2
- Navigation role-aware V2
- Bộ component base

### Acceptance
- Mọi trang dùng chung header/content width/spacing nhất quán.

## UX-P2: Landing + Guide (3-5 ngày)

### Công việc
1. Xây mới landing page đầy đủ nội dung giới thiệu.
2. Xây trang hướng dẫn sử dụng theo role.
3. Thêm CTA xuyên suốt giữa landing -> guide -> login -> workspace.

### Deliverables
- `/` mới
- `/huong-dan`
- CTA funnel tracking

### Acceptance
- Người mới hoàn tất flow từ landing tới câu hỏi đầu tiên trong <= 2 phút.

## UX-P3: Chatbot workspace overhaul (4-6 ngày)

### Công việc
1. Thiết kế lại research/chat theo thread UX.
2. Tách `answer summary` và `evidence panel`.
3. Giảm số nút hiển thị, chuyển thao tác phụ vào menu ngữ cảnh.
4. Đồng bộ pattern phản hồi cho CareGuard/Scribe/Council.

### Deliverables
- Chat layout V2
- Evidence panel chuẩn
- Unified response card

### Acceptance
- Time-to-first-answer giảm, tỷ lệ người dùng hỏi tiếp tăng.

## UX-P4: Language rollout toàn bộ trang (2-3 ngày)

### Công việc
1. Áp glossary cho tất cả page/component.
2. Chuẩn hoá thông điệp lỗi/empty/loading/success.
3. Bổ sung bản copy an toàn y tế (disclaimer theo ngữ cảnh).

### Deliverables
- UI text chuẩn tiếng Việt
- Error messaging framework

### Acceptance
- Không còn label trộn Anh-Việt ở luồng chính.

## UX-P5: Accessibility + mobile polish (3-4 ngày)

### Công việc
1. Kiểm tra contrast, focus order, keyboard navigation.
2. Tối ưu mobile responsive cho landing/chat.
3. Tối ưu performance frontend (CLS/LCP/INP).

### Deliverables
- A11y checklist pass
- Mobile polish pass
- Performance report

### Acceptance
- A11y mức AA cho màn hình cốt lõi.

## UX-P6: Usability test + release gate (2-3 ngày)

### Công việc
1. Chạy usability test với 3 nhóm role.
2. Đo funnel onboarding và chat success.
3. Chốt backlog cải tiến vòng 2.

### Deliverables
- Usability findings
- Release readiness report
- Iteration backlog

### Acceptance
- Đạt KPI UX tối thiểu trước khi mở rộng rollout.

## 9. KPI UX cần đo

1. Onboarding completion rate (landing -> login -> first query).
2. Time to first meaningful answer.
3. Tỷ lệ người dùng quay lại trong 7 ngày.
4. Tỷ lệ sử dụng trang hướng dẫn trước khi tạo support ticket.
5. CSAT theo role sau mỗi phiên.

## 10. Kiểm thử bắt buộc

- Unit test cho component nền tảng (chat input, citation card, alert).
- E2E cho 3 luồng đầu: người mới, researcher, doctor.
- Snapshot test cho landing và guide.
- Copy regression check: không vỡ ngôn ngữ sau mỗi lần merge.

## 11. Ràng buộc triển khai

1. Không tăng số lượng nút chính trên mỗi màn hình vượt quá 2.
2. Không đưa thông tin kỹ thuật dày đặc ở màn hình đầu cho người mới.
3. Mọi cảnh báo y tế phải có phân cấp mức độ và câu chữ an toàn.
4. Mọi thay đổi UI phải giữ tương thích API hiện có.

## 12. Quyết định triển khai tiếp theo

- Sau khi duyệt tài liệu plan này, bắt đầu thực thi theo thứ tự: `UX-P0 -> UX-P1 -> UX-P2 -> UX-P3 -> UX-P4 -> UX-P5 -> UX-P6`.
- Mỗi phase sẽ tách commit nhỏ theo nhóm: `layout`, `content`, `chat`, `a11y`, `tests`.

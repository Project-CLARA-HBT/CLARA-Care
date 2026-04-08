# Frontend UI/UX Rebuild Plan (UIUXProMax) - v1

## 1) Mục tiêu triển khai

- Đập lại trải nghiệm frontend theo hướng `modern + future-med + đơn giản`.
- Tăng conversion cho landing theo cấu trúc chạy ads.
- Giảm rối cho end-user ở luồng chat và self-med.
- Chuẩn hóa navbar + IA (information architecture) theo hành trình dùng thực.
- Đảm bảo deploy an toàn và test đủ chức năng cốt lõi.

## 2) Kiến trúc trang sau khi restructure

### Public Funnel

- `/` Landing chuyển đổi
- `/huong-dan` Hướng dẫn dùng nhanh + FAQ
- `/login`, `/register`, `/forgot-password`, `/reset-password`, `/verify-email`

### Authenticated Core

- `/dashboard` Tổng quan cá nhân theo role
- `/research` Chat nghiên cứu (UI giống mô hình Perplexity/Gemini: input-first)
- `/selfmed` Module tủ thuốc riêng biệt (permanent cabinet)
- `/careguard` Kiểm tra an toàn thuốc chuyên đề
- `/council`, `/scribe` chuyên sâu bác sĩ/research

### Admin Control Plane

- `/admin/overview`
- `/admin/rag-sources`
- `/admin/answer-flow`
- `/admin/observability`

## 3) Navbar mới (thứ tự ưu tiên)

### Normal user

1. `Tổng quan`
2. `Hỏi đáp y tế`
3. `Tủ thuốc`
4. `Kiểm tra tương tác thuốc`
5. `Hướng dẫn`

### Researcher

1. `Tổng quan`
2. `Hỏi đáp nghiên cứu`
3. `Tủ thuốc`
4. `Admin Control Tower`
5. `Hướng dẫn`

### Doctor

1. `Tổng quan`
2. `Hỏi đáp nghiên cứu`
3. `Hội chẩn AI`
4. `Medical Scribe`
5. `Tủ thuốc`
6. `Kiểm tra tương tác thuốc`
7. `Admin Control Tower`

## 4) Micro-task execution (để chia subagent)

### Track A - Design System & Foundation

- A1. Chuẩn hóa token màu, radius, typography, shadow cho phong cách future-med.
- A2. Tạo reusable section wrappers cho landing và nội dung chính.
- A3. Chuẩn hóa spacing/breakpoint cho mobile-first.

### Track B - Landing Conversion

- B1. Hero có 1 CTA chính, 1 CTA phụ.
- B2. Thêm khối social proof + trust bar.
- B3. Thêm visual động nhẹ (biểu đồ/infographic style card) ở homepage.
- B4. Cấu trúc đúng funnel: Hero -> Problem -> Solution -> Feature -> Social proof -> CTA -> FAQ -> Footer pháp lý.

### Track C - Navigation & IA

- C1. Refactor sidebar/navbar theo role + hành trình người dùng.
- C2. Gom nhãn ngôn ngữ thân thiện, bỏ jargon kỹ thuật.
- C3. Chuẩn hóa page metadata/title/subtitle theo route.

### Track D - Research Chat UX

- D1. Composer trung tâm, suggestion chips rõ use-case.
- D2. Rõ mode `Nhanh/Chuyên sâu` và mô tả ngắn ngay cạnh toggle.
- D3. Kết quả phân lớp: Answer -> Sources -> Steps.
- D4. Trạng thái loading/error/fallback phải rõ, không để giao diện “đơ”.

### Track E - Self-Med UX

- E1. Refactor page thành layout app-like: `Cabinet summary`, `Scan`, `Medication list`, `DDI`.
- E2. Làm rõ flow onboarding 3 bước: quét -> thêm -> kiểm tra.
- E3. Nâng cấp biểu diễn risk severity trực quan.
- E4. Giảm text dài, tăng state card dễ đọc cho người lớn tuổi/caregiver.

### Track F - Admin UX (Dify-style)

- F1. Chuẩn hóa visual panel cho nguồn RAG.
- F2. Chuẩn hóa flow toggles + threshold cho answer flow.
- F3. Hiển thị metric card/graph đơn giản, kỹ thuật nhưng dễ quét.

### Track G - QA + Deploy

- G1. Build FE production.
- G2. Deploy chỉ service `web` với `--no-deps`.
- G3. Smoke test route chính và API integration từ frontend.
- G4. Kiểm tra không ảnh hưởng container khác.

## 5) Test checklist bắt buộc sau deploy

- Landing hiển thị đúng và CTA hoạt động.
- Login/register/forgot/reset/verify chạy UI đúng.
- `/research` gửi câu hỏi được ở 2 mode.
- `/selfmed`:
  - tải tủ thuốc thành công,
  - thêm thuốc thủ công thành công,
  - quét OCR (text/file) hiển thị detection,
  - import detection vào tủ,
  - auto DDI check trả về risk.
- `/admin/*` tải config/metrics không crash UI.
- Navbar đổi theo role, không hiển thị sai thứ tự.

## 6) Commit strategy (nhỏ, tách rõ)

- Commit 1: design tokens + shell nền.
- Commit 2: navbar + IA.
- Commit 3: landing funnel.
- Commit 4: research chat UX.
- Commit 5: selfmed UX.
- Commit 6: admin UX polish.
- Commit 7: docs deepdive + execution plan.
- Commit 8: deploy/config FE updates (nếu có).

Mỗi commit:

- tiêu đề <= 50 ký tự, lowercase, không dấu chấm cuối,
- body bullet ngắn nêu thay đổi chính,
- tránh gộp nhiều module không liên quan.

## 7) Rủi ro và chặn lỗi

- Rủi ro lệch API base URL khi build image: bắt buộc kiểm tra `NEXT_PUBLIC_API_URL`.
- Rủi ro UI đẹp nhưng khó dùng: ưu tiên readability và hành động chính.
- Rủi ro regression route: chạy smoke test route matrix trước/ sau deploy.

## 8) Định nghĩa hoàn thành (DoD)

- UI toàn web thống nhất phong cách mới.
- Landing có cấu trúc conversion đầy đủ.
- Chat + self-med thân thiện, không rối chức năng.
- Navbar hợp lý theo role.
- Deploy chạy ổn trên `clara.thiennn.icu`.
- Build pass + smoke test pass.
- Tất cả thay đổi được commit nhỏ, rõ, theo chuẩn message.

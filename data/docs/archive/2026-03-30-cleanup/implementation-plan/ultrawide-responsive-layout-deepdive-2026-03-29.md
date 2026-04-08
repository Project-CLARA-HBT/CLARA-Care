# Ultrawide Responsive Layout Deep Dive - CLARA (2026-03-29)

## 1) Audit vấn đề hiện tại (tập trung màn hình rộng/siêu rộng)

- `apps/web/components/app-shell.tsx` đang cho `isWideWorkspace => max-w-none` ở cả wrapper ngoài và vùng `main`, nên trên màn 1920+ nội dung bị kéo giãn theo viewport thay vì giới hạn rail đọc.
- `apps/web/components/sidebar-nav.tsx` dùng sidebar cố định `w-80` (320px), nhưng không có cơ chế co giãn/toggle theo độ rộng thực tế của workspace.
- `apps/web/app/research/page.tsx` dùng grid cố định `xl:grid-cols-[260px_minmax(0,1fr)_320px]`; khi viewport tăng mạnh, cột giữa phình quá rộng, làm giảm khả năng đọc liên tục.
- Cùng file trên có bubble user `max-w-3xl`, nhưng các khối trả lời chính/evidence chưa có “reading rail max width” nhất quán; độ dài dòng thực tế dễ vượt chuẩn đọc nhanh.
- Hệ breakpoints hiện có tăng `gutter` đến mốc 2160 (`apps/web/styles/globals.css`) nhưng chưa định nghĩa `container max`, `content rail max`, `panel max` cho ultrawide.
- Các trang đang pha trộn nhiều chuẩn rộng (`max-w-5xl`, `max-w-6xl`, `max-w-7xl`, `max-w-none`), dẫn đến trải nghiệm không đồng nhất khi đổi module.

## 2) Benchmark pattern (layout principles) từ ChatGPT / Gemini / Perplexity

## ChatGPT (nguyên tắc)
- Duy trì một trục đọc trung tâm ổn định; nội dung không kéo full-width dù màn hình lớn.
- Sidebar là rail phụ, có thể ẩn/hiện; không cạnh tranh với rail chính khi cần tập trung đọc/soạn.
- Composer bám cùng chiều rộng với luồng hội thoại để giảm chuyển động mắt.

## Gemini (nguyên tắc)
- Ưu tiên “question + answer rail” làm trung tâm; panel phụ xuất hiện theo ngữ cảnh (artifact/source), không ép luôn cố định.
- Bố cục desktop rộng theo hướng linh hoạt 2-pane, nhưng phần text chính vẫn bị “cap” để giữ nhịp đọc.

## Perplexity (nguyên tắc)
- “Answer-first + sources” tách rõ primary rail và evidence rail.
- Trên màn rộng, tăng khoảng thở xung quanh thay vì tăng line length vô hạn.
- Panel nguồn nên là secondary rail (có thể thu gọn), không làm vỡ trọng tâm đọc.

## Tổng hợp nguyên tắc áp dụng cho CLARA
- Một màn chỉ có 1 primary reading rail.
- Secondary rails phải collapse/toggle được.
- Ultrawide ưu tiên thêm whitespace ngoài biên, không mở rộng text rail.
- Input/composer và answer rail phải cùng trục.

## 3) Blueprint responsive cho CLARA

## 3.1 Breakpoints đề xuất

| Mốc | Width | Mục tiêu layout |
|---|---:|---|
| `xs` | `0-639` | 1 cột; panel phụ mở bằng drawer |
| `sm` | `640-1023` | 1 cột chính; nhóm control rút gọn |
| `md` | `1024-1439` | 12 cột; có thể hiện rail trái |
| `lg` | `1440-1919` | 12 cột; đủ 3 rail (trái/chính/phải) |
| `xl` | `1920-2559` | 16 cột; khóa max-width container |
| `2xl+` | `>=2560` | giữ rail cố định, tăng outer gutters |

## 3.2 Grid spec cho workspace chat

- `xs-sm`: `grid-cols-1`; history/evidence thành drawer/sheet.
- `md`: `grid-cols-12`:
  - rail trái: `span 3` (min 240, max 280)
  - rail chính: `span 9`
  - rail phải: ẩn theo mặc định, mở overlay khi cần
- `lg`: `grid-template-columns: 280px minmax(760px, 880px) 320px`
- `xl`: `grid-template-columns: 300px 880px 340px`, bọc trong container `max-width: 1840px`
- `2xl+`: giữ 3 rail như `xl`, nâng `container max-width` lên `2080px`; phần dư chia đều thành outer gutters.

## 3.3 Max line length và typography rail

- Nội dung trả lời dài: mục tiêu `60-72ch`, hard cap `76ch`.
- Đoạn tóm tắt/khuyến nghị: `52-64ch`.
- Danh sách evidence/metadata: `40-56ch`.
- Khối code/bảng: cho phép rộng hơn nhưng giới hạn `max-width: 96ch` + scroll ngang cục bộ.
- Composer nên khóa cùng rail với answer (`max-width: 880px` ở desktop+).

## 3.4 Token/layout contract đề xuất

- `--layout-container-max-lg: 1600px`
- `--layout-container-max-xl: 1840px`
- `--layout-container-max-2xl: 2080px`
- `--layout-rail-main-max: 880px`
- `--layout-rail-left: clamp(260px, 16vw, 300px)`
- `--layout-rail-right: clamp(300px, 18vw, 340px)`
- `--layout-gap: 16px` (`lg: 20px`, `xl+: 24px`)

## 4) KPI kiểm thử UI/UX

- Không có horizontal scroll ngoài ý muốn tại các viewport: `360, 390, 768, 1024, 1366, 1440, 1920, 2560`.
- `P95` line length của đoạn văn trả lời `<= 72ch` (đo tự động bằng script DOM audit).
- Tỷ lệ người dùng hoàn tất tác vụ “hỏi câu đầu tiên” trong 60 giây: `>= 90%` (test nội bộ).
- Tỷ lệ mở panel nguồn mà vẫn quay lại luồng chat chính trong cùng phiên: `>= 75%` (đánh giá không mất ngữ cảnh).
- CLS trang workspace `<= 0.1`; không nhảy layout khi mở/đóng rails.
- Tỷ lệ pass visual regression cho bộ viewport chuẩn: `>= 95%` snapshot ổn định.

## 5) Checklist implement Phase 1

- [ ] Chuẩn hóa layout token trong `globals.css`: thêm `container/rail/gap` tokens cho `lg/xl/2xl+`.
- [ ] Refactor `AppShell`: bỏ `max-w-none` cho wide workspace, chuyển sang container có trần.
- [ ] Tạo `WorkspaceLayout` dùng chung (left rail / main rail / right rail, có chế độ collapse).
- [ ] Áp dụng `WorkspaceLayout` trước cho `research` (pilot), chưa rollout toàn bộ module.
- [ ] Khóa `main answer rail` + `composer` cùng `max-width` theo blueprint.
- [ ] Chuyển `evidence/history` sang cơ chế toggle/drawer ở `md` trở xuống.
- [ ] Thêm test responsive theo viewport matrix (Playwright/Cypress + visual snapshots).
- [ ] Định nghĩa tiêu chí done của Phase 1: pass KPI #1, #2, #5 trước khi mở rộng sang `selfmed/careguard`.

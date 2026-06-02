# Plan Refactor Landing KP3-Inspired (2026-03-29)

## Scope

- Refactor `apps/web/app/page.tsx` theo hướng conversion-first.
- Không đổi routing; chỉ đổi content structure + UI hierarchy + responsive behavior.

## Phase A - Information Architecture

1. Hero conversion block
- Headline kết quả rõ ràng.
- Subheadline ngắn, dễ hiểu cho user mới.
- 2 CTA chính + 1 CTA phụ.
- Trust badges ngay trong fold đầu.

2. Proof strip
- 3-4 bằng chứng ngắn: nguồn, verify/policy, KPI.

3. Value architecture
- 3 product blocks: Research / SelfMed / Control Tower.
- Mỗi block: 1 promise + 3 bullet outcomes.

4. Flow section
- 3 bước “bắt đầu -> phân tích -> hành động”.

5. Objection handling
- FAQ ngắn, trả lời trực diện các phản đối phổ biến.

6. Final CTA
- Single dominant action + secondary action.

## Phase B - Visual & UX

1. Hero visual hierarchy
- Typography mạnh, spacing thoáng.
- CTA area rõ, không quá nhiều nút.

2. Responsive system
- Mobile: 1 cột.
- Tablet: 1-2 cột theo section.
- Desktop/Ultrawide: `max-w-7xl` đồng nhất, không kéo text line quá dài.

3. Conversion readability
- Đoạn mô tả giữ trong line length dễ đọc.
- Mọi section có tiêu đề + microcopy rõ ý định.

## Phase C - Build Checklist

- [ ] Hero + CTA refactor xong.
- [ ] Proof/value/flow/faq/final CTA refactor xong.
- [ ] Dark mode không vỡ màu.
- [ ] Build pass (`npm run build`).

## Done Criteria

- Landing có cấu trúc direct-response rõ ràng.
- CTA chính xuất hiện tối thiểu 3 vị trí hợp lý.
- UI gọn, hiện đại, responsive ổn định trên mobile -> desktop -> ultrawide.

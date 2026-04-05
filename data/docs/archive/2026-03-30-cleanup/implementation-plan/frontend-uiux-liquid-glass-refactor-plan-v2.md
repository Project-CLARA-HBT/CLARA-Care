# Kế Hoạch Refactor UI/UX FE CLARA (Liquid Glass + IA chuẩn)

## 1. Mục tiêu
- Tái cấu trúc frontend để dễ dùng cho người mới, giảm rối chức năng.
- Chuẩn hóa hệ thiết kế (token, typography, shadow, blur, spacing) theo phong cách modern medical + liquid glass.
- Chuẩn hóa điều hướng đa vai trò bằng một nguồn cấu hình duy nhất.
- Giảm technical debt bằng component hóa theo module (Auth, Research, SelfMed, Admin).

## 2. Kết luận audit (deepdive)
### 2.1 Các điểm chưa hợp lý
1. Global CSS bị tách 2 nơi (`app/globals.css` và `styles/globals.css`) gây lệch style system.
2. Token màu mâu thuẫn giữa CSS variables và `tailwind.config.ts`.
3. Không có mobile primary navigation; sidebar chỉ hiện trên desktop.
4. Điều hướng role bị định nghĩa trùng (`sidebar-nav.tsx` và `lib/auth/roles.ts`) dễ drift.
5. `selfmed/page.tsx` là trang monolith quá dài, trộn nhiều flow.
6. `research/page.tsx` vẫn monolith, khó mở rộng kiểu Perplexity/Gemini.
7. Auth pages lặp UI pattern, chưa tận dụng `AuthFormShell`.
8. Ngôn ngữ UI trộn Việt/Anh chưa nhất quán.

### 2.2 Những phần cần dỡ bỏ/giảm bớt
- Dỡ bỏ cấu hình menu theo role bị trùng lặp.
- Dỡ bỏ hardcode page metadata trong `AppShell`.
- Dỡ bỏ pattern copy-paste class cho input/button/feedback trên auth pages.
- Giảm số section “nổi bật ngang nhau” ở landing để tăng conversion funnel.

## 3. Kiến trúc UI mục tiêu
## 3.1 Design System
- Một file global CSS duy nhất: `styles/globals.css`.
- Semantic tokens:
  - Nền: `--bg-canvas`, `--bg-elev-1..3`
  - Glass: `--glass-fill`, `--glass-stroke`, `--blur-sm..lg`
  - Text: `--text-primary`, `--text-secondary`, `--text-muted`
  - Brand/state: `--brand-*`, `--success-*`, `--warn-*`, `--danger-*`
- Utility chuẩn:
  - `glass-surface-1..3`
  - `focus-ring`
  - `text-display`, `text-body`, `text-caption`

## 3.2 IA và điều hướng
- Tạo `lib/navigation.config.ts` làm single source of truth:
  - route meta, nhóm menu, role visibility, thứ tự hiển thị.
- Desktop: sidebar theo nhóm.
- Mobile: bottom nav cho các mục chính + giữ active state rõ ràng.

## 3.3 Componentization
- Auth:
  - `components/auth/auth-form-shell.tsx`
  - `components/auth/auth-feedback.tsx`
  - `components/auth/auth-field.tsx`
- Research:
  - Tách composer, answer card, citation list, debug panel.
- SelfMed:
  - Tách scan panel, cabinet panel, ddi panel, notice/risk badge.

## 4. Roadmap triển khai
## 4.1 Phase 1 (triển khai ngay)
1. Hợp nhất CSS + token.
2. Chuẩn hóa điều hướng (desktop + mobile) bằng config chung.
3. Chuẩn hóa auth pages dùng reusable shell/components.
4. Build kiểm tra regression các route chính.

## 4.2 Phase 2
1. Tách SelfMed thành route module:
   - `/selfmed`
   - `/selfmed/cabinet`
   - `/selfmed/scan`
   - `/selfmed/ddi`
2. Tách Research thành block component và chuẩn bị session UX.

## 4.3 Phase 3
1. Landing revamp funnel tối ưu chuyển đổi.
2. Hoàn thiện motion system (reduced-motion support).
3. A11y pass đầy đủ (focus, contrast, keyboard path).

## 5. KPI giao diện sau refactor
- Mobile không còn dead-end điều hướng.
- Tối thiểu 80% class style lặp được thay bằng component/token chuẩn.
- Time-to-first-action cho user mới giảm (đo qua funnel login -> first query/selfmed action).
- UI copy tiếng Việt nhất quán ở toàn bộ auth + core flow.

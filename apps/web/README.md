# CLARA Web

- Next.js 15 + React 18 + TypeScript + Tailwind CSS.
- Sidebar thay đổi theo role: Normal / Researcher / Doctor / Admin.
- Luồng người dùng cá nhân bắt đầu từ `/today`, `/chat`, `/lifemap`, `/visits`,
  `/family`, `/phr` và hub duy nhất `/medicines`.
- `/selfmed`, `/selfmed/ddi` và `/careguard` là URL tương thích cho bookmark;
  không được dùng cho link mới. Xem
  [`docs/architecture/web-legacy-route-boundaries.md`](../../docs/architecture/web-legacy-route-boundaries.md).
- Các workspace chuyên môn gồm `/research`, `/scribe`, `/council` và
  `/dashboard`, theo RBAC.
- HTTP client tại `lib/http-client.ts` có JWT interceptor và refresh flow.

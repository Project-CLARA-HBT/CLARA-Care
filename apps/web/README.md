# CLARA Web (P0)

- Next.js 14 + TailwindCSS.
- Sidebar thay đổi theo role: Normal / Researcher / Doctor.
- Đã triển khai auth UI và các route nghiệp vụ chính: `/research`, `/scribe`, `/careguard`, `/council`, `/dashboard`.
- HTTP client tại `lib/http-client.ts` có JWT interceptor và refresh flow.

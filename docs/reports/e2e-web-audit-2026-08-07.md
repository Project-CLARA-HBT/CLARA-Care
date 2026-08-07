# Báo cáo kiểm tra E2E web — 2026-08-07

## Phạm vi và nguyên tắc

Kiểm tra được thực hiện trên `https://theclaracare.com` bằng trình duyệt headless
với tài khoản quản trị do chủ hệ thống cung cấp. Không in, lưu vào báo cáo hoặc
thay đổi mật khẩu/tokens. Các thao tác ghi chỉ dùng bản ghi PHR hiện hữu, không
tạo dữ liệu lâm sàng thử nghiệm. “Pass” ở đây là bằng chứng phần mềm/trình duyệt,
không phải xác nhận lâm sàng.

## Kết quả đã xác nhận

| Luồng | Kết quả | Bằng chứng |
|---|---|---|
| Đăng nhập cookie session | Pass | `POST /api/v1/auth/login` trả 200 và cookie CSRF hiện diện trong trình duyệt. |
| CSRF API | Pass | `PUT /phr/record` không header bị chặn 403; cùng payload với cookie/header khớp trả 200. |
| Lưu PHR bằng giao diện | Pass | Login → `/phr/identity` → **Lưu hồ sơ** hoàn tất, không có 4xx hay dòng `CSRF validation failed`. |
| PHR screen links | Pass | `/phr`, `identity`, `body`, `contact`, `allergies`, `conditions`, `medications`, `status`, `export`, `sharing`, `emergency-card`, `reminders` đều trả 200. |
| Personal/professional primary screens | Pass | `/today`, `/chat`, `/lifemap`, `/medicines`, `/family`, `/visits`, `/evidence`, `/council`, `/scribe`, `/dashboard`, `/research/source-hub`, `/account/consent` đều trả 200 với session admin. |
| Public health | Pass | Trang chủ public trả HTTP 200; container web trả `WEB_OK`. |

## Lỗi đã tìm thấy và đã sửa

### 1. CSRF bị sai sau khi tồn tại cookie cũ cùng tên

Nguyên nhân: sau thay đổi cấu hình domain cookie, trình duyệt có thể giữ hai
`clara_csrf_token`. Client cũ lấy giá trị đầu tiên còn FastAPI lấy giá trị cuối
cùng trong header Cookie, làm header và cookie không khớp khi lưu PHR.

Sửa trong commit `21a56746`:

- Client lấy token cuối cùng cùng tên, cùng quy tắc với parser phía API.
- Cookie malformed không chặn việc dùng token hợp lệ kế tiếp.
- Thêm regression test duplicate-cookie.
- Không tắt CSRF, không thêm endpoint miễn CSRF và không thay đổi RBAC/consent.

Kiểm tra cục bộ: auth-store/http-client/PHR 10/10 pass; lint pass với 7 warning
React Hook đã tồn tại từ trước.

### 2. Council first-use tạo 404 nhiễu

Nguyên nhân: khi chưa có case, Council gọi `/council/cases/latest`, endpoint trả
404 đúng theo API cũ nhưng giao diện hiểu thành lỗi tải.

Sửa trong commit `fc6062a5`:

- Ba entry screen Council dùng list owner-scoped giới hạn một case.
- Không có case là empty state bình thường; id case cũ trong local storage bị xóa.
- Không mở rộng dữ liệu cross-profile/cross-user.

Kiểm tra cục bộ: Council focused tests 10/10 và `tsc --noEmit` pass.

## Các URL không phải route hợp lệ

`/medicines/cabinet` trả 404 trong probe, nhưng đây không phải link sản phẩm.
Route đúng là `/medicines?tab=cabinet`; thêm thuốc là `/medicines/cabinet/add`.
Không tạo redirect để tránh duy trì một URL không được đưa ra bởi navigation.

## Chưa thể kết luận “đã chạy hết mọi feature”

Các hành động dưới đây cần fixture/consent/dữ liệu chuyên biệt hoặc tạo bản ghi
mới; không nên tự động kích hoạt bằng tài khoản production trong smoke test:

- tạo/xóa thuốc, OCR upload và import thuốc;
- tạo chia sẻ PHR, thu hồi chia sẻ, export FHIR;
- tạo case Council, chạy hội chẩn và phân luồng khẩn cấp;
- ghi âm Scribe, ký note;
- gửi lời mời người thân, thu hồi quyền; tạo/làm xong LifeMap task;
- gửi chat/research y khoa có free text.

Các luồng này đã có unit/integration tests trong repository, nhưng vẫn cần một
staging profile vô danh + seeded fixtures để có E2E mutation coverage an toàn,
không làm bẩn dữ liệu production. Đây là hạng mục kiểm thử còn thiếu, không phải
bằng chứng rằng tính năng lâm sàng đã được xác nhận.

## Triển khai

- `21a56746` (CSRF) đã được build/deploy trước audit Council.
- `fc6062a5` (Council empty state) đang build web độc lập tại thời điểm ghi báo
  cáo; chỉ xác nhận hoàn tất sau khi log Docker ghi `Container clara-app-web-1 Started`.


# Ranh giới tương thích route cũ trên web

Sản phẩm hướng đến người dùng chỉ có một route chính cho mỗi tác vụ. Các URL
lịch sử vẫn truy cập được để bảo toàn bookmark, liên kết và hướng dẫn hỗ trợ;
chúng không phải đích điều hướng mới và không tạo ra mô hình dữ liệu thứ hai.

| Route lịch sử | Đích chuẩn | Trạng thái và rollback |
| --- | --- | --- |
| `/selfmed` | `/medicines?tab=cabinet` | Alias redirect ở server. Giữ lại khi còn liên kết đã lưu. |
| `/selfmed/ddi` | `/medicines?tab=safety` | Alias redirect ở server. Giữ lại khi còn liên kết đã lưu. |
| `/careguard` | `/medicines?tab=safety` | Alias redirect ở server. Giữ lại khi còn liên kết đã lưu. |
| `/selfmed/add` | `/medicines/cabinet/add` | Entry tương thích cho bookmark cũ. Link mới dùng route Medicines chuẩn, hiện tái sử dụng cùng triển khai quét/thêm đã consent-gate. |
| `/chat` với `NEXT_PUBLIC_CHAT_V2=false` | `/chat` V2 mặc định | Rollback có kiểm soát. Runbook Chat V2 sở hữu quyết định loại bỏ sau này. |
| `/research/*` | `/chat` | Ranh giới tương thích redirect hiện có. |

## Bất biến

- Alias không được bỏ qua authentication, consent, CSRF, RBAC, hoặc đường
  DrugBank fail-closed của CareGuard.
- Hợp nhất URL không được xóa cabinet record, medication course, conversation,
  hoặc dữ liệu LifeMap lịch sử.
- Chỉ xóa route tương thích trong thay đổi được review riêng sau khi đã rà soát
  liên kết hỗ trợ và không còn yêu cầu rollback.

## Rollback

Revert commit hợp nhất route này để các link mới quay về alias lịch sử. Không
cần migration hay rollback dữ liệu vì thay đổi chỉ động đến điều hướng. Riêng
Chat phải dùng quy trình rebuild/deploy với `NEXT_PUBLIC_CHAT_V2=false` đã được
tài liệu hóa, thay vì đổi route.

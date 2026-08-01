# Xoay và khôi phục liên kết chia sẻ công khai

## Phạm vi

Liên kết PHR, cuộc trò chuyện Workspace và báo cáo Research là **bearer
capability**: bất kỳ ai có URL đều có thể đọc đúng projection được cho phép cho
đến khi hết hạn hoặc bị thu hồi. Chúng không phải tài khoản đăng nhập và không
được đưa vào log, analytics, ticket, ảnh chụp màn hình hay cơ sở dữ liệu ở dạng
thô.

Từ Alembic `20260801_0047`, server chỉ lưu SHA-256 của capability. Token thô
chỉ được trả trong response tạo/xoay link. Không có API hay trang owner nào có
thể đọc lại token cũ từ database.

## Vận hành bình thường

1. Owner tạo link và sao chép URL ngay trong response/UI.
2. Nếu cần URL mới, owner chọn **Cấp lại và sao chép** (hoặc xoay liên kết trong
   cuộc trò chuyện). Link cũ bị vô hiệu ngay sau khi token mới được cấp.
3. Owner thu hồi link khi không còn cần chia sẻ. Public đọc revoked, expired và
   unknown đều nhận cùng một phản hồi `404 public_share_unavailable`.
4. PHR có thời hạn mặc định 30 ngày; Workspace/Research có thời hạn mặc định
   168 giờ. Client không gửi `null` để vô tình tạo link vô hạn.

## Incident response

Nếu URL bị lộ, owner thu hồi link hoặc xoay link ngay. Không tìm kiếm token
trong database: giá trị thô không còn ở đó. Kiểm tra audit access và DSAR theo
quy trình compliance hiện có, nhưng không chép capability vào ticket.

## Triển khai và rollback

Trước khi deploy code dùng digest, chạy migration:

```bash
cd services/api
alembic upgrade 20260801_0047
```

Triển khai API và web cùng một release. Migration backfill digest cho các link
cũ nên URL đã cấp vẫn đọc được sau nâng cấp.

`alembic downgrade 20260731_0046` chỉ khôi phục **schema**; hash không thể đổi
ngược thành token. Cách rollback an toàn cho sự cố sau migration là khôi phục
cả application và database backup trước migration, hoặc rollback code và yêu
cầu owner cấp lại liên kết mới. Không downgrade riêng code vào database đã xóa
plaintext.

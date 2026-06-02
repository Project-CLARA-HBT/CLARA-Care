# Production Env Guard & Backup Runbook (2026-04-03)

## Mục tiêu
- Chặn lỗi deploy do `.env` sai host DB (`localhost` trong container runtime).
- Đảm bảo có backup `.env` định kỳ + checksum để rollback nhanh.

## Thành phần mới
- `scripts/ops/validate_runtime_env.sh`
  - Validate `DATABASE_URL`, `POSTGRES_HOST`.
  - Khi `REQUIRE_DEEPSEEK=true`, bắt buộc có `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`.
- `scripts/ops/backup_env.sh`
  - Backup `.env` theo timestamp và lưu file `.sha256`.
  - Có retention (`RETENTION_DAYS`, mặc định 14).
- `scripts/ops/install_env_backup_cron.sh`
  - Cài cron backup env định kỳ (mặc định mỗi 6 giờ).
- `scripts/deploy/redeploy_app_stack.sh`
  - Tích hợp preflight env guard trước khi `docker compose up`.

## Cách dùng nhanh

```bash
# Validate env trước deploy
REQUIRE_DEEPSEEK=true scripts/ops/validate_runtime_env.sh /opt/clara-care/.env

# Backup env thủ công
scripts/ops/backup_env.sh /opt/clara-care/.env

# Cài cron backup mỗi 6 giờ
scripts/ops/install_env_backup_cron.sh "0 */6 * * *" /opt/clara-care/scripts/ops/backup_env.sh
```

## Checklist vận hành production
- [ ] `.env` không dùng `localhost` cho `DATABASE_URL` trong containerized runtime.
- [ ] `POSTGRES_HOST` trỏ đúng service `clara-postgres`.
- [ ] `DEEPSEEK_API_KEY` tồn tại khi chạy gate `REQUIRE_DEEPSEEK=true`.
- [ ] Cron backup env đã cài và log file hoạt động.
- [ ] Có ít nhất 1 backup `.env` mới trong thư mục `.env.backups`.

## Ghi chú an toàn
- Không commit `.env` hoặc backup `.env` vào git.
- Quyền file backup/checksum nên giữ `600`.
- Khi xoay khóa API, chạy backup ngay sau khi cập nhật.

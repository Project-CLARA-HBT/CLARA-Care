# Disk Retention Policy

Mục tiêu:
- Giữ rollback window đủ an toàn cho deploy gần nhất.
- Không để Docker build cache, image cũ và container logs làm đầy disk.
- Ưu tiên tính ổn định của production hơn là giữ lại artifact quá lâu trên server.

## Runtime Policy

- Docker container logs:
  - driver: `json-file`
  - `max-size: 10m`
  - `max-file: 5`
  - Áp dụng cho `api`, `ml`, `web`, `searxng` và các service hạ tầng trong `deploy/docker/docker-compose*.yml`
- Docker image retention:
  - chỉ prune image **không dùng**
  - retention mặc định: `168h` (7 ngày)
- Docker builder cache retention:
  - retention mặc định: `24h`
- App cache cleanup:
  - xóa `.next`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`
  - xóa `.venv*` trong thư mục deploy nếu có

## Ops Commands

- Chạy cleanup thủ công:
  - `./scripts/ops/cleanup_disk.sh --max-used-pct 88 --min-free-gb 4`
- Cài cron mặc định:
  - `./scripts/ops/install_cleanup_cron.sh`
- Cài cron aggressive hơn khi server disk quá nhỏ:
  - `DOCKER_IMAGE_RETENTION_HOURS=96 DOCKER_BUILDER_RETENTION_HOURS=12 ./scripts/ops/install_cleanup_cron.sh '*/20 * * * *'`

## Safe Defaults

- Không prune volume đang dùng.
- Không stop container chỉ để reclaim disk.
- Không xóa image active.
- Không truncate docker json logs trừ khi bật rõ:
  - `TRUNCATE_DOCKER_JSON_LOGS=true`

## Escalation Policy

Nếu disk vẫn >90% sau cleanup:
- kiểm tra `docker system df`
- kiểm tra thư mục lớn trong `/opt`, `/root`, `/var/lib/docker`
- chỉ xóa artifact/backups thủ công sau khi xác định rõ không còn dùng

## Recommended Production Habit

- Sau mỗi đợt rebuild lớn:
  - chạy `cleanup_disk.sh`
- Sau mỗi thay đổi compose:
  - giữ log rotation ở compose, không dựa hoàn toàn vào cleanup script
- Trước demo/hackathon:
  - đảm bảo free disk >= 4GB
  - rebuild sẵn image cần dùng

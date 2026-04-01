# Source Hub Auto Crawl Ops

Script ownership: `scripts/ops/source_hub_auto_crawl.sh`

## 1) Env config

Required:
- `SOURCE_HUB_API_BASE` (default: `http://127.0.0.1:8100/api/v1`)
- `SOURCE_HUB_ACCOUNT` (email account để login API)
- `SOURCE_HUB_PASSWORD`
- `SOURCE_HUB_TOPICS` (danh sách topic, ngăn cách bằng `;` hoặc xuống dòng)

Optional:
- `SOURCE_HUB_SOURCES` (lọc source, ngăn cách bởi `,`/`;`/xuống dòng)
- `SOURCE_HUB_LIMIT` (default: `500`, script sẽ chia batch request để an toàn API)
- `SOURCE_HUB_TIMEOUT_SECONDS` (default: `30`)
- `SOURCE_HUB_LOCK_FILE` (default: `/tmp/clara-source-hub-crawl.lock`)
- `SOURCE_HUB_LOOP_SECONDS` (default: `1`, dùng cho mode loop)

`SOURCE_HUB_TOPICS` hỗ trợ:
- Topic global áp cho mọi source: `warfarin interaction`
- Topic theo source: `pubmed=hypertension guideline`

Ví dụ:

```bash
export SOURCE_HUB_API_BASE="http://127.0.0.1:8100/api/v1"
export SOURCE_HUB_ACCOUNT="ops@research.clara"
export SOURCE_HUB_PASSWORD="secret"
export SOURCE_HUB_TOPICS="warfarin nsaid bleeding risk;metformin renal dosing;davidrug=paracetamol"
export SOURCE_HUB_LIMIT=500
```

## 2) Run thủ công

Chạy 1 lần (cron-safe):

```bash
./scripts/ops/source_hub_auto_crawl.sh --mode once
```

Chạy loop mỗi giây (mô phỏng per-second polling):

```bash
./scripts/ops/source_hub_auto_crawl.sh --mode loop --loop-seconds 1
```

## 3) Cài cron mỗi phút

Installer script:

```bash
./scripts/ops/install_source_hub_crawl_cron.sh
```

Script cài cron sẽ:
- remove job cũ cùng marker
- thêm job mới mỗi phút
- source file `.env` (mặc định `/opt/clara-care/.env`) trước khi chạy
- ghi log mặc định vào `/var/log/clara-source-hub-crawl.log`

Ví dụ custom:

```bash
ENV_FILE=/opt/clara-care/.env.production \
LOG_FILE=/var/log/clara/source-hub-crawl.log \
./scripts/ops/install_source_hub_crawl_cron.sh "* * * * *" "/opt/clara-care/scripts/ops/source_hub_auto_crawl.sh"
```

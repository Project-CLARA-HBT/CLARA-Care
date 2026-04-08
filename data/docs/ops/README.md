# Ops Scripts Quick Guide

## Source Hub auto crawl

- Script chạy crawl: `scripts/ops/source_hub_auto_crawl.sh`
- Installer cron mỗi phút: `scripts/ops/install_source_hub_crawl_cron.sh`
- Hướng dẫn đầy đủ: `docs/ops/source-hub-crawl.md`

Chạy nhanh:

```bash
SOURCE_HUB_ACCOUNT="ops@research.clara" \
SOURCE_HUB_PASSWORD="secret" \
SOURCE_HUB_TOPICS="en: warfarin interaction;vi: tương tác warfarin" \
SOURCE_HUB_AUTO_KEYWORDS=true \
./scripts/ops/source_hub_auto_crawl.sh --mode once
```

## Disk cleanup

- Script cleanup: `scripts/ops/cleanup_disk.sh`
- Installer cron: `scripts/ops/install_cleanup_cron.sh`
- Tài liệu: `docs/ops/disk-retention-policy.md`

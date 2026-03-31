#!/usr/bin/env bash
set -euo pipefail

SCHEDULE="${1:-*/30 * * * *}"
SCRIPT_PATH="${2:-/opt/clara-care/scripts/ops/cleanup_disk.sh}"
MAX_USED_PCT="${MAX_USED_PCT:-88}"
MIN_FREE_GB="${MIN_FREE_GB:-4}"
LOG_FILE="${LOG_FILE:-/var/log/clara-disk-cleanup.log}"
MARKER="# clara-disk-cleanup"

CRON_LINE="${SCHEDULE} ${SCRIPT_PATH} --max-used-pct ${MAX_USED_PCT} --min-free-gb ${MIN_FREE_GB} >> ${LOG_FILE} 2>&1 ${MARKER}"

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

crontab -l 2>/dev/null | grep -v "${MARKER}" >"$tmp_file" || true
echo "$CRON_LINE" >>"$tmp_file"
crontab "$tmp_file"

echo "installed cron:"
echo "$CRON_LINE"

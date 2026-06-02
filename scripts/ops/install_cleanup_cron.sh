#!/usr/bin/env bash
set -euo pipefail

SCHEDULE="${1:-*/30 * * * *}"
SCRIPT_PATH="${2:-/opt/clara-care/scripts/ops/cleanup_disk.sh}"
MAX_USED_PCT="${MAX_USED_PCT:-88}"
MIN_FREE_GB="${MIN_FREE_GB:-4}"
DOCKER_IMAGE_RETENTION_HOURS="${DOCKER_IMAGE_RETENTION_HOURS:-168}"
DOCKER_BUILDER_RETENTION_HOURS="${DOCKER_BUILDER_RETENTION_HOURS:-24}"
TRUNCATE_DOCKER_JSON_LOGS="${TRUNCATE_DOCKER_JSON_LOGS:-false}"
DOCKER_JSON_LOG_MAX_MB="${DOCKER_JSON_LOG_MAX_MB:-200}"
LOG_FILE="${LOG_FILE:-/var/log/clara-disk-cleanup.log}"
MARKER="# clara-disk-cleanup"

CRON_ARGS="--max-used-pct ${MAX_USED_PCT} --min-free-gb ${MIN_FREE_GB} --image-retention-hours ${DOCKER_IMAGE_RETENTION_HOURS} --builder-retention-hours ${DOCKER_BUILDER_RETENTION_HOURS} --docker-json-log-max-mb ${DOCKER_JSON_LOG_MAX_MB}"

if [[ "${TRUNCATE_DOCKER_JSON_LOGS}" == "true" ]]; then
  CRON_ARGS="${CRON_ARGS} --truncate-docker-json-logs"
fi

CRON_LINE="${SCHEDULE} ${SCRIPT_PATH} ${CRON_ARGS} >> ${LOG_FILE} 2>&1 ${MARKER}"

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

crontab -l 2>/dev/null | grep -v "${MARKER}" >"$tmp_file" || true
echo "$CRON_LINE" >>"$tmp_file"
crontab "$tmp_file"

echo "installed cron:"
echo "$CRON_LINE"

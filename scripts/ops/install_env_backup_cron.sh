#!/usr/bin/env bash
set -euo pipefail

SCHEDULE="${1:-0 */6 * * *}"
SCRIPT_PATH="${2:-/opt/clara-care/scripts/ops/backup_env.sh}"
ENV_FILE="${ENV_FILE:-/opt/clara-care/.env}"
BACKUP_DIR="${BACKUP_DIR:-/opt/clara-care/.env.backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
LOG_FILE="${LOG_FILE:-/var/log/clara-env-backup.log}"
MARKER="# clara-env-backup"

CRON_LINE="${SCHEDULE} BACKUP_DIR=${BACKUP_DIR} RETENTION_DAYS=${RETENTION_DAYS} ${SCRIPT_PATH} ${ENV_FILE} >> ${LOG_FILE} 2>&1 ${MARKER}"

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

mkdir -p "$(dirname "${LOG_FILE}")"
touch "${LOG_FILE}"

crontab -l 2>/dev/null | grep -v "${MARKER}" >"${tmp_file}" || true
echo "${CRON_LINE}" >>"${tmp_file}"
crontab "${tmp_file}"

echo "installed cron:"
echo "${CRON_LINE}"

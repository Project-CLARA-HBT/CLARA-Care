#!/usr/bin/env bash
# Install a crontab entry that runs the data-retention sweep on a schedule.
#
# The sweep itself is flag-gated by COMPLIANCE_RETENTION_JOB_ENABLED, so this
# installer is safe to run before the job is enabled per environment (the cron
# will simply log an inert no-op summary until the flag is turned on).
#
# Usage:
#   install_retention_sweep_cron.sh ["<cron schedule>"] [/path/to/run_retention_sweep.sh]
#
# Defaults to a daily 03:15 run of the sibling run_retention_sweep.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SCHEDULE="${1:-15 3 * * *}"
SCRIPT_PATH="${2:-${SCRIPT_DIR}/run_retention_sweep.sh}"
LOG_FILE="${LOG_FILE:-/var/log/clara-retention-sweep.log}"
MARKER="# clara-retention-sweep"

CRON_LINE="${SCHEDULE} ${SCRIPT_PATH} >> ${LOG_FILE} 2>&1 ${MARKER}"

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

crontab -l 2>/dev/null | grep -v "${MARKER}" >"$tmp_file" || true
echo "$CRON_LINE" >>"$tmp_file"
crontab "$tmp_file"

echo "installed cron:"
echo "$CRON_LINE"

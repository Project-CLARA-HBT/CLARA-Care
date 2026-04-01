#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install_source_hub_crawl_cron.sh [schedule] [script_path]

Examples:
  install_source_hub_crawl_cron.sh
  install_source_hub_crawl_cron.sh "* * * * *" "/opt/clara-care/scripts/ops/source_hub_auto_crawl.sh"

Env:
  ENV_FILE   default: /opt/clara-care/.env
  LOG_FILE   default: /var/log/clara-source-hub-crawl.log
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

SCHEDULE="${1:-* * * * *}"
SCRIPT_PATH="${2:-/opt/clara-care/scripts/ops/source_hub_auto_crawl.sh}"
ENV_FILE="${ENV_FILE:-/opt/clara-care/.env}"
LOG_FILE="${LOG_FILE:-/var/log/clara-source-hub-crawl.log}"
MARKER="# clara-source-hub-crawl"

CRON_COMMAND="bash -lc 'if [ -f \"${ENV_FILE}\" ]; then set -a; . \"${ENV_FILE}\"; set +a; fi; \"${SCRIPT_PATH}\" --mode once'"
CRON_LINE="${SCHEDULE} ${CRON_COMMAND} >> ${LOG_FILE} 2>&1 ${MARKER}"

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

crontab -l 2>/dev/null | grep -v "${MARKER}" >"$tmp_file" || true
echo "$CRON_LINE" >>"$tmp_file"
crontab "$tmp_file"

echo "installed cron:"
echo "$CRON_LINE"

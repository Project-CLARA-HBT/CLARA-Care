#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/clara-care}"
MAX_USED_PCT="${MAX_USED_PCT:-88}"
MIN_FREE_GB="${MIN_FREE_GB:-4}"
DOCKER_IMAGE_RETENTION_HOURS="${DOCKER_IMAGE_RETENTION_HOURS:-168}"
DOCKER_BUILDER_RETENTION_HOURS="${DOCKER_BUILDER_RETENTION_HOURS:-24}"
TRUNCATE_DOCKER_JSON_LOGS="${TRUNCATE_DOCKER_JSON_LOGS:-false}"
DOCKER_JSON_LOG_MAX_MB="${DOCKER_JSON_LOG_MAX_MB:-200}"
LOCK_FILE="${LOCK_FILE:-/tmp/clara-disk-cleanup.lock}"
FORCE_RUN="false"
DRY_RUN="false"

usage() {
  cat <<'EOF'
Usage: cleanup_disk.sh [options]

Options:
  --project-dir <path>    Project root to clean local caches (default: /opt/clara-care)
  --max-used-pct <int>    Trigger cleanup when / used% >= value (default: 88)
  --min-free-gb <int>     Trigger cleanup when / free GB < value (default: 4)
  --image-retention-hours <int>   Prune unused docker images older than N hours (default: 168)
  --builder-retention-hours <int> Prune docker builder cache older than N hours (default: 24)
  --truncate-docker-json-logs     Truncate docker json logs larger than --docker-json-log-max-mb
  --docker-json-log-max-mb <int>  Threshold for docker json logs truncation (default: 200)
  --force                 Run cleanup even when thresholds are not exceeded
  --dry-run               Print actions without executing destructive commands
  -h, --help              Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      PROJECT_DIR="${2:?missing value for --project-dir}"
      shift 2
      ;;
    --max-used-pct)
      MAX_USED_PCT="${2:?missing value for --max-used-pct}"
      shift 2
      ;;
    --min-free-gb)
      MIN_FREE_GB="${2:?missing value for --min-free-gb}"
      shift 2
      ;;
    --image-retention-hours)
      DOCKER_IMAGE_RETENTION_HOURS="${2:?missing value for --image-retention-hours}"
      shift 2
      ;;
    --builder-retention-hours)
      DOCKER_BUILDER_RETENTION_HOURS="${2:?missing value for --builder-retention-hours}"
      shift 2
      ;;
    --truncate-docker-json-logs)
      TRUNCATE_DOCKER_JSON_LOGS="true"
      shift
      ;;
    --docker-json-log-max-mb)
      DOCKER_JSON_LOG_MAX_MB="${2:?missing value for --docker-json-log-max-mb}"
      shift 2
      ;;
    --force)
      FORCE_RUN="true"
      shift
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

timestamp() {
  date '+%Y-%m-%d %H:%M:%S%z'
}

log() {
  echo "[$(timestamp)] $*"
}

run_cmd() {
  local cmd="$1"
  if [[ "$DRY_RUN" == "true" ]]; then
    log "[dry-run] $cmd"
    return 0
  fi
  log "run: $cmd"
  if ! bash -lc "$cmd"; then
    log "warn: command failed, continue: $cmd"
  fi
}

disk_used_pct() {
  df -P / | awk 'NR==2 {gsub("%","",$5); print $5}'
}

disk_free_gb() {
  local available_kb
  available_kb="$(df -Pk / | awk 'NR==2 {print $4}')"
  echo $((available_kb / 1024 / 1024))
}

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    log "another cleanup process is running, skip"
    exit 0
  fi
fi

before_used="$(disk_used_pct)"
before_free="$(disk_free_gb)"
log "disk before: used=${before_used}% free=${before_free}GB"

need_cleanup="false"
if [[ "$FORCE_RUN" == "true" ]]; then
  need_cleanup="true"
elif (( before_used >= MAX_USED_PCT )) || (( before_free < MIN_FREE_GB )); then
  need_cleanup="true"
fi

if [[ "$need_cleanup" != "true" ]]; then
  log "threshold not exceeded, skip cleanup"
  exit 0
fi

log "cleanup started (threshold used>=${MAX_USED_PCT}% or free<${MIN_FREE_GB}GB)"

if [[ -d "$PROJECT_DIR" ]]; then
  run_cmd "find '$PROJECT_DIR' -type d \\( -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache' -o -name '.ruff_cache' \\) -prune -exec rm -rf {} +"
  run_cmd "find '$PROJECT_DIR' -type d -name '.next' -prune -exec rm -rf {} +"
  run_cmd "rm -rf '$PROJECT_DIR/.venv' '$PROJECT_DIR/.venv-ci' '$PROJECT_DIR/.venv311'"
fi

if command -v docker >/dev/null 2>&1; then
  # Safe cleanup only: remove unused artifacts, never touch active containers or named volumes in use.
  run_cmd "docker container prune -f"
  run_cmd "docker image prune -af --filter 'until=${DOCKER_IMAGE_RETENTION_HOURS}h'"
  run_cmd "docker builder prune -af --filter 'until=${DOCKER_BUILDER_RETENTION_HOURS}h'"
  run_cmd "docker network prune -f"
  if [[ "$TRUNCATE_DOCKER_JSON_LOGS" == "true" ]]; then
    run_cmd "find /var/lib/docker/containers -type f -name '*-json.log' -size +${DOCKER_JSON_LOG_MAX_MB}M -exec truncate -s ${DOCKER_JSON_LOG_MAX_MB}M {} +"
  fi
else
  log "docker not found, skip docker cleanup"
fi

after_used="$(disk_used_pct)"
after_free="$(disk_free_gb)"
log "disk after: used=${after_used}% free=${after_free}GB"

if (( after_used >= MAX_USED_PCT )) || (( after_free < MIN_FREE_GB )); then
  log "warn: disk is still tight, consider manual cleanup of large artifacts"
  exit 1
fi

log "cleanup completed successfully"

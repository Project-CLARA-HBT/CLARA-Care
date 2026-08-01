#!/usr/bin/env bash
# Deploy one immutable, pre-built CLARA application release on the controlled
# target host.  This script intentionally never builds source or reads a git
# worktree: the bundle contains only deploy configuration and image references.
# Secrets remain in the host-owned environment file and are never emitted.
set -euo pipefail
umask 077

usage() {
  cat <<'EOF'
Usage: deploy_release_bundle.sh --release-dir PATH [--root-dir PATH] [--env-file PATH]

The release directory must contain deploy/docker/docker-compose.deploy.yml,
scripts/ops/validate_runtime_env.sh, and images.env.  The host environment file
is kept outside the release directory, defaults to <root-dir>/.env, and must be
mode 600 or stricter.  On success <root-dir>/current points to this release.
EOF
}

ROOT_DIR="/opt/clara-care"
ENV_FILE=""
RELEASE_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root-dir)
      ROOT_DIR="$2"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --release-dir)
      RELEASE_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[error] unsupported argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$RELEASE_DIR" ]]; then
  echo "[error] --release-dir is required" >&2
  usage >&2
  exit 2
fi

ROOT_DIR="$(cd "$ROOT_DIR" && pwd)"
RELEASE_DIR="$(cd "$RELEASE_DIR" && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

case "$RELEASE_DIR" in
  "$ROOT_DIR"/releases/*) ;;
  *)
    echo "[error] release directory must be below $ROOT_DIR/releases" >&2
    exit 2
    ;;
esac

for required in \
  "$RELEASE_DIR/deploy/docker/docker-compose.deploy.yml" \
  "$RELEASE_DIR/scripts/ops/validate_runtime_env.sh" \
  "$RELEASE_DIR/images.env"; do
  if [[ ! -f "$required" ]]; then
    echo "[error] required release file missing: $required" >&2
    exit 2
  fi
done
if [[ ! -f "$ENV_FILE" ]]; then
  echo "[error] protected environment file missing: $ENV_FILE" >&2
  exit 2
fi

env_mode="$(stat -c '%a' "$ENV_FILE")"
if (( 8#$env_mode & 077 )); then
  echo "[error] protected environment file must not be group/world-readable: $ENV_FILE" >&2
  exit 2
fi

# Image references are release metadata, but still validate them strictly so a
# malformed runner input cannot become shell or compose configuration.
while IFS='=' read -r key value; do
  [[ -z "$key" || "$key" == \#* ]] && continue
  if [[ ! "$key" =~ ^(API|ML|ASR|WEB)_IMAGE$ ]] || [[ ! "$value" =~ ^[A-Za-z0-9._/@:+-]+$ ]]; then
    echo "[error] malformed image reference metadata in images.env" >&2
    exit 2
  fi
done < "$RELEASE_DIR/images.env"
for image_key in API_IMAGE ML_IMAGE ASR_IMAGE WEB_IMAGE; do
  grep -q "^${image_key}=" "$RELEASE_DIR/images.env" || {
    echo "[error] missing $image_key in images.env" >&2
    exit 2
  }
done

mkdir -p "$ROOT_DIR/releases" "$ROOT_DIR/backups/pre-migration"
chmod 700 "$ROOT_DIR/releases" "$ROOT_DIR/backups" "$ROOT_DIR/backups/pre-migration"
exec 9>"$ROOT_DIR/.deploy.lock"
if ! flock -n 9; then
  echo "[error] another deployment is already active" >&2
  exit 1
fi

# Deployment env is operator-controlled.  It is sourced only in this process
# to derive local port/backup names; xtrace is never enabled and nothing below
# prints its values.
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

compose=(
  docker compose
  --project-name clara-app
  --env-file "$ENV_FILE"
  --env-file "$RELEASE_DIR/images.env"
  -f "$RELEASE_DIR/deploy/docker/docker-compose.deploy.yml"
)

REQUIRE_DEEPSEEK=true "$RELEASE_DIR/scripts/ops/validate_runtime_env.sh" "$ENV_FILE"
"${compose[@]}" config >/dev/null

previous_release=""
if [[ -L "$ROOT_DIR/current" ]]; then
  previous_release="$(readlink -f "$ROOT_DIR/current")"
  printf '%s\n' "$previous_release" > "$RELEASE_DIR/previous-release.path"
  chmod 600 "$RELEASE_DIR/previous-release.path"
fi

backup_database() {
  local container="${CLARA_POSTGRES_CONTAINER:-clara-postgres}"
  if ! docker ps --format '{{.Names}}' | grep -qx "$container"; then
    echo "[info] no running Postgres container; skipping pre-migration backup"
    return 0
  fi

  local timestamp dump
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  dump="$ROOT_DIR/backups/pre-migration/pg_clara_${timestamp}.dump"
  echo "[backup] creating verified pre-migration backup"
  docker exec "$container" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$dump"
  test -s "$dump"
  sha256sum "$dump" > "$dump.sha256"
  (cd "$(dirname "$dump")" && sha256sum -c "$(basename "$dump").sha256")
  chmod 600 "$dump" "$dump.sha256"
  printf '%s\n' "$dump" > "$RELEASE_DIR/pre-migration-backup.path"
  chmod 600 "$RELEASE_DIR/pre-migration-backup.path"
}

wait_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-60}"
  local index=1
  while (( index <= attempts )); do
    if curl --fail --silent --show-error --max-time 5 --output /dev/null "$url"; then
      echo "[ok] $label"
      return 0
    fi
    sleep 3
    index=$((index + 1))
  done
  echo "[error] $label did not become ready" >&2
  return 1
}

backup_database
echo "[deploy] pulling immutable release images"
"${compose[@]}" pull
echo "[deploy] starting release services"
"${compose[@]}" up -d --remove-orphans
echo "[migration] upgrading database schema"
"${compose[@]}" exec -T api alembic upgrade head
"${compose[@]}" exec -T api alembic current

wait_http "http://127.0.0.1:${APP_API_PORT:-8100}/health" "API health"
wait_http "http://127.0.0.1:${APP_API_PORT:-8100}/api/v1/health/ready" "API readiness"
wait_http "http://127.0.0.1:${APP_ML_PORT:-8110}/health" "ML health"
wait_http "http://127.0.0.1:${APP_ASR_PORT:-8190}/ready" "ASR readiness"
wait_http "http://127.0.0.1:${APP_WEB_PORT:-3100}/" "web home"
wait_http "http://127.0.0.1:${APP_WEB_PORT:-3100}/share/not-a-real-token" "public conversation route"
wait_http "http://127.0.0.1:${APP_WEB_PORT:-3100}/phr/shared/not-a-real-token" "public PHR route"

ln -sfn "$RELEASE_DIR" "$ROOT_DIR/current"
echo "[deploy] release activated: $(basename "$RELEASE_DIR")"
if [[ -n "$previous_release" && "$previous_release" != "$RELEASE_DIR" ]]; then
  echo "[deploy] previous release retained at: $previous_release"
fi
echo "[deploy] rollback: deploy the prior immutable release image set; restore $(cat "$RELEASE_DIR/pre-migration-backup.path" 2>/dev/null || echo 'the recorded pre-migration backup') only if data recovery is required"

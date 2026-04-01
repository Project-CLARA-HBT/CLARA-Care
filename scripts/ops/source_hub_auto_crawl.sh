#!/usr/bin/env bash
set -euo pipefail

SOURCE_HUB_API_BASE="${SOURCE_HUB_API_BASE:-http://127.0.0.1:8100/api/v1}"
SOURCE_HUB_ACCOUNT="${SOURCE_HUB_ACCOUNT:-}"
SOURCE_HUB_PASSWORD="${SOURCE_HUB_PASSWORD:-}"
SOURCE_HUB_TOPICS="${SOURCE_HUB_TOPICS:-}"
SOURCE_HUB_SOURCES="${SOURCE_HUB_SOURCES:-}"
SOURCE_HUB_LIMIT="${SOURCE_HUB_LIMIT:-500}"
SOURCE_HUB_TIMEOUT_SECONDS="${SOURCE_HUB_TIMEOUT_SECONDS:-30}"
SOURCE_HUB_MODE="${SOURCE_HUB_MODE:-once}"
SOURCE_HUB_LOOP_SECONDS="${SOURCE_HUB_LOOP_SECONDS:-1}"
SOURCE_HUB_LOCK_FILE="${SOURCE_HUB_LOCK_FILE:-/tmp/clara-source-hub-crawl.lock}"

HTTP_STATUS=""
HTTP_BODY=""
LOCK_DIR=""

usage() {
  cat <<'EOF'
Usage: source_hub_auto_crawl.sh [options]

Options:
  --mode <once|loop>            Run once (cron-safe) or loop forever (default: once)
  --loop-seconds <int>          Sleep seconds between cycles in loop mode (default: 1)
  --api-base <url>              API base URL (default: http://127.0.0.1:8100/api/v1)
  --account <email>             Login account (required)
  --password <string>           Login password (required)
  --topics <string>             Topic list separated by ';' or newline
                                Supports global topic: "warfarin interaction"
                                Supports source-specific topic: "pubmed=hypertension guideline"
  --sources <string>            Optional source filter list (comma/semicolon/newline)
  --limit <int>                 Total target fetch limit per source/topic (default: 500)
  --timeout-seconds <int>       HTTP timeout in seconds (default: 30)
  --lock-file <path>            Lock file path (default: /tmp/clara-source-hub-crawl.lock)
  -h, --help                    Show this help message

Env vars are supported for all options with SOURCE_HUB_* names.
EOF
}

timestamp() {
  date '+%Y-%m-%d %H:%M:%S%z'
}

log() {
  echo "[$(timestamp)] [source-hub-crawl] $*" >&2
}

warn() {
  log "WARN: $*"
}

err() {
  log "ERROR: $*"
}

trim() {
  local value="$*"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

is_positive_int() {
  local value="$1"
  [[ "$value" =~ ^[1-9][0-9]*$ ]]
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    err "missing required command: ${cmd}"
    exit 2
  fi
}

acquire_lock() {
  if command -v flock >/dev/null 2>&1; then
    exec 9>"$SOURCE_HUB_LOCK_FILE"
    if ! flock -n 9; then
      log "another source-hub crawl process is running, skip"
      exit 0
    fi
    return 0
  fi

  LOCK_DIR="${SOURCE_HUB_LOCK_FILE}.d"
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    log "another source-hub crawl process is running, skip"
    exit 0
  fi
}

cleanup() {
  if [[ -n "$LOCK_DIR" && -d "$LOCK_DIR" ]]; then
    rmdir "$LOCK_DIR" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

http_request() {
  local method="$1"
  local url="$2"
  local payload="${3:-}"
  local token="${4:-}"
  local body_file
  body_file="$(mktemp)"
  local -a args
  local status=""

  args=(-sS --max-time "$SOURCE_HUB_TIMEOUT_SECONDS" -o "$body_file" -w "%{http_code}" -X "$method")
  args+=(-H "Content-Type: application/json")
  if [[ -n "$token" ]]; then
    args+=(-H "Authorization: Bearer ${token}")
  fi
  if [[ -n "$payload" ]]; then
    args+=(-d "$payload")
  fi

  set +e
  status="$(curl "${args[@]}" "$url")"
  local curl_code=$?
  set -e
  if (( curl_code != 0 )); then
    HTTP_STATUS="000"
    HTTP_BODY=""
    rm -f "$body_file"
    return "$curl_code"
  fi

  HTTP_STATUS="$status"
  HTTP_BODY="$(cat "$body_file")"
  rm -f "$body_file"
  return 0
}

build_login_payload() {
  python3 - "$SOURCE_HUB_ACCOUNT" "$SOURCE_HUB_PASSWORD" <<'PY'
import json
import sys

email = sys.argv[1]
password = sys.argv[2]
print(json.dumps({"email": email, "password": password}, ensure_ascii=False))
PY
}

build_sync_payload() {
  local source="$1"
  local query="$2"
  local limit="$3"
  python3 - "$source" "$query" "$limit" <<'PY'
import json
import sys

source = sys.argv[1]
query = sys.argv[2]
limit = int(sys.argv[3])
print(json.dumps({"source": source, "query": query, "limit": limit}, ensure_ascii=False))
PY
}

extract_access_token() {
  python3 - "$1" <<'PY'
import json
import sys

try:
    payload = json.loads(sys.argv[1] or "{}")
except Exception:
    print("")
    sys.exit(0)
print(payload.get("access_token", "") or "")
PY
}

parse_sync_response() {
  python3 - "$1" <<'PY'
import json
import sys

try:
    payload = json.loads(sys.argv[1] or "{}")
except Exception:
    print("0\t0\t")
    sys.exit(0)

fetched = int(payload.get("fetched", 0) or 0)
stored = int(payload.get("stored", 0) or 0)
warnings = payload.get("warnings") or []
warning_text = " | ".join(str(item).strip() for item in warnings if str(item).strip())
warning_text = warning_text.replace("\t", " ").replace("\n", " ").strip()
print(f"{fetched}\t{stored}\t{warning_text}")
PY
}

build_sync_plan() {
  local catalog_json="$1"
  local catalog_file
  catalog_file="$(mktemp)"
  printf '%s' "$catalog_json" >"$catalog_file"

  python3 - "$catalog_file" "$SOURCE_HUB_TOPICS" "$SOURCE_HUB_SOURCES" <<'PY'
import json
import sys

catalog_path = sys.argv[1]
topics_raw = sys.argv[2]
sources_raw = sys.argv[3]


def split_topics(raw):
    if not raw:
        return []
    normalized = raw.replace("\r", "\n").replace(";", "\n")
    return [chunk.strip() for chunk in normalized.split("\n") if chunk.strip()]


def split_sources(raw):
    if not raw:
        return set()
    normalized = raw.replace("\r", "\n").replace(";", "\n").replace(",", "\n")
    return {chunk.strip().lower() for chunk in normalized.split("\n") if chunk.strip()}


with open(catalog_path, "r", encoding="utf-8") as file_obj:
    payload = json.load(file_obj)

sources = payload.get("sources") or []
requested_sources = split_sources(sources_raw)

selected = []
selected_keys = set()

for item in sources:
    key = str(item.get("key") or "").strip().lower()
    if not key:
        continue
    if not bool(item.get("supports_live_sync", True)):
        continue
    if requested_sources and key not in requested_sources:
        continue
    selected.append((key, str(item.get("default_query") or "").strip()))
    selected_keys.add(key)

if requested_sources:
    for missing in sorted(requested_sources - selected_keys):
        print(
            f"WARN: source '{missing}' not in live catalog, skipped.",
            file=sys.stderr,
        )

global_topics = []
source_topics = {}
for topic in split_topics(topics_raw):
    if "=" in topic:
        lhs, rhs = topic.split("=", 1)
        source_key = lhs.strip().lower()
        source_query = rhs.strip()
        if source_key and source_query:
            source_topics.setdefault(source_key, []).append(source_query)
            continue
    global_topics.append(topic)

if not selected:
    print("ERROR: no source selected from catalog.", file=sys.stderr)
    sys.exit(3)

emitted = 0
for source_key, default_query in selected:
    candidates = []
    candidates.extend(global_topics)
    candidates.extend(source_topics.get(source_key, []))
    if not candidates and default_query:
        candidates.append(default_query)

    deduped = []
    seen = set()
    for query in candidates:
        cleaned = query.strip()
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)

    for query in deduped:
        print(f"{source_key}\t{query}")
        emitted += 1

if emitted == 0:
    print(
        "ERROR: no source/topic pair to sync. Configure SOURCE_HUB_TOPICS or SOURCE_HUB_SOURCES.",
        file=sys.stderr,
    )
    sys.exit(4)
PY

  local status=$?
  rm -f "$catalog_file"
  return "$status"
}

api_login() {
  local login_url="${SOURCE_HUB_API_BASE%/}/auth/login"
  local login_payload
  local token

  login_payload="$(build_login_payload)"
  if ! http_request "POST" "$login_url" "$login_payload"; then
    err "login request failed (url=${login_url})"
    return 1
  fi

  if [[ "${HTTP_STATUS}" != 2* ]]; then
    err "login failed (status=${HTTP_STATUS}) body=$(trim "${HTTP_BODY}")"
    return 1
  fi

  token="$(extract_access_token "$HTTP_BODY")"
  if [[ -z "$token" ]]; then
    err "login response missing access_token"
    return 1
  fi

  printf '%s' "$token"
}

fetch_catalog() {
  local token="$1"
  local catalog_url="${SOURCE_HUB_API_BASE%/}/research/source-hub/catalog"

  if ! http_request "GET" "$catalog_url" "" "$token"; then
    err "catalog request failed (url=${catalog_url})"
    return 1
  fi

  if [[ "${HTTP_STATUS}" != 2* ]]; then
    err "catalog failed (status=${HTTP_STATUS}) body=$(trim "${HTTP_BODY}")"
    return 1
  fi

  printf '%s' "$HTTP_BODY"
}

sync_source_topic() {
  local token="$1"
  local source="$2"
  local query="$3"
  local sync_url="${SOURCE_HUB_API_BASE%/}/research/source-hub/sync"
  local remaining="$SOURCE_HUB_LIMIT"
  local loop_guard=0
  local total_fetched=0
  local last_stored=0

  log "sync start source=${source} query=\"${query}\" target_limit=${SOURCE_HUB_LIMIT}"

  while (( remaining > 0 )); do
    local request_limit="$remaining"
    local parsed=""
    local fetched=0
    local stored=0
    local warning_text=""
    local payload=""

    if (( request_limit > 100 )); then
      request_limit=100
    fi

    payload="$(build_sync_payload "$source" "$query" "$request_limit")"
    if ! http_request "POST" "$sync_url" "$payload" "$token"; then
      err "sync request failed source=${source} query=\"${query}\""
      return 1
    fi

    if [[ "${HTTP_STATUS}" != 2* ]]; then
      err "sync failed source=${source} status=${HTTP_STATUS} body=$(trim "${HTTP_BODY}")"
      return 1
    fi

    parsed="$(parse_sync_response "$HTTP_BODY")"
    IFS=$'\t' read -r fetched stored warning_text <<<"$parsed"
    fetched="$(trim "$fetched")"
    stored="$(trim "$stored")"
    warning_text="$(trim "$warning_text")"

    if ! is_positive_int "$fetched" && [[ "$fetched" != "0" ]]; then
      fetched=0
    fi
    if ! is_positive_int "$stored" && [[ "$stored" != "0" ]]; then
      stored=0
    fi

    total_fetched=$((total_fetched + fetched))
    last_stored="$stored"
    remaining=$((remaining - request_limit))

    log "sync batch source=${source} fetched=${fetched} stored=${stored} batch_limit=${request_limit} remaining_target=${remaining}"
    if [[ -n "$warning_text" ]]; then
      warn "sync warning source=${source} query=\"${query}\" detail=${warning_text}"
    fi

    if (( fetched <= 0 )); then
      break
    fi
    if (( fetched < request_limit )); then
      break
    fi

    loop_guard=$((loop_guard + 1))
    if (( loop_guard >= 50 )); then
      warn "loop guard reached source=${source} query=\"${query}\", stop batching"
      break
    fi
  done

  log "sync completed source=${source} query=\"${query}\" fetched_total=${total_fetched} stored_last=${last_stored}"
  return 0
}

run_cycle() {
  local token=""
  local catalog_json=""
  local plan_lines=""
  local failures=0
  local total_pairs=0

  token="$(api_login)" || return 1
  log "login success account=${SOURCE_HUB_ACCOUNT}"

  catalog_json="$(fetch_catalog "$token")" || return 1
  log "catalog fetched"

  if ! plan_lines="$(build_sync_plan "$catalog_json" 2> >(while IFS= read -r line; do warn "$line"; done))"; then
    err "failed to build sync plan from catalog/topics"
    return 1
  fi

  while IFS=$'\t' read -r source query; do
    source="$(trim "$source")"
    query="$(trim "$query")"
    [[ -z "$source" || -z "$query" ]] && continue
    total_pairs=$((total_pairs + 1))
    if ! sync_source_topic "$token" "$source" "$query"; then
      failures=$((failures + 1))
    fi
  done <<<"$plan_lines"

  log "cycle completed pairs=${total_pairs} failures=${failures}"
  if (( failures > 0 )); then
    return 1
  fi
  return 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      SOURCE_HUB_MODE="$(trim "${2:?missing value for --mode}")"
      shift 2
      ;;
    --loop-seconds)
      SOURCE_HUB_LOOP_SECONDS="$(trim "${2:?missing value for --loop-seconds}")"
      shift 2
      ;;
    --api-base)
      SOURCE_HUB_API_BASE="$(trim "${2:?missing value for --api-base}")"
      shift 2
      ;;
    --account)
      SOURCE_HUB_ACCOUNT="$(trim "${2:?missing value for --account}")"
      shift 2
      ;;
    --password)
      SOURCE_HUB_PASSWORD="${2:?missing value for --password}"
      shift 2
      ;;
    --topics)
      SOURCE_HUB_TOPICS="${2:?missing value for --topics}"
      shift 2
      ;;
    --sources)
      SOURCE_HUB_SOURCES="${2:?missing value for --sources}"
      shift 2
      ;;
    --limit)
      SOURCE_HUB_LIMIT="$(trim "${2:?missing value for --limit}")"
      shift 2
      ;;
    --timeout-seconds)
      SOURCE_HUB_TIMEOUT_SECONDS="$(trim "${2:?missing value for --timeout-seconds}")"
      shift 2
      ;;
    --lock-file)
      SOURCE_HUB_LOCK_FILE="$(trim "${2:?missing value for --lock-file}")"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "unknown option: $1"
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$SOURCE_HUB_MODE" != "once" && "$SOURCE_HUB_MODE" != "loop" ]]; then
  err "--mode must be one of: once, loop"
  exit 2
fi

if ! is_positive_int "$SOURCE_HUB_LOOP_SECONDS"; then
  err "--loop-seconds must be a positive integer"
  exit 2
fi
if ! is_positive_int "$SOURCE_HUB_LIMIT"; then
  err "--limit must be a positive integer"
  exit 2
fi
if ! is_positive_int "$SOURCE_HUB_TIMEOUT_SECONDS"; then
  err "--timeout-seconds must be a positive integer"
  exit 2
fi

if [[ -z "$SOURCE_HUB_ACCOUNT" ]]; then
  err "missing SOURCE_HUB_ACCOUNT (or --account)"
  exit 2
fi
if [[ -z "$SOURCE_HUB_PASSWORD" ]]; then
  err "missing SOURCE_HUB_PASSWORD (or --password)"
  exit 2
fi

require_command "curl"
require_command "python3"

acquire_lock

log "started mode=${SOURCE_HUB_MODE} api_base=${SOURCE_HUB_API_BASE} limit=${SOURCE_HUB_LIMIT}"

if [[ "$SOURCE_HUB_MODE" == "once" ]]; then
  run_cycle
  exit $?
fi

while true; do
  if ! run_cycle; then
    warn "cycle failed in loop mode, continue"
  fi
  sleep "$SOURCE_HUB_LOOP_SECONDS"
done

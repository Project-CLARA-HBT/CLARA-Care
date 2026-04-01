#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${CLARA_PYTHON_BIN:-python3}"

RUN_ID=""
MODE="auto"
API_BASE="${CLARA_API_BASE_URL:-http://127.0.0.1:8000}"
ML_BASE="${CLARA_ML_BASE_URL:-http://127.0.0.1:8001}"
TOKEN="${CLARA_BEARER_TOKEN:-}"
DOCTOR_TOKEN="${CLARA_DOCTOR_BEARER_TOKEN:-}"
EMAIL="${CLARA_DEMO_EMAIL:-}"
PASSWORD="${CLARA_DEMO_PASSWORD:-}"
DOCTOR_EMAIL="${CLARA_DOCTOR_EMAIL:-}"
DOCTOR_PASSWORD="${CLARA_DOCTOR_PASSWORD:-}"
STRICT="false"
LIMIT="200"

CONVERSATION_LOGS=()

usage() {
  cat <<'EOF'
Usage:
  bash scripts/demo/run_active_eval_loop.sh \
    --run-id <id> \
    [--mode auto|static|live] \
    [--api-base <url>] [--ml-base <url>] \
    [--token <bearer>] [--doctor-token <bearer>] \
    [--email <email>] [--password <password>] \
    [--doctor-email <email>] [--doctor-password <password>] \
    [--conversation-log <path>]... \
    [--limit <n>] [--strict true|false]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id)
      RUN_ID="$2"; shift 2 ;;
    --mode)
      MODE="$2"; shift 2 ;;
    --api-base)
      API_BASE="$2"; shift 2 ;;
    --ml-base)
      ML_BASE="$2"; shift 2 ;;
    --token)
      TOKEN="$2"; shift 2 ;;
    --doctor-token)
      DOCTOR_TOKEN="$2"; shift 2 ;;
    --email)
      EMAIL="$2"; shift 2 ;;
    --password)
      PASSWORD="$2"; shift 2 ;;
    --doctor-email)
      DOCTOR_EMAIL="$2"; shift 2 ;;
    --doctor-password)
      DOCTOR_PASSWORD="$2"; shift 2 ;;
    --conversation-log)
      CONVERSATION_LOGS+=("$2"); shift 2 ;;
    --limit)
      LIMIT="$2"; shift 2 ;;
    --strict)
      STRICT="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "[active-eval] Unknown arg: $1" >&2
      usage
      exit 2 ;;
  esac
done

if [[ -z "$RUN_ID" ]]; then
  echo "[active-eval] --run-id is required" >&2
  exit 2
fi

if [[ "$MODE" != "auto" && "$MODE" != "static" && "$MODE" != "live" ]]; then
  echo "[active-eval] --mode must be one of auto|static|live" >&2
  exit 2
fi

normalize_bool() {
  local raw="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$raw" in
    1|true|yes|on) echo "true" ;;
    0|false|no|off) echo "false" ;;
    *)
      echo "[active-eval] invalid bool: $1" >&2
      exit 2 ;;
  esac
}

STRICT="$(normalize_bool "$STRICT")"

BASE_RUN_ID="${RUN_ID}-base"
POST_RUN_ID="${RUN_ID}-postneg"
ARTIFACT_RUN_BASE="${ROOT_DIR}/artifacts/round2/${BASE_RUN_ID}"
ARTIFACT_RUN_POST="${ROOT_DIR}/artifacts/round2/${POST_RUN_ID}"
NEGATIVE_SET="${ROOT_DIR}/data/demo/hard-negative-mined-${RUN_ID}.jsonl"
SUMMARY_DIR="${ROOT_DIR}/artifacts/round2/${RUN_ID}"
SUMMARY_MD="${SUMMARY_DIR}/active-eval-summary.md"
SUMMARY_JSON="${SUMMARY_DIR}/active-eval-summary.json"

mkdir -p "${SUMMARY_DIR}"

log() {
  printf '[active-eval] %s\n' "$*"
}

run_kpi() {
  local target_run_id="$1"
  local extra_env_name="$2"

  local cmd=()
  cmd+=("$PYTHON_BIN" "${ROOT_DIR}/scripts/demo/run_hackathon_kpis.py")
  cmd+=(--run-id "$target_run_id")
  cmd+=(--mode "$MODE")
  cmd+=(--api-base-url "$API_BASE")
  cmd+=(--ml-base-url "$ML_BASE")

  if [[ -n "$TOKEN" ]]; then
    cmd+=(--bearer-token "$TOKEN")
  fi
  if [[ -n "$DOCTOR_TOKEN" ]]; then
    cmd+=(--doctor-bearer-token "$DOCTOR_TOKEN")
  fi
  if [[ -n "$EMAIL" ]]; then
    cmd+=(--email "$EMAIL")
  fi
  if [[ -n "$PASSWORD" ]]; then
    cmd+=(--password "$PASSWORD")
  fi
  if [[ -n "$DOCTOR_EMAIL" ]]; then
    cmd+=(--doctor-email "$DOCTOR_EMAIL")
  fi
  if [[ -n "$DOCTOR_PASSWORD" ]]; then
    cmd+=(--doctor-password "$DOCTOR_PASSWORD")
  fi
  if [[ "$STRICT" == "true" ]]; then
    cmd+=(--strict-live --enforce-gate)
  fi

  log "Run KPI (${extra_env_name}) -> ${target_run_id}"
  "${cmd[@]}"
}

count_jsonl_rows() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo 0
    return
  fi
  awk 'NF {c++} END {print c+0}' "$path"
}

# (a) baseline KPI
run_kpi "$BASE_RUN_ID" "baseline"
if [[ ! -d "$ARTIFACT_RUN_BASE" ]]; then
  echo "[active-eval] baseline run artifact missing: ${ARTIFACT_RUN_BASE}" >&2
  exit 3
fi

# (b) mine hard negatives from latest run
mine_cmd=(
  "$PYTHON_BIN" "${ROOT_DIR}/scripts/demo/mine_hard_negatives.py"
  --run-dir "$ARTIFACT_RUN_BASE"
  --output "$NEGATIVE_SET"
  --limit "$LIMIT"
)
set +u
for item in "${CONVERSATION_LOGS[@]}"; do
  mine_cmd+=(--conversation-log "$item")
done
set -u

log "Mine hard negatives from ${BASE_RUN_ID}"
"${mine_cmd[@]}"

NEGATIVE_COUNT="$(count_jsonl_rows "$NEGATIVE_SET")"
log "Mined negatives: ${NEGATIVE_COUNT}"

# (c) re-run KPI after mining (if any)
POST_EXECUTED="false"
if [[ "$NEGATIVE_COUNT" -gt 0 ]]; then
  export CLARA_ACTIVE_NEGATIVE_SET="$NEGATIVE_SET"
  run_kpi "$POST_RUN_ID" "post-negative"
  unset CLARA_ACTIVE_NEGATIVE_SET || true
  POST_EXECUTED="true"
  if [[ ! -d "$ARTIFACT_RUN_POST" ]]; then
    echo "[active-eval] post-negative run artifact missing: ${ARTIFACT_RUN_POST}" >&2
    exit 4
  fi
else
  log "Skip post-negative KPI run because mined set is empty"
fi

# (d) summary markdown/json
cat > "$SUMMARY_MD" <<EOF
# CLARA Active Eval Loop Summary

- run_id_root: ${RUN_ID}
- baseline_run_id: ${BASE_RUN_ID}
- post_negative_run_id: ${POST_RUN_ID}
- mode: ${MODE}
- strict: ${STRICT}
- api_base: ${API_BASE}
- ml_base: ${ML_BASE}
- baseline_artifact: ${ARTIFACT_RUN_BASE}
- post_artifact_executed: ${POST_EXECUTED}
- mined_negative_set: ${NEGATIVE_SET}
- mined_negative_count: ${NEGATIVE_COUNT}

## Steps
1. Baseline KPI run completed.
2. Hard negatives mined from baseline artifacts.
3. KPI re-run completed if mined set is not empty.
4. Summary exported.
EOF

cat > "$SUMMARY_JSON" <<EOF
{
  "run_id": "${RUN_ID}",
  "mode": "${MODE}",
  "strict": ${STRICT},
  "api_base": "${API_BASE}",
  "ml_base": "${ML_BASE}",
  "baseline_run_id": "${BASE_RUN_ID}",
  "post_run_id": "${POST_RUN_ID}",
  "baseline_artifact": "${ARTIFACT_RUN_BASE}",
  "post_executed": ${POST_EXECUTED},
  "negative_set": "${NEGATIVE_SET}",
  "negative_count": ${NEGATIVE_COUNT}
}
EOF

log "Done"
log "- summary: ${SUMMARY_MD}"
log "- summary_json: ${SUMMARY_JSON}"

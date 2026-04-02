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
PULL_PRODUCTION_LOGS="${CLARA_PULL_PRODUCTION_LOGS:-true}"
PRODUCTION_LOG_SOURCE="${CLARA_PRODUCTION_FLOW_SOURCE:-research}"
PRODUCTION_LOG_LIMIT="${CLARA_PRODUCTION_FLOW_LIMIT:-500}"
PREVIOUS_KPI="${CLARA_PREVIOUS_BASELINE_KPI:-}"
COMPARE_STRICT="${CLARA_COMPARE_STRICT:-false}"
MAX_DROP_RATE="${CLARA_COMPARE_MAX_DROP_RATE:-2.0}"
MAX_LATENCY_INCREASE_MS="${CLARA_COMPARE_MAX_LATENCY_INCREASE_MS:-350.0}"

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
    [--limit <n>] [--strict true|false] \
    [--previous-kpi <path>] [--compare-strict true|false] \
    [--max-drop-rate <float>] [--max-latency-increase-ms <float>]
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
    --pull-production-logs)
      PULL_PRODUCTION_LOGS="$2"; shift 2 ;;
    --production-log-source)
      PRODUCTION_LOG_SOURCE="$2"; shift 2 ;;
    --production-log-limit)
      PRODUCTION_LOG_LIMIT="$2"; shift 2 ;;
    --previous-kpi)
      PREVIOUS_KPI="$2"; shift 2 ;;
    --compare-strict)
      COMPARE_STRICT="$2"; shift 2 ;;
    --max-drop-rate)
      MAX_DROP_RATE="$2"; shift 2 ;;
    --max-latency-increase-ms)
      MAX_LATENCY_INCREASE_MS="$2"; shift 2 ;;
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
PULL_PRODUCTION_LOGS="$(normalize_bool "$PULL_PRODUCTION_LOGS")"
COMPARE_STRICT="$(normalize_bool "$COMPARE_STRICT")"

BASE_RUN_ID="${RUN_ID}-base"
POST_RUN_ID="${RUN_ID}-postneg"
ARTIFACT_RUN_BASE="${ROOT_DIR}/artifacts/round2/${BASE_RUN_ID}"
ARTIFACT_RUN_POST="${ROOT_DIR}/artifacts/round2/${POST_RUN_ID}"
NEGATIVE_SET="${ROOT_DIR}/data/demo/hard-negative-mined-${RUN_ID}.jsonl"
SUMMARY_DIR="${ROOT_DIR}/artifacts/round2/${RUN_ID}"
SUMMARY_MD="${SUMMARY_DIR}/active-eval-summary.md"
SUMMARY_JSON="${SUMMARY_DIR}/active-eval-summary.json"
PRODUCTION_LOG_FILE="${SUMMARY_DIR}/production-flow-events.json"
COMPARE_JSON="${SUMMARY_DIR}/baseline-regression-compare.json"
COMPARE_MD="${SUMMARY_DIR}/baseline-regression-compare.md"

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

discover_previous_kpi() {
  local current_base="$1"
  local current_post="$2"
  local explicit="${3:-}"
  if [[ -n "$explicit" ]]; then
    if [[ -f "$explicit" ]]; then
      printf '%s\n' "$explicit"
      return
    fi
    echo "[active-eval] --previous-kpi not found: $explicit" >&2
    return
  fi

  local search_root="${ROOT_DIR}/artifacts/round2"
  if [[ ! -d "$search_root" ]]; then
    return
  fi

  local candidates=()
  while IFS= read -r path; do
    candidates+=("$path")
  done < <(find "$search_root" -type f -path "*/kpi-report/kpi-report.json" -print)

  if [[ ${#candidates[@]} -eq 0 ]]; then
    return
  fi

  local best_path=""
  local best_mtime=0
  local item=""
  local mtime=0
  for item in "${candidates[@]}"; do
    if [[ "$item" == *"/${current_base}/kpi-report/kpi-report.json" ]]; then
      continue
    fi
    if [[ "$item" == *"/${current_post}/kpi-report/kpi-report.json" ]]; then
      continue
    fi
    mtime="$(stat -f "%m" "$item" 2>/dev/null || echo 0)"
    if [[ "$mtime" -gt "$best_mtime" ]]; then
      best_mtime="$mtime"
      best_path="$item"
    fi
  done

  if [[ -n "$best_path" ]]; then
    printf '%s\n' "$best_path"
  fi
}

# (a) baseline KPI
run_kpi "$BASE_RUN_ID" "baseline"
if [[ ! -d "$ARTIFACT_RUN_BASE" ]]; then
  echo "[active-eval] baseline run artifact missing: ${ARTIFACT_RUN_BASE}" >&2
  exit 3
fi

# (b) mine hard negatives from latest run
if [[ "${PULL_PRODUCTION_LOGS}" == "true" ]]; then
  export_cmd=(
    "$PYTHON_BIN" "${ROOT_DIR}/scripts/demo/export_production_flow_events.py"
    --api-base "$API_BASE"
    --output "$PRODUCTION_LOG_FILE"
    --source "$PRODUCTION_LOG_SOURCE"
    --limit "$PRODUCTION_LOG_LIMIT"
  )
  if [[ -n "$DOCTOR_TOKEN" ]]; then
    export_cmd+=(--token "$DOCTOR_TOKEN")
  elif [[ -n "$TOKEN" ]]; then
    export_cmd+=(--token "$TOKEN")
  elif [[ -n "$DOCTOR_EMAIL" && -n "$DOCTOR_PASSWORD" ]]; then
    export_cmd+=(--email "$DOCTOR_EMAIL" --password "$DOCTOR_PASSWORD")
  elif [[ -n "$EMAIL" && -n "$PASSWORD" ]]; then
    export_cmd+=(--email "$EMAIL" --password "$PASSWORD")
  fi
  log "Export production flow-events from API"
  if "${export_cmd[@]}"; then
    CONVERSATION_LOGS+=("$PRODUCTION_LOG_FILE")
  else
    log "Warning: export production flow-events failed; continue mining without prod flow logs"
  fi
fi

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

# (d) compare against previous baseline run (if available)
TARGET_KPI="${ARTIFACT_RUN_BASE}/kpi-report/kpi-report.json"
if [[ "$POST_EXECUTED" == "true" ]]; then
  TARGET_KPI="${ARTIFACT_RUN_POST}/kpi-report/kpi-report.json"
fi
PREVIOUS_KPI_RESOLVED="$(discover_previous_kpi "$BASE_RUN_ID" "$POST_RUN_ID" "$PREVIOUS_KPI")"
COMPARE_EXECUTED="false"
COMPARE_GO="null"
COMPARE_CURRENT_KPI="$TARGET_KPI"
COMPARE_PREVIOUS_KPI="$PREVIOUS_KPI_RESOLVED"
if [[ -n "$PREVIOUS_KPI_RESOLVED" && -f "$PREVIOUS_KPI_RESOLVED" && -f "$TARGET_KPI" ]]; then
  log "Compare KPI with previous baseline report"
  set +e
  "$PYTHON_BIN" "${ROOT_DIR}/scripts/demo/compare_kpi_reports.py" \
    --current "$TARGET_KPI" \
    --previous "$PREVIOUS_KPI_RESOLVED" \
    --output-json "$COMPARE_JSON" \
    --output-md "$COMPARE_MD" \
    --max-drop-rate "$MAX_DROP_RATE" \
    --max-latency-increase-ms "$MAX_LATENCY_INCREASE_MS"
  compare_rc=$?
  set -e
  COMPARE_EXECUTED="true"
  if [[ "$compare_rc" -eq 0 ]]; then
    COMPARE_GO="true"
  else
    COMPARE_GO="false"
    if [[ "$COMPARE_STRICT" == "true" ]]; then
      echo "[active-eval] baseline regression compare failed in strict mode" >&2
      exit 5
    fi
  fi
else
  log "Skip baseline compare (missing previous KPI or current target report)."
fi

# (e) summary markdown/json
cat > "$SUMMARY_MD" <<EOF
# CLARA Active Eval Loop Summary

- run_id_root: ${RUN_ID}
- baseline_run_id: ${BASE_RUN_ID}
- post_negative_run_id: ${POST_RUN_ID}
- mode: ${MODE}
- strict: ${STRICT}
- pull_production_logs: ${PULL_PRODUCTION_LOGS}
- production_log_source: ${PRODUCTION_LOG_SOURCE}
- production_log_file: ${PRODUCTION_LOG_FILE}
- api_base: ${API_BASE}
- ml_base: ${ML_BASE}
- baseline_artifact: ${ARTIFACT_RUN_BASE}
- post_artifact_executed: ${POST_EXECUTED}
- mined_negative_set: ${NEGATIVE_SET}
- mined_negative_count: ${NEGATIVE_COUNT}
- compare_executed: ${COMPARE_EXECUTED}
- compare_strict: ${COMPARE_STRICT}
- compare_current_kpi: ${COMPARE_CURRENT_KPI}
- compare_previous_kpi: ${COMPARE_PREVIOUS_KPI}
- compare_go: ${COMPARE_GO}
- compare_json: ${COMPARE_JSON}
- compare_md: ${COMPARE_MD}

## Steps
1. Baseline KPI run completed.
2. Hard negatives mined from baseline artifacts.
3. KPI re-run completed if mined set is not empty.
4. Compare with previous baseline run if available.
5. Summary exported.
EOF

cat > "$SUMMARY_JSON" <<EOF
{
  "run_id": "${RUN_ID}",
  "mode": "${MODE}",
  "strict": ${STRICT},
  "pull_production_logs": ${PULL_PRODUCTION_LOGS},
  "production_log_source": "${PRODUCTION_LOG_SOURCE}",
  "production_log_file": "${PRODUCTION_LOG_FILE}",
  "api_base": "${API_BASE}",
  "ml_base": "${ML_BASE}",
  "baseline_run_id": "${BASE_RUN_ID}",
  "post_run_id": "${POST_RUN_ID}",
  "baseline_artifact": "${ARTIFACT_RUN_BASE}",
  "post_executed": ${POST_EXECUTED},
  "negative_set": "${NEGATIVE_SET}",
  "negative_count": ${NEGATIVE_COUNT},
  "compare_executed": ${COMPARE_EXECUTED},
  "compare_strict": ${COMPARE_STRICT},
  "compare_current_kpi": "${COMPARE_CURRENT_KPI}",
  "compare_previous_kpi": "${COMPARE_PREVIOUS_KPI}",
  "compare_go": ${COMPARE_GO},
  "compare_json": "${COMPARE_JSON}",
  "compare_md": "${COMPARE_MD}"
}
EOF

log "Done"
log "- summary: ${SUMMARY_MD}"
log "- summary_json: ${SUMMARY_JSON}"

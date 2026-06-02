#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${CLARA_PYTHON_BIN:-python3}"

RUN_ID="round2-scientific-full-$(date +%Y%m%d-%H%M%S)"
API_BASE_URL="${CLARA_API_BASE_URL:-http://127.0.0.1:8000}"
ML_BASE_URL="${CLARA_ML_BASE_URL:-http://127.0.0.1:8001}"
EMAIL="${CLARA_DEMO_EMAIL:-admin@example.com}"
PASSWORD="${CLARA_DEMO_PASSWORD:-}"
DOCTOR_EMAIL="${CLARA_DOCTOR_EMAIL:-$EMAIL}"
DOCTOR_PASSWORD="${CLARA_DOCTOR_PASSWORD:-$PASSWORD}"
BEARER_TOKEN="${CLARA_BEARER_TOKEN:-}"
DOCTOR_BEARER_TOKEN="${CLARA_DOCTOR_BEARER_TOKEN:-}"
STRICT_LIVE="true"
WITH_ACTIVE_LOOP="true"
NEG_LIMIT="150"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/demo/run_scientific_eval_full.sh [options]

Options:
  --run-id <id>                  Root run id (default: auto timestamp)
  --api-base-url <url>           API base URL (default: http://127.0.0.1:8000)
  --ml-base-url <url>            ML base URL (default: http://127.0.0.1:8001)
  --email <email>                User email for live auth
  --password <password>          User password for live auth
  --doctor-email <email>         Doctor/admin email for runtime toggle
  --doctor-password <password>   Doctor/admin password for runtime toggle
  --bearer-token <token>         User bearer token (optional)
  --doctor-bearer-token <token>  Doctor bearer token (optional)
  --strict-live <true|false>     Enable strict live mode (default: true)
  --with-active-loop <true|false>Run active eval + hard-negative loop (default: true)
  --negative-limit <n>           Max mined hard negatives (default: 150)
EOF
}

normalize_bool() {
  local raw
  raw="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$raw" in
    1|true|yes|on) echo "true" ;;
    0|false|no|off) echo "false" ;;
    *)
      echo "[scientific-full] invalid boolean: $1" >&2
      exit 2
      ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id) RUN_ID="$2"; shift 2 ;;
    --api-base-url) API_BASE_URL="$2"; shift 2 ;;
    --ml-base-url) ML_BASE_URL="$2"; shift 2 ;;
    --email) EMAIL="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --doctor-email) DOCTOR_EMAIL="$2"; shift 2 ;;
    --doctor-password) DOCTOR_PASSWORD="$2"; shift 2 ;;
    --bearer-token) BEARER_TOKEN="$2"; shift 2 ;;
    --doctor-bearer-token) DOCTOR_BEARER_TOKEN="$2"; shift 2 ;;
    --strict-live) STRICT_LIVE="$(normalize_bool "$2")"; shift 2 ;;
    --with-active-loop) WITH_ACTIVE_LOOP="$(normalize_bool "$2")"; shift 2 ;;
    --negative-limit) NEG_LIMIT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "[scientific-full] unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

log() {
  printf '[scientific-full] %s\n' "$*"
}

run_kpi() {
  local mode="$1"
  local run_id="$2"
  shift 2

  local cmd=(
    "$PYTHON_BIN" "$ROOT_DIR/scripts/demo/run_hackathon_kpis.py"
    --mode "$mode"
    --run-id "$run_id"
    --api-base-url "$API_BASE_URL"
    --ml-base-url "$ML_BASE_URL"
  )

  if [[ -n "$BEARER_TOKEN" ]]; then
    cmd+=(--bearer-token "$BEARER_TOKEN")
  else
    cmd+=(--email "$EMAIL" --password "$PASSWORD")
  fi
  if [[ -n "$DOCTOR_BEARER_TOKEN" ]]; then
    cmd+=(--doctor-bearer-token "$DOCTOR_BEARER_TOKEN")
  else
    cmd+=(--doctor-email "$DOCTOR_EMAIL" --doctor-password "$DOCTOR_PASSWORD")
  fi

  if [[ "$STRICT_LIVE" == "true" && "$mode" == "live" ]]; then
    cmd+=(--strict-live --enforce-gate)
  fi

  log "run KPI mode=$mode run_id=$run_id"
  "${cmd[@]}"
}

STATIC_RUN_ID="${RUN_ID}-static"
LIVE_RUN_ID="${RUN_ID}-live"
SUMMARY_DIR="$ROOT_DIR/artifacts/round2/$RUN_ID"
SUMMARY_MD="$SUMMARY_DIR/scientific-eval-summary.md"
SUMMARY_JSON="$SUMMARY_DIR/scientific-eval-summary.json"

mkdir -p "$SUMMARY_DIR"

run_kpi "static" "$STATIC_RUN_ID"
run_kpi "live" "$LIVE_RUN_ID"

ACTIVE_SUMMARY=""
if [[ "$WITH_ACTIVE_LOOP" == "true" && -f "$ROOT_DIR/scripts/demo/run_active_eval_loop.sh" ]]; then
  log "run active eval loop"
  bash "$ROOT_DIR/scripts/demo/run_active_eval_loop.sh" \
    --run-id "${RUN_ID}-active" \
    --mode live \
    --api-base "$API_BASE_URL" \
    --ml-base "$ML_BASE_URL" \
    --email "$EMAIL" \
    --password "$PASSWORD" \
    --doctor-email "$DOCTOR_EMAIL" \
    --doctor-password "$DOCTOR_PASSWORD" \
    --strict "$STRICT_LIVE" \
    --limit "$NEG_LIMIT"
  ACTIVE_SUMMARY="artifacts/round2/${RUN_ID}-active/active-eval-summary.md"
fi

python3 - "$ROOT_DIR" "$STATIC_RUN_ID" "$LIVE_RUN_ID" "$ACTIVE_SUMMARY" "$SUMMARY_MD" "$SUMMARY_JSON" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
static_run = sys.argv[2]
live_run = sys.argv[3]
active_summary = sys.argv[4]
summary_md = Path(sys.argv[5])
summary_json = Path(sys.argv[6])

def load_kpi(run_id: str) -> dict:
    path = root / "artifacts" / "round2" / run_id / "kpi-report" / "kpi-report.json"
    return json.loads(path.read_text(encoding="utf-8"))

def pick_metrics(kpi: dict) -> dict:
    metrics = kpi.get("metrics", {})
    latency = metrics.get("latency", {})
    return {
        "ddi_precision": metrics.get("ddi_precision", {}),
        "fallback_success_rate": metrics.get("fallback_success_rate", {}),
        "refusal_compliance": metrics.get("refusal_compliance", {}),
        "latency_online": latency.get("online", {}),
        "latency_offline": latency.get("offline", {}),
    }

static_kpi = load_kpi(static_run)
live_kpi = load_kpi(live_run)

payload = {
    "static_run_id": static_run,
    "live_run_id": live_run,
    "static": pick_metrics(static_kpi),
    "live": pick_metrics(live_kpi),
    "active_summary": active_summary or None,
}
summary_json.parent.mkdir(parents=True, exist_ok=True)
summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def metric_line(name: str, node: dict) -> str:
    rate = node.get("rate_percent")
    passed = node.get("passed")
    total = node.get("total")
    if rate is None:
        return f"- {name}: n/a"
    if passed is None or total is None:
        return f"- {name}: {rate}%"
    return f"- {name}: {rate}% ({passed}/{total})"

lines = [
    "# Scientific Eval Full Summary",
    "",
    f"- static_run_id: `{static_run}`",
    f"- live_run_id: `{live_run}`",
    "",
    "## Static KPI",
    metric_line("DDI precision", payload["static"]["ddi_precision"]),
    metric_line("Fallback success", payload["static"]["fallback_success_rate"]),
    metric_line("Refusal compliance", payload["static"]["refusal_compliance"]),
    "",
    "## Live KPI",
    metric_line("DDI precision", payload["live"]["ddi_precision"]),
    metric_line("Fallback success", payload["live"]["fallback_success_rate"]),
    metric_line("Refusal compliance", payload["live"]["refusal_compliance"]),
]
if active_summary:
    lines += ["", "## Active Eval", f"- summary: `{active_summary}`"]

summary_md.parent.mkdir(parents=True, exist_ok=True)
summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

log "completed"
log "- static: artifacts/round2/${STATIC_RUN_ID}/kpi-report/kpi-report.json"
log "- live: artifacts/round2/${LIVE_RUN_ID}/kpi-report/kpi-report.json"
if [[ -n "$ACTIVE_SUMMARY" ]]; then
  log "- active: $ACTIVE_SUMMARY"
fi
log "- summary: ${SUMMARY_MD#$ROOT_DIR/}"

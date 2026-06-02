#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${CLARA_MATRIX_PYTHON:-python3}"

RUN_ID="${CLARA_MATRIX_RUN_ID:-round2-$(date +%Y%m%d-%H%M%S)}"
STATIC_RUN_ID="${CLARA_MATRIX_STATIC_RUN_ID:-${RUN_ID}-static}"
ONLINE_RUN_ID="${CLARA_MATRIX_ONLINE_RUN_ID:-${RUN_ID}-online}"
OFFLINE_RUN_ID="${CLARA_MATRIX_OFFLINE_RUN_ID:-${RUN_ID}-offline}"

API_BASE_URL="${CLARA_API_BASE_URL:-http://127.0.0.1:8000}"
ML_BASE_URL="${CLARA_ML_BASE_URL:-http://127.0.0.1:8001}"
TIMEOUT_SECONDS="${CLARA_MATRIX_TIMEOUT_SECONDS:-12}"

REQUIRE_ONLINE="${CLARA_MATRIX_REQUIRE_ONLINE:-true}"
REQUIRE_OFFLINE="${CLARA_MATRIX_REQUIRE_OFFLINE:-true}"

SUMMARY_DIR="${ROOT_DIR}/artifacts/round2/${RUN_ID}"
SUMMARY_JSON="${SUMMARY_DIR}/matrix-summary.json"
SUMMARY_MD="${SUMMARY_DIR}/matrix-summary.md"

mkdir -p "${SUMMARY_DIR}"

log() {
  printf '[round2-matrix] %s\n' "$*"
}

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    log "Thiếu command bắt buộc: ${cmd}"
    return 1
  fi
}

normalize_bool() {
  local raw="${1:-}"
  local lower
  lower="$(printf '%s' "${raw}" | tr '[:upper:]' '[:lower:]')"
  case "${lower}" in
    1|true|yes|y|on)
      printf 'true'
      ;;
    0|false|no|n|off)
      printf 'false'
      ;;
    *)
      return 1
      ;;
  esac
}

MATRIX_FAILED="false"
FAILED_STEPS=()

append_summary_line() {
  printf '%s\n' "$*" >> "${SUMMARY_MD}"
}

json_field() {
  local file="$1"
  local field="$2"
  "${PYTHON_BIN}" - "$file" "$field" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
field = sys.argv[2]
if not path.exists():
    print("")
    raise SystemExit(0)
obj = json.loads(path.read_text(encoding="utf-8"))
parts = field.split(".")
cur = obj
for part in parts:
    if isinstance(cur, dict) and part in cur:
        cur = cur[part]
    else:
        print("")
        raise SystemExit(0)
if isinstance(cur, (dict, list)):
    print(json.dumps(cur, ensure_ascii=False))
else:
    print(cur)
PY
}

http_request() {
  local method="$1"
  local url="$2"
  local token="${3:-}"
  local data="${4:-}"

  local tmp_body
  tmp_body="$(mktemp)"

  local status
  if [[ -n "${token}" ]]; then
    if [[ -n "${data}" ]]; then
      status="$(curl -sS -o "${tmp_body}" -w '%{http_code}' -X "${method}" "${url}" -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' --data "${data}")"
    else
      status="$(curl -sS -o "${tmp_body}" -w '%{http_code}' -X "${method}" "${url}" -H "Authorization: Bearer ${token}")"
    fi
  else
    if [[ -n "${data}" ]]; then
      status="$(curl -sS -o "${tmp_body}" -w '%{http_code}' -X "${method}" "${url}" -H 'Content-Type: application/json' --data "${data}")"
    else
      status="$(curl -sS -o "${tmp_body}" -w '%{http_code}' -X "${method}" "${url}")"
    fi
  fi

  HTTP_STATUS="${status}"
  HTTP_BODY="$(cat "${tmp_body}")"
  rm -f "${tmp_body}"
}

build_common_args() {
  COMMON_ARGS=(
    --api-base-url "${API_BASE_URL}"
    --ml-base-url "${ML_BASE_URL}"
    --timeout-seconds "${TIMEOUT_SECONDS}"
  )

  if [[ -n "${CLARA_DEMO_EMAIL:-}" ]]; then
    COMMON_ARGS+=(--email "${CLARA_DEMO_EMAIL}")
  fi
  if [[ -n "${CLARA_DEMO_PASSWORD:-}" ]]; then
    COMMON_ARGS+=(--password "${CLARA_DEMO_PASSWORD}")
  fi
  if [[ -n "${CLARA_DOCTOR_EMAIL:-}" ]]; then
    COMMON_ARGS+=(--doctor-email "${CLARA_DOCTOR_EMAIL}")
  fi
  if [[ -n "${CLARA_DOCTOR_PASSWORD:-}" ]]; then
    COMMON_ARGS+=(--doctor-password "${CLARA_DOCTOR_PASSWORD}")
  fi
  if [[ -n "${CLARA_BEARER_TOKEN:-}" ]]; then
    COMMON_ARGS+=(--bearer-token "${CLARA_BEARER_TOKEN}")
  fi
  if [[ -n "${CLARA_DOCTOR_BEARER_TOKEN:-}" ]]; then
    COMMON_ARGS+=(--doctor-bearer-token "${CLARA_DOCTOR_BEARER_TOKEN}")
  fi
}

DOCTOR_TOKEN=""
ORIGINAL_RUNTIME_JSON=""
SHOULD_RESTORE_RUNTIME="false"

restore_runtime() {
  if [[ "${SHOULD_RESTORE_RUNTIME}" != "true" ]]; then
    return
  fi
  if [[ -z "${DOCTOR_TOKEN}" || -z "${ORIGINAL_RUNTIME_JSON}" ]]; then
    return
  fi

  log "Khôi phục runtime careguard về trạng thái ban đầu"
  if http_request PUT "${API_BASE_URL}/api/v1/system/careguard/runtime" "${DOCTOR_TOKEN}" "${ORIGINAL_RUNTIME_JSON}"; then
    if [[ "${HTTP_STATUS}" != "200" ]]; then
      log "Cảnh báo: khôi phục runtime trả mã ${HTTP_STATUS}: ${HTTP_BODY}"
      return
    fi
    log "Khôi phục runtime thành công"
  else
    log "Cảnh báo: khôi phục runtime thất bại"
  fi
}

trap restore_runtime EXIT

get_doctor_token() {
  if [[ -n "${CLARA_DOCTOR_BEARER_TOKEN:-}" ]]; then
    DOCTOR_TOKEN="${CLARA_DOCTOR_BEARER_TOKEN}"
    return
  fi

  local email="${CLARA_DOCTOR_EMAIL:-${CLARA_DEMO_EMAIL:-}}"
  local password="${CLARA_DOCTOR_PASSWORD:-${CLARA_DEMO_PASSWORD:-}}"

  if [[ -z "${email}" || -z "${password}" ]]; then
    log "Thiếu token/credential doctor để toggle runtime offline"
    return 1
  fi

  local login_payload
  login_payload="$("${PYTHON_BIN}" - <<PY
import json
print(json.dumps({"email": "${email}", "password": "${password}"}, ensure_ascii=False))
PY
)"

  http_request POST "${API_BASE_URL}/api/v1/auth/login" "" "${login_payload}"
  if [[ "${HTTP_STATUS}" != "200" ]]; then
    log "Login doctor thất bại: HTTP ${HTTP_STATUS} | ${HTTP_BODY}"
    return 1
  fi

  DOCTOR_TOKEN="$(
    HTTP_BODY_JSON="${HTTP_BODY}" "${PYTHON_BIN}" - <<'PY'
import json
import os

raw = os.environ.get("HTTP_BODY_JSON", "")
body = json.loads(raw) if raw else {}
print(body.get("access_token", ""))
PY
  )"

  if [[ -z "${DOCTOR_TOKEN}" ]]; then
    log "Không lấy được access_token doctor từ response login"
    return 1
  fi
}

enable_disable_external_ddi() {
  local enabled="$1" # true|false

  http_request PUT "${API_BASE_URL}/api/v1/system/careguard/runtime" "${DOCTOR_TOKEN}" "{\"external_ddi_enabled\": ${enabled}}"
  if [[ "${HTTP_STATUS}" != "200" ]]; then
    log "Toggle external_ddi_enabled=${enabled} thất bại: HTTP ${HTTP_STATUS} | ${HTTP_BODY}"
    return 1
  fi

  local actual
  actual="$(
    HTTP_BODY_JSON="${HTTP_BODY}" "${PYTHON_BIN}" - <<'PY'
import json
import os

raw = os.environ.get("HTTP_BODY_JSON", "")
body = json.loads(raw) if raw else {}
print(str(body.get("external_ddi_enabled", "")).lower())
PY
  )"

  if [[ "${actual}" != "${enabled}" ]]; then
    log "Toggle phản hồi không khớp, expected=${enabled}, actual=${actual}"
    return 1
  fi
}

run_step() {
  local step_name="$1"
  shift

  log "Bắt đầu: ${step_name}"
  if "$@"; then
    log "Hoàn tất: ${step_name}"
    return 0
  fi
  log "Lỗi: ${step_name}"
  return 1
}

run_step_capture() {
  local step_name="$1"
  shift
  if run_step "${step_name}" "$@"; then
    return 0
  fi
  MATRIX_FAILED="true"
  FAILED_STEPS+=("${step_name}")
  return 1
}

run_matrix() {
  : > "${SUMMARY_MD}"
  append_summary_line "# Round2 Matrix Summary"
  append_summary_line ""
  append_summary_line "- run_id: \`${RUN_ID}\`"
  append_summary_line "- api_base_url: \`${API_BASE_URL}\`"
  append_summary_line "- ml_base_url: \`${ML_BASE_URL}\`"
  append_summary_line "- generated_at: \`$(date -u +"%Y-%m-%dT%H:%M:%SZ")\`"
  append_summary_line ""

  build_common_args

  if ! run_step_capture "Generate demo artifacts" \
    "${PYTHON_BIN}" "${ROOT_DIR}/scripts/demo/generate_demo_artifacts.py" --run-id "${RUN_ID}"; then
    :
  fi

  if ! run_step_capture "KPI static" \
    "${PYTHON_BIN}" "${ROOT_DIR}/scripts/demo/run_hackathon_kpis.py" \
    --mode static \
    --run-id "${STATIC_RUN_ID}" \
    "${COMMON_ARGS[@]}"; then
    :
  fi

  if [[ "${REQUIRE_ONLINE}" == "true" ]]; then
    if ! run_step_capture "KPI live online strict" \
      "${PYTHON_BIN}" "${ROOT_DIR}/scripts/demo/run_hackathon_kpis.py" \
      --mode live \
      --strict-live \
      --run-id "${ONLINE_RUN_ID}" \
      "${COMMON_ARGS[@]}"; then
      :
    fi
  else
    log "Bỏ qua KPI live online strict vì CLARA_MATRIX_REQUIRE_ONLINE=${REQUIRE_ONLINE}"
  fi

  if [[ "${REQUIRE_OFFLINE}" == "true" ]]; then
    local offline_ready="true"
    if ! run_step_capture "Lấy doctor token để toggle runtime" get_doctor_token; then
      offline_ready="false"
    fi

    if [[ "${offline_ready}" == "true" ]]; then
      http_request GET "${API_BASE_URL}/api/v1/system/careguard/runtime" "${DOCTOR_TOKEN}" ""
      if [[ "${HTTP_STATUS}" != "200" ]]; then
        log "Không lấy được runtime hiện tại: HTTP ${HTTP_STATUS} | ${HTTP_BODY}"
        MATRIX_FAILED="true"
        FAILED_STEPS+=("Đọc runtime careguard hiện tại")
        offline_ready="false"
      else
        ORIGINAL_RUNTIME_JSON="${HTTP_BODY}"
        SHOULD_RESTORE_RUNTIME="true"
      fi
    fi

    if [[ "${offline_ready}" == "true" ]]; then
      if run_step_capture "Toggle external DDI OFF" enable_disable_external_ddi false; then
        if ! run_step_capture "KPI live offline fallback strict" \
          "${PYTHON_BIN}" "${ROOT_DIR}/scripts/demo/run_hackathon_kpis.py" \
          --mode live \
          --strict-live \
          --run-id "${OFFLINE_RUN_ID}" \
          "${COMMON_ARGS[@]}"; then
          :
        fi
        if ! run_step_capture "Toggle external DDI ON" enable_disable_external_ddi true; then
          :
        fi
      fi
    else
      log "Bỏ qua KPI live offline fallback vì chưa sẵn sàng runtime toggle"
    fi
  else
    log "Bỏ qua KPI live offline fallback vì CLARA_MATRIX_REQUIRE_OFFLINE=${REQUIRE_OFFLINE}"
  fi

  local static_kpi online_kpi offline_kpi
  static_kpi="${ROOT_DIR}/artifacts/round2/${STATIC_RUN_ID}/kpi-report/kpi-report.json"
  online_kpi="${ROOT_DIR}/artifacts/round2/${ONLINE_RUN_ID}/kpi-report/kpi-report.json"
  offline_kpi="${ROOT_DIR}/artifacts/round2/${OFFLINE_RUN_ID}/kpi-report/kpi-report.json"

  append_summary_line "## Output chính"
  append_summary_line "- static: \`${static_kpi#${ROOT_DIR}/}\`"
  if [[ "${REQUIRE_ONLINE}" == "true" ]]; then
    append_summary_line "- online: \`${online_kpi#${ROOT_DIR}/}\`"
  fi
  if [[ "${REQUIRE_OFFLINE}" == "true" ]]; then
    append_summary_line "- offline: \`${offline_kpi#${ROOT_DIR}/}\`"
  fi
  append_summary_line ""

  if [[ "${MATRIX_FAILED}" == "true" ]]; then
    append_summary_line "## Trạng thái cuối"
    append_summary_line "- decision: **FAILED**"
    append_summary_line "- failed_steps:"
    for step in "${FAILED_STEPS[@]}"; do
      append_summary_line "  - ${step}"
    done
    append_summary_line ""
  else
    append_summary_line "## Trạng thái cuối"
    append_summary_line "- decision: **PASSED**"
    append_summary_line ""
  fi

  append_summary_line "## Snapshot nhanh"
  append_summary_line "| Run | DDI precision (%) | Fallback success (%) | Refusal compliance (%) |"
  append_summary_line "|---|---:|---:|---:|"

  local static_ddi static_fallback static_refusal
  static_ddi="$(json_field "${static_kpi}" "metrics.ddi_precision.rate_percent")"
  static_fallback="$(json_field "${static_kpi}" "metrics.fallback_success_rate.rate_percent")"
  static_refusal="$(json_field "${static_kpi}" "metrics.refusal_compliance.rate_percent")"
  append_summary_line "| static | ${static_ddi:-n/a} | ${static_fallback:-n/a} | ${static_refusal:-n/a} |"

  if [[ "${REQUIRE_ONLINE}" == "true" ]]; then
    local online_ddi online_fallback online_refusal
    online_ddi="$(json_field "${online_kpi}" "metrics.ddi_precision.rate_percent")"
    online_fallback="$(json_field "${online_kpi}" "metrics.fallback_success_rate.rate_percent")"
    online_refusal="$(json_field "${online_kpi}" "metrics.refusal_compliance.rate_percent")"
    append_summary_line "| online | ${online_ddi:-n/a} | ${online_fallback:-n/a} | ${online_refusal:-n/a} |"
  fi

  if [[ "${REQUIRE_OFFLINE}" == "true" ]]; then
    local offline_ddi offline_fallback offline_refusal
    offline_ddi="$(json_field "${offline_kpi}" "metrics.ddi_precision.rate_percent")"
    offline_fallback="$(json_field "${offline_kpi}" "metrics.fallback_success_rate.rate_percent")"
    offline_refusal="$(json_field "${offline_kpi}" "metrics.refusal_compliance.rate_percent")"
    append_summary_line "| offline | ${offline_ddi:-n/a} | ${offline_fallback:-n/a} | ${offline_refusal:-n/a} |"
  fi

  local failed_steps_json
  if ((${#FAILED_STEPS[@]} > 0)); then
    failed_steps_json="$(
      printf '%s\n' "${FAILED_STEPS[@]}" | "${PYTHON_BIN}" -c \
        'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()], ensure_ascii=False))'
    )"
  else
    failed_steps_json="[]"
  fi

  ROOT_DIR_ENV="${ROOT_DIR}" \
  SUMMARY_JSON_ENV="${SUMMARY_JSON}" \
  RUN_ID_ENV="${RUN_ID}" \
  API_BASE_URL_ENV="${API_BASE_URL}" \
  ML_BASE_URL_ENV="${ML_BASE_URL}" \
  STATIC_RUN_ID_ENV="${STATIC_RUN_ID}" \
  ONLINE_RUN_ID_ENV="${ONLINE_RUN_ID}" \
  OFFLINE_RUN_ID_ENV="${OFFLINE_RUN_ID}" \
  REQUIRE_ONLINE_ENV="${REQUIRE_ONLINE}" \
  REQUIRE_OFFLINE_ENV="${REQUIRE_OFFLINE}" \
  MATRIX_FAILED_ENV="${MATRIX_FAILED}" \
  FAILED_STEPS_JSON_ENV="${failed_steps_json}" \
  SUMMARY_MD_ENV="${SUMMARY_MD}" \
  "${PYTHON_BIN}" - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT_DIR_ENV"])
summary_json = Path(os.environ["SUMMARY_JSON_ENV"])
summary_json.parent.mkdir(parents=True, exist_ok=True)
payload = {
    "run_id": os.environ["RUN_ID_ENV"],
    "api_base_url": os.environ["API_BASE_URL_ENV"],
    "ml_base_url": os.environ["ML_BASE_URL_ENV"],
    "static_run_id": os.environ["STATIC_RUN_ID_ENV"],
    "online_run_id": os.environ["ONLINE_RUN_ID_ENV"],
    "offline_run_id": os.environ["OFFLINE_RUN_ID_ENV"],
    "require_online": os.environ["REQUIRE_ONLINE_ENV"].lower() == "true",
    "require_offline": os.environ["REQUIRE_OFFLINE_ENV"].lower() == "true",
    "summary_markdown": str(Path(os.environ["SUMMARY_MD_ENV"]).relative_to(root)),
    "matrix_failed": os.environ["MATRIX_FAILED_ENV"].lower() == "true",
    "failed_steps": json.loads(os.environ.get("FAILED_STEPS_JSON_ENV", "[]")),
}
summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

  log "Đã ghi summary: ${SUMMARY_MD#${ROOT_DIR}/}"
  log "Đã ghi summary JSON: ${SUMMARY_JSON#${ROOT_DIR}/}"

  if [[ "${MATRIX_FAILED}" == "true" ]]; then
    log "Matrix kết thúc với lỗi ở các bước: ${FAILED_STEPS[*]}"
    return 1
  fi
}

cd "${ROOT_DIR}"

require_cmd "${PYTHON_BIN}" || exit 2
require_cmd curl || exit 2

if ! REQUIRE_ONLINE="$(normalize_bool "${REQUIRE_ONLINE}")"; then
  log "Giá trị CLARA_MATRIX_REQUIRE_ONLINE không hợp lệ: ${REQUIRE_ONLINE}"
  exit 2
fi
if ! REQUIRE_OFFLINE="$(normalize_bool "${REQUIRE_OFFLINE}")"; then
  log "Giá trị CLARA_MATRIX_REQUIRE_OFFLINE không hợp lệ: ${REQUIRE_OFFLINE}"
  exit 2
fi

run_matrix

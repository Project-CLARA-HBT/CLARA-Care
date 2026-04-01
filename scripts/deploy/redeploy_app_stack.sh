#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-/opt/clara-care}"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
REQUIRE_DEEPSEEK="${REQUIRE_DEEPSEEK:-true}"
SKIP_BUILD="${SKIP_BUILD:-false}"

if [[ ! -d "${ROOT_DIR}" ]]; then
  echo "[deploy] root dir not found: ${ROOT_DIR}" >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[deploy] env file not found: ${ENV_FILE}" >&2
  exit 1
fi

COMPOSE=(
  docker compose
  --env-file "${ENV_FILE}"
  -f "${ROOT_DIR}/deploy/docker/docker-compose.yml"
  -f "${ROOT_DIR}/deploy/docker/docker-compose.app.yml"
)

bridge_api_to_postgres_network() {
  local postgres_container="${POSTGRES_CONTAINER_NAME:-clara-postgres}"
  local api_container_id
  local postgres_container_id
  local network

  api_container_id="$("${COMPOSE[@]}" ps -q api 2>/dev/null || true)"
  postgres_container_id="$(docker ps -q -f "name=^/${postgres_container}$" 2>/dev/null || true)"

  if [[ -z "${api_container_id}" || -z "${postgres_container_id}" ]]; then
    return 0
  fi

  while IFS= read -r network; do
    [[ -z "${network}" ]] && continue
    docker network connect "${network}" "${api_container_id}" 2>/dev/null || true
  done < <(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "${postgres_container_id}")
}

wait_json() {
  local url="$1"
  local pattern="$2"
  local attempts="${3:-20}"
  local sleep_seconds="${4:-2}"

  for ((i=1; i<=attempts; i++)); do
    if output="$(curl -fsSL "${url}" 2>/dev/null)"; then
      if [[ "${output}" == *"${pattern}"* ]]; then
        echo "[health] ok ${url}"
        return 0
      fi
    fi
    echo "[health] waiting ${url} (${i}/${attempts})"
    sleep "${sleep_seconds}"
  done

  echo "[health] failed ${url} did not contain pattern: ${pattern}" >&2
  return 1
}

SMOKE_RESEARCH_FAIL_REASON=""

smoke_research_mode() {
  local ml_url="$1"
  local research_mode="$2"
  local output_file="$3"
  local require_deepseek="$4"
  local last_reason="no successful attempt"

  for attempt in 1 2 3; do
    if curl -fsS -m 120 -X POST "${ml_url}/v1/research/tier2" \
      -H 'Content-Type: application/json' \
      -d "{\"query\":\"aspirin and ibuprofen interaction risk\",\"research_mode\":\"${research_mode}\",\"source_mode\":\"hybrid\"}" > "${output_file}"; then
      :
    else
      local curl_exit="$?"
      last_reason="transport_error (curl_exit=${curl_exit})"
      echo "[smoke] ${research_mode} attempt ${attempt} failed at transport layer (curl_exit=${curl_exit})"
      sleep 2
      continue
    fi

    if [[ "${require_deepseek}" =~ ^(1|true|yes)$ ]]; then
      local policy_reason
      if ! policy_reason="$(
        RESEARCH_JSON="${output_file}" \
        RESEARCH_MODE="${research_mode}" \
        python3 - <<'PY'
import json
import os
import sys

with open(os.environ["RESEARCH_JSON"], "r", encoding="utf-8") as file_obj:
    research = json.load(file_obj)

mode = os.environ["RESEARCH_MODE"]
context_debug = research.get("context_debug")
if not isinstance(context_debug, dict):
    context_debug = {}
used_stages = set(context_debug.get("used_stages") or [])
fallback_used = bool(research.get("fallback_used"))

if "llm_generation" not in used_stages:
    print(f"{mode}: llm_generation stage not present")
    sys.exit(1)
if fallback_used:
    print(f"{mode}: fallback_used=true")
    sys.exit(1)
PY
      )"; then
        policy_reason="${policy_reason//$'\n'/; }"
        if [[ -z "${policy_reason}" ]]; then
          policy_reason="${research_mode}: deepseek policy check failed"
        fi
        last_reason="deepseek_policy_violation (${policy_reason})"
        echo "[smoke] ${research_mode} attempt ${attempt} failed deepseek policy: ${policy_reason}; retrying..."
        sleep 2
        continue
      fi
    fi

    SMOKE_RESEARCH_FAIL_REASON=""
    return 0
  done

  SMOKE_RESEARCH_FAIL_REASON="${last_reason}"
  return 1
}

smoke_ml() {
  local ml_url="http://127.0.0.1:8110"
  local tmp_dir
  local require_deepseek
  local deep_research_json
  local deep_beta_research_json
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "${tmp_dir}"' RETURN
  require_deepseek="$(printf '%s' "${REQUIRE_DEEPSEEK}" | tr '[:upper:]' '[:lower:]')"
  deep_research_json="${tmp_dir}/research.deep.json"
  deep_beta_research_json="${tmp_dir}/research.deep_beta.json"

  curl -fsS -m 30 -X POST "${ml_url}/v1/chat/routed" \
    -H 'Content-Type: application/json' \
    -d '{"query":"hi","role":"admin"}' > "${tmp_dir}/chat.json"

  if ! smoke_research_mode "${ml_url}" "deep" "${deep_research_json}" "${require_deepseek}"; then
    echo "[smoke] FAILED"
    echo "- deep research failed after retries: ${SMOKE_RESEARCH_FAIL_REASON}"
    return 1
  fi

  if ! smoke_research_mode "${ml_url}" "deep_beta" "${deep_beta_research_json}" "${require_deepseek}"; then
    echo "[smoke] FAILED"
    echo "- deep_beta research failed after retries: ${SMOKE_RESEARCH_FAIL_REASON}"
    return 1
  fi

  curl -fsS -m 20 -X POST "${ml_url}/v1/careguard/analyze" \
    -H 'Content-Type: application/json' \
    -d '{"medications":["Aspirin","Ibuprofen"],"symptoms":[],"allergies":[]}' > "${tmp_dir}/careguard.json"

  REQUIRE_DEEPSEEK="${REQUIRE_DEEPSEEK}" \
  TMP_DIR="${tmp_dir}" \
  RESEARCH_DEEP_JSON="${deep_research_json}" \
  RESEARCH_DEEP_BETA_JSON="${deep_beta_research_json}" \
  python3 - <<'PY'
import json
import os
import sys

tmp_dir = os.environ["TMP_DIR"]
with open(f"{tmp_dir}/chat.json", "r", encoding="utf-8") as file_obj:
    chat = json.load(file_obj)
with open(os.environ["RESEARCH_DEEP_JSON"], "r", encoding="utf-8") as file_obj:
    deep_research = json.load(file_obj)
with open(os.environ["RESEARCH_DEEP_BETA_JSON"], "r", encoding="utf-8") as file_obj:
    deep_beta_research = json.load(file_obj)
with open(f"{tmp_dir}/careguard.json", "r", encoding="utf-8") as file_obj:
    careguard = json.load(file_obj)
require_deepseek = os.environ.get("REQUIRE_DEEPSEEK", "true").lower() in {"1", "true", "yes"}

errors = []

if not str(chat.get("answer", "")).strip():
    errors.append("chat answer empty")

def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _validate_research_mode(payload, mode):
    mode_errors = []
    if not isinstance(payload, dict):
        return [f"{mode}: response payload is not an object"], set(), ""
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    if payload.get("research_mode") != mode:
        mode_errors.append(
            f"{mode}: research_mode mismatch (got {payload.get('research_mode')!r})"
        )
    metadata_mode = metadata.get("research_mode")
    if metadata_mode not in ("", None, mode):
        mode_errors.append(f"{mode}: metadata.research_mode mismatch (got {metadata_mode!r})")

    deep_pass_count = _safe_int(payload.get("deep_pass_count") or 0)
    if deep_pass_count < 3:
        mode_errors.append(f"{mode}: deep_pass_count < 3 (got {deep_pass_count})")

    flow_events = payload.get("flow_events")
    if not isinstance(flow_events, list):
        flow_events = metadata.get("flow_events") if isinstance(metadata.get("flow_events"), list) else []
    stages = {str(item.get("stage")) for item in flow_events if isinstance(item, dict)}

    if mode == "deep":
        if "evidence_search" not in stages:
            mode_errors.append("deep: missing evidence_search stage")
        if "evidence_index" not in stages:
            mode_errors.append("deep: missing evidence_index stage")
    elif mode == "deep_beta":
        pipeline = str(metadata.get("pipeline") or "")
        if "deep-beta" not in pipeline:
            mode_errors.append(
                f"deep_beta: metadata.pipeline missing deep-beta runtime marker (got {pipeline!r})"
            )
        required_beta_stages = {
            "deep_beta_scope",
            "deep_beta_hypothesis_map",
            "deep_beta_retrieval_budget",
            "deep_beta_multi_pass_retrieval",
            "deep_beta_chain_synthesis",
            "deep_beta_chain_verification",
        }
        missing_beta_stages = sorted(required_beta_stages - stages)
        if missing_beta_stages:
            mode_errors.append(
                "deep_beta: missing runtime stages: " + ", ".join(missing_beta_stages)
            )

        reasoning_steps = payload.get("reasoning_steps")
        if not isinstance(reasoning_steps, list):
            reasoning_steps = metadata.get("reasoning_steps")
        if not isinstance(reasoning_steps, list) or len(reasoning_steps) < 3:
            mode_errors.append(
                "deep_beta: reasoning_steps missing or too short for beta runtime"
            )

        retrieval_budgets = payload.get("retrieval_budgets")
        if not isinstance(retrieval_budgets, dict):
            retrieval_budgets = (
                metadata.get("retrieval_budgets")
                if isinstance(metadata.get("retrieval_budgets"), dict)
                else {}
            )
        if retrieval_budgets.get("mode") != "deep_beta":
            mode_errors.append(
                f"deep_beta: retrieval_budgets.mode is not deep_beta (got {retrieval_budgets.get('mode')!r})"
            )

        chain_status = payload.get("chain_status")
        if not isinstance(chain_status, dict):
            chain_status = metadata.get("chain_status") if isinstance(metadata.get("chain_status"), dict) else {}
        if chain_status.get("mode") != "deep_beta":
            mode_errors.append(
                f"deep_beta: chain_status.mode is not deep_beta (got {chain_status.get('mode')!r})"
            )

    context_debug = payload.get("context_debug")
    if not isinstance(context_debug, dict):
        context_debug = {}
    used_stages = {str(item) for item in (context_debug.get("used_stages") or [])}
    if require_deepseek and "llm_generation" not in used_stages:
        mode_errors.append(f"{mode}: llm_generation stage not present")
    if require_deepseek and bool(payload.get("fallback_used")):
        mode_errors.append(f"{mode}: fallback_used=true under REQUIRE_DEEPSEEK")

    return mode_errors, used_stages, str(metadata.get("pipeline") or "")


deep_errors, deep_used_stages, deep_pipeline = _validate_research_mode(deep_research, "deep")
beta_errors, deep_beta_used_stages, deep_beta_pipeline = _validate_research_mode(
    deep_beta_research, "deep_beta"
)
errors.extend(deep_errors)
errors.extend(beta_errors)

risk = careguard.get("risk") or {}
metadata = careguard.get("metadata") or {}
if risk.get("level") not in {"low", "medium", "high"}:
    errors.append("careguard risk level invalid")
if "source_used" not in metadata:
    errors.append("careguard metadata.source_used missing")

if errors:
    print("[smoke] FAILED")
    for item in errors:
        print(f"- {item}")
    sys.exit(1)

print("[smoke] OK")
print(f"chat_intent={chat.get('intent')}")
print(f"research_deep_pipeline={deep_pipeline}")
print(f"research_deep_beta_pipeline={deep_beta_pipeline}")
print(f"research_deep_fallback={deep_research.get('fallback_used')}")
print(f"research_deep_beta_fallback={deep_beta_research.get('fallback_used')}")
print(f"research_deep_stages={sorted(deep_used_stages)}")
print(f"research_deep_beta_stages={sorted(deep_beta_used_stages)}")
print(f"careguard_level={risk.get('level')}")
print(f"careguard_sources={metadata.get('source_used')}")
PY
}

smoke_auth() {
  local api_url="http://127.0.0.1:8100/api/v1"
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "${tmp_dir}"' RETURN

  local email="mobile-smoke-$(date +%s)@example.com"
  local password="secret123"

  curl -fsS -c "${tmp_dir}/cookies.txt" \
    -X POST "${api_url}/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"${email}\",\"password\":\"${password}\"}" > "${tmp_dir}/login.json"

  curl -fsS -b "${tmp_dir}/cookies.txt" \
    "${api_url}/auth/me" > "${tmp_dir}/me.json"

  curl -fsS -b "${tmp_dir}/cookies.txt" \
    -X POST "${api_url}/auth/refresh" \
    -H 'Content-Type: application/json' \
    -d '{}' > "${tmp_dir}/refresh.json"

  TMP_DIR="${tmp_dir}" python3 - <<'PY'
import json
import os
import sys

tmp_dir = os.environ["TMP_DIR"]
with open(f"{tmp_dir}/login.json", "r", encoding="utf-8") as file_obj:
    login_payload = json.load(file_obj)
with open(f"{tmp_dir}/me.json", "r", encoding="utf-8") as file_obj:
    me_payload = json.load(file_obj)
with open(f"{tmp_dir}/refresh.json", "r", encoding="utf-8") as file_obj:
    refresh_payload = json.load(file_obj)

errors = []
if not login_payload.get("access_token"):
    errors.append("missing access_token from login")
if not login_payload.get("refresh_token"):
    errors.append("missing refresh_token from login")
if not me_payload.get("subject"):
    errors.append("auth/me did not resolve subject via cookie")
if not refresh_payload.get("access_token"):
    errors.append("refresh without body token did not issue access_token")

if errors:
    print("[smoke-auth] FAILED")
    for item in errors:
        print(f"- {item}")
    sys.exit(1)

print("[smoke-auth] OK")
print(f"subject={me_payload.get('subject')}")
PY
}

cd "${ROOT_DIR}"

echo "[deploy] using env file: ${ENV_FILE}"
if [[ "${SKIP_BUILD}" == "true" ]]; then
  "${COMPOSE[@]}" up -d api ml web
else
  "${COMPOSE[@]}" up -d --build api ml web
fi

bridge_api_to_postgres_network

wait_json "http://127.0.0.1:8100/health" '"status":"ok"'
wait_json "http://127.0.0.1:8110/health" '"status":"ok"'
wait_json "http://127.0.0.1:3100" "<html" 25 2
wait_json "http://127.0.0.1:3100/research" "<html" 25 2
wait_json "http://127.0.0.1:3100/research/deepdive" "<html" 25 2
wait_json "http://127.0.0.1:3100/research/analyze" "<html" 25 2
wait_json "http://127.0.0.1:3100/research/citations" "<html" 25 2
wait_json "http://127.0.0.1:3100/research/details" "<html" 25 2

if [[ "${REQUIRE_DEEPSEEK}" == "true" ]]; then
  wait_json "http://127.0.0.1:8110/health/details" '"deepseek_configured":true' 20 2
fi

smoke_ml
smoke_auth

echo "[deploy] completed successfully"

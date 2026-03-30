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

wait_json() {
  local url="$1"
  local pattern="$2"
  local attempts="${3:-20}"
  local sleep_seconds="${4:-2}"

  for ((i=1; i<=attempts; i++)); do
    if output="$(curl -fsS "${url}" 2>/dev/null)"; then
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

smoke_ml() {
  local ml_url="http://127.0.0.1:8110"
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "${tmp_dir}"' RETURN

  curl -fsS -X POST "${ml_url}/v1/chat/routed" \
    -H 'Content-Type: application/json' \
    -d '{"query":"hi","role":"admin"}' > "${tmp_dir}/chat.json"

  curl -fsS -X POST "${ml_url}/v1/research/tier2" \
    -H 'Content-Type: application/json' \
    -d '{"query":"aspirin and ibuprofen interaction risk","research_mode":"deep","source_mode":"hybrid"}' > "${tmp_dir}/research.json"

  curl -fsS -X POST "${ml_url}/v1/careguard/analyze" \
    -H 'Content-Type: application/json' \
    -d '{"medications":["Aspirin","Ibuprofen"],"symptoms":[],"allergies":[]}' > "${tmp_dir}/careguard.json"

  REQUIRE_DEEPSEEK="${REQUIRE_DEEPSEEK}" \
  TMP_DIR="${tmp_dir}" \
  python3 - <<'PY'
import json
import os
import sys

tmp_dir = os.environ["TMP_DIR"]
with open(f"{tmp_dir}/chat.json", "r", encoding="utf-8") as file_obj:
    chat = json.load(file_obj)
with open(f"{tmp_dir}/research.json", "r", encoding="utf-8") as file_obj:
    research = json.load(file_obj)
with open(f"{tmp_dir}/careguard.json", "r", encoding="utf-8") as file_obj:
    careguard = json.load(file_obj)
require_deepseek = os.environ.get("REQUIRE_DEEPSEEK", "true").lower() in {"1", "true", "yes"}

errors = []

if not str(chat.get("answer", "")).strip():
    errors.append("chat answer empty")

if research.get("research_mode") != "deep":
    errors.append("research_mode is not deep")
if int(research.get("deep_pass_count") or 0) < 3:
    errors.append("deep_pass_count < 3")

flow_events = research.get("flow_events") or []
stages = {str(item.get("stage")) for item in flow_events if isinstance(item, dict)}
if "evidence_search" not in stages:
    errors.append("missing evidence_search stage")
if "evidence_index" not in stages:
    errors.append("missing evidence_index stage")

context_debug = research.get("context_debug") or {}
used_stages = set(context_debug.get("used_stages") or [])
if require_deepseek and "llm_generation" not in used_stages:
    errors.append("llm_generation stage not present")
if require_deepseek and bool(research.get("fallback_used")):
    errors.append("research still uses fallback")

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
print(f"research_pipeline={(research.get('metadata') or {}).get('pipeline')}")
print(f"research_fallback={research.get('fallback_used')}")
print(f"research_stages={sorted(used_stages)}")
print(f"careguard_level={risk.get('level')}")
print(f"careguard_sources={metadata.get('source_used')}")
PY
}

cd "${ROOT_DIR}"

echo "[deploy] using env file: ${ENV_FILE}"
if [[ "${SKIP_BUILD}" == "true" ]]; then
  "${COMPOSE[@]}" up -d api ml web
else
  "${COMPOSE[@]}" up -d --build api ml web
fi

wait_json "http://127.0.0.1:8100/health" '"status":"ok"'
wait_json "http://127.0.0.1:8110/health" '"status":"ok"'
wait_json "http://127.0.0.1:3100" "<html" 25 2

if [[ "${REQUIRE_DEEPSEEK}" == "true" ]]; then
  wait_json "http://127.0.0.1:8110/health/details" '"deepseek_configured":true' 20 2
fi

smoke_ml

echo "[deploy] completed successfully"

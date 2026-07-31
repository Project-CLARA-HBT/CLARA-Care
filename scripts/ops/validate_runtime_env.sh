#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-/opt/clara-care/.env}"
REQUIRE_DEEPSEEK="${REQUIRE_DEEPSEEK:-true}"
EXPECTED_POSTGRES_HOST="${EXPECTED_POSTGRES_HOST:-clara-postgres}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[env-guard] env file not found: ${ENV_FILE}" >&2
  exit 2
fi

tmp_env="$(mktemp)"
trap 'rm -f "${tmp_env}"' EXIT

# Keep only key=value rows and parse without shell evaluation.
grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${ENV_FILE}" > "${tmp_env}" || true

declare -A ENV_VALUES=()
while IFS= read -r line; do
  [[ -z "${line}" ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi
  ENV_VALUES["${key}"]="${value}"
done < "${tmp_env}"

errors=0

must_set_non_empty() {
  local var_name="$1"
  local value="${ENV_VALUES[${var_name}]:-}"
  if [[ -z "${value}" ]]; then
    echo "[env-guard] missing required variable: ${var_name}" >&2
    errors=$((errors + 1))
  fi
}

must_be_positive_number() {
  local var_name="$1"
  local value="${ENV_VALUES[${var_name}]:-}"
  if ! awk -v value="${value}" 'BEGIN { exit !(value ~ /^[0-9]+([.][0-9]+)?$/ && (value + 0) > 0) }'; then
    echo "[env-guard] ${var_name} must be a positive number" >&2
    errors=$((errors + 1))
  fi
}

warn_if_equals() {
  local var_name="$1"
  local bad_value="$2"
  local value="${ENV_VALUES[${var_name}]:-}"
  if [[ "${value}" == "${bad_value}" ]]; then
    echo "[env-guard] invalid ${var_name}=${value}; expected non-${bad_value} for containerized runtime" >&2
    errors=$((errors + 1))
  fi
}

must_set_non_empty "DATABASE_URL"
must_set_non_empty "POSTGRES_HOST"
warn_if_equals "POSTGRES_HOST" "localhost"
warn_if_equals "POSTGRES_HOST" "127.0.0.1"

if [[ "${ENV_VALUES[POSTGRES_HOST]:-}" != "${EXPECTED_POSTGRES_HOST}" ]]; then
  echo "[env-guard] warning: POSTGRES_HOST=${ENV_VALUES[POSTGRES_HOST]:-} (expected ${EXPECTED_POSTGRES_HOST} for compose network)"
fi

if [[ "${ENV_VALUES[DATABASE_URL]:-}" == *"@localhost:"* ]] || [[ "${ENV_VALUES[DATABASE_URL]:-}" == *"@127.0.0.1:"* ]]; then
  echo "[env-guard] invalid DATABASE_URL host (localhost/127.0.0.1) for containerized runtime" >&2
  errors=$((errors + 1))
fi

require_deepseek_normalized="$(printf '%s' "${REQUIRE_DEEPSEEK}" | tr '[:upper:]' '[:lower:]')"
if [[ "${require_deepseek_normalized}" == "true" ]] || [[ "${REQUIRE_DEEPSEEK}" == "1" ]]; then
  must_set_non_empty "DEEPSEEK_API_KEY"
  must_set_non_empty "DEEPSEEK_BASE_URL"
  must_set_non_empty "DEEPSEEK_MODEL"
  must_set_non_empty "DEEPSEEK_PRO_MODEL"
  must_set_non_empty "DEEPSEEK_FLASH_MODEL"
  must_set_non_empty "DEEPSEEK_AUDIO_MODEL"
  must_set_non_empty "DEEPSEEK_TIMEOUT_SECONDS"
  must_set_non_empty "ML_SERVICE_TIMEOUT_SECONDS"
  if [[ "${ENV_VALUES[DEEPSEEK_MODEL]:-}" != "${ENV_VALUES[DEEPSEEK_PRO_MODEL]:-}" ]]; then
    echo "[env-guard] DEEPSEEK_MODEL must equal DEEPSEEK_PRO_MODEL for the governed V4 default route" >&2
    errors=$((errors + 1))
  fi
  if [[ "${ENV_VALUES[DEEPSEEK_PRO_MODEL]:-}" == "${ENV_VALUES[DEEPSEEK_FLASH_MODEL]:-}" ]]; then
    echo "[env-guard] DEEPSEEK_PRO_MODEL and DEEPSEEK_FLASH_MODEL must be distinct" >&2
    errors=$((errors + 1))
  fi
  if [[ "${ENV_VALUES[DEEPSEEK_PRO_MODEL]:-}" != "deepseek-v4-pro" ]]; then
    echo "[env-guard] DEEPSEEK_PRO_MODEL must be deepseek-v4-pro for the governed V4 route" >&2
    errors=$((errors + 1))
  fi
  if [[ "${ENV_VALUES[DEEPSEEK_FLASH_MODEL]:-}" != "deepseek-v4-flash" ]]; then
    echo "[env-guard] DEEPSEEK_FLASH_MODEL must be deepseek-v4-flash for the governed V4 route" >&2
    errors=$((errors + 1))
  fi
  if [[ "${ENV_VALUES[LLM_DEEPSEEK_ONLY]:-}" != "true" ]]; then
    echo "[env-guard] LLM_DEEPSEEK_ONLY=true is required for the governed runtime" >&2
    errors=$((errors + 1))
  fi
  if [[ "${ENV_VALUES[MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED]:-}" != "true" ]]; then
    echo "[env-guard] MODEL_REGISTRY_TASK_MODEL_ROUTING_ENABLED=true is required for V4 Pro/Flash task routing" >&2
    errors=$((errors + 1))
  fi
  if [[ "${ENV_VALUES[MODEL_REGISTRY_ENABLED]:-}" != "true" ]]; then
    echo "[env-guard] MODEL_REGISTRY_ENABLED=true is required for the governed runtime" >&2
    errors=$((errors + 1))
  fi
  must_be_positive_number "DEEPSEEK_TIMEOUT_SECONDS"
  must_be_positive_number "ML_SERVICE_TIMEOUT_SECONDS"
  if awk -v api_timeout="${ENV_VALUES[ML_SERVICE_TIMEOUT_SECONDS]:-0}" -v ml_timeout="${ENV_VALUES[DEEPSEEK_TIMEOUT_SECONDS]:-0}" 'BEGIN { exit !((api_timeout + 0) < (ml_timeout + 0)) }'; then
    echo "[env-guard] ML_SERVICE_TIMEOUT_SECONDS must be >= DEEPSEEK_TIMEOUT_SECONDS" >&2
    errors=$((errors + 1))
  fi
fi

# A watermark backfill is broader than ordinary incremental ingestion: it can
# contact every enabled upstream source. The runtime must make that opt-in
# explicit and keep the persistent corpus plane available; otherwise refuse to
# launch a configuration that can only fail mid-run.
backfill_enabled_normalized="$(printf '%s' "${ENV_VALUES[RAG_BACKFILL_ENABLED]:-false}" | tr '[:upper:]' '[:lower:]')"
if [[ "${backfill_enabled_normalized}" == "true" ]] || [[ "${backfill_enabled_normalized}" == "1" ]]; then
  if [[ "${ENV_VALUES[RAG_INGESTION_ENABLED]:-}" != "true" ]]; then
    echo "[env-guard] RAG_BACKFILL_ENABLED=true requires RAG_INGESTION_ENABLED=true" >&2
    errors=$((errors + 1))
  fi
  if [[ "${ENV_VALUES[RAG_PERSISTENT_STORE_ENABLED]:-}" != "true" ]]; then
    echo "[env-guard] RAG_BACKFILL_ENABLED=true requires RAG_PERSISTENT_STORE_ENABLED=true" >&2
    errors=$((errors + 1))
  fi
fi

# A strict CareGuard deployment has no safe curated/LLM substitute for DrugBank
# DDI conclusions. Catch contradictory or unprovisioned bind-mount settings
# before compose starts a container that must fail closed at request time.
drugbank_required_normalized="$(printf '%s' "${ENV_VALUES[CAREGUARD_DRUGBANK_REQUIRED]:-false}" | tr '[:upper:]' '[:lower:]')"
if [[ "${drugbank_required_normalized}" == "true" ]] || [[ "${drugbank_required_normalized}" == "1" ]]; then
  if [[ "${ENV_VALUES[CAREGUARD_DRUGBANK_SQLITE_ENABLED]:-}" != "true" ]]; then
    echo "[env-guard] CAREGUARD_DRUGBANK_REQUIRED=true requires CAREGUARD_DRUGBANK_SQLITE_ENABLED=true" >&2
    errors=$((errors + 1))
  fi
  if [[ "${ENV_VALUES[CAREGUARD_DRUGBANK_MANIFEST_INTEGRITY_REQUIRED]:-}" != "true" ]]; then
    echo "[env-guard] CAREGUARD_DRUGBANK_REQUIRED=true requires CAREGUARD_DRUGBANK_MANIFEST_INTEGRITY_REQUIRED=true" >&2
    errors=$((errors + 1))
  fi
  must_set_non_empty "CAREGUARD_DRUGBANK_ARTIFACT_HOST_DIR"
  must_set_non_empty "CAREGUARD_DRUGBANK_MANIFEST_PATH"
  must_set_non_empty "CAREGUARD_DRUGBANK_SQLITE_PATH"
  drugbank_artifact_host_dir="${ENV_VALUES[CAREGUARD_DRUGBANK_ARTIFACT_HOST_DIR]:-}"
  if [[ -n "${drugbank_artifact_host_dir}" && ! -d "${drugbank_artifact_host_dir}" ]]; then
    echo "[env-guard] CAREGUARD_DRUGBANK_ARTIFACT_HOST_DIR is not a readable directory" >&2
    errors=$((errors + 1))
  fi
fi

if (( errors > 0 )); then
  echo "[env-guard] failed with ${errors} error(s)" >&2
  exit 1
fi

echo "[env-guard] ok: ${ENV_FILE}"

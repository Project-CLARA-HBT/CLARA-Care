#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-/opt/clara-care}"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
PAGE_SIZE="${PAGE_SIZE:-100}"
MAX_RECORDS="${MAX_RECORDS:-0}"
COMMIT_EVERY="${COMMIT_EVERY:-500}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-45}"
SLEEP_SECONDS="${SLEEP_SECONDS:-0.02}"
IMPORT_USER_EMAIL="${IMPORT_USER_EMAIL:-}"
DRY_RUN="${DRY_RUN:-false}"
SUMMARY_JSON="${SUMMARY_JSON:-${ROOT_DIR}/data/demo/vn_davidrug_seed_summary.json}"

if [[ ! -d "${ROOT_DIR}" ]]; then
  echo "[seed-vn-davidrug] root dir not found: ${ROOT_DIR}" >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[seed-vn-davidrug] env file not found: ${ENV_FILE}" >&2
  exit 1
fi

if [[ -z "${IMPORT_USER_EMAIL}" ]]; then
  echo "[seed-vn-davidrug] IMPORT_USER_EMAIL is required and must reference an existing user account." >&2
  exit 1
fi

COMPOSE=(
  docker compose
  --env-file "${ENV_FILE}"
  -f "${ROOT_DIR}/deploy/docker/docker-compose.yml"
  -f "${ROOT_DIR}/deploy/docker/docker-compose.app.yml"
)

mkdir -p "$(dirname "${SUMMARY_JSON}")"

ARGS=(
  python -m clara_api.scripts.seed_vn_davidrug_dictionary
  --page-size "${PAGE_SIZE}"
  --max-records "${MAX_RECORDS}"
  --commit-every "${COMMIT_EVERY}"
  --timeout-seconds "${TIMEOUT_SECONDS}"
  --sleep-seconds "${SLEEP_SECONDS}"
  --import-user-email "${IMPORT_USER_EMAIL}"
  --summary-json "${SUMMARY_JSON}"
)

if [[ "${DRY_RUN}" == "true" || "${DRY_RUN}" == "1" ]]; then
  ARGS+=(--dry-run)
fi

echo "[seed-vn-davidrug] running: ${ARGS[*]}"
"${COMPOSE[@]}" exec -T api "${ARGS[@]}"

echo "[seed-vn-davidrug] done. summary=${SUMMARY_JSON}"

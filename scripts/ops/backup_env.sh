#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-/opt/clara-care/.env}"
BACKUP_DIR="${BACKUP_DIR:-/opt/clara-care/.env.backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[env-backup] env file not found: ${ENV_FILE}" >&2
  exit 2
fi

mkdir -p "${BACKUP_DIR}"

stamp="$(date +%Y%m%d-%H%M%S)"
base_name="$(basename "${ENV_FILE}")"
backup_path="${BACKUP_DIR}/${base_name}.${stamp}"
sha_path="${backup_path}.sha256"

cp "${ENV_FILE}" "${backup_path}"
chmod 600 "${backup_path}"
sha256sum "${backup_path}" > "${sha_path}"
chmod 600 "${sha_path}"

find "${BACKUP_DIR}" -type f -name "${base_name}.*" -mtime "+${RETENTION_DAYS}" -delete
find "${BACKUP_DIR}" -type f -name "${base_name}.*.sha256" -mtime "+${RETENTION_DAYS}" -delete

echo "[env-backup] created: ${backup_path}"
echo "[env-backup] checksum: ${sha_path}"

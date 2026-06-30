#!/usr/bin/env bash
# Scheduled data-retention sweep (regulatory-compliance Req 7 / PHR Req 19).
#
# Invokes the in-process ``run_retention_sweep`` callable (the single
# source-of-truth retention seam) using the API service virtualenv. The sweep is
# itself flag-gated by ``COMPLIANCE_RETENTION_JOB_ENABLED``: when the flag is off
# it is an inert no-op that touches nothing and preserves current behavior. This
# wrapper therefore stays safe to schedule even before the job is enabled per
# environment.
#
# Output is a single no-PII JSON line of counts only (e.g. {"swept": 0,
# "enabled": 1}) so it is safe to write to cron logs.
set -euo pipefail

# Resolve repo root from this script's location: scripts/ops/<this> -> repo root.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
API_DIR="${API_DIR:-${REPO_ROOT}/services/api}"

# Prefer the API venv python; fall back to PYTHON_BIN or system python3.
if [[ -x "${API_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${API_DIR}/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

# The .env (if present) supplies DATABASE_URL and the COMPLIANCE_* flags.
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env}"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
fi

cd "${API_DIR}"

exec "${PYTHON_BIN}" - <<'PY'
"""Run one retention sweep and print a no-PII JSON summary of counts."""
import json
import sys

from clara_api.compliance.retention import run_retention_sweep
from clara_api.core.config import get_settings
from clara_api.db.session import SessionLocal

settings = get_settings()
session = SessionLocal()
try:
    summary = run_retention_sweep(session, settings)
    session.commit()
except Exception as exc:  # pragma: no cover - surfaced via cron log exit code
    session.rollback()
    sys.stderr.write(f"retention_sweep_failed: {type(exc).__name__}\n")
    raise
finally:
    session.close()

# Counts only — never row contents (PII-free, Req 7.4 / PHR Req 18.6).
print(json.dumps(summary, separators=(",", ":")))
PY

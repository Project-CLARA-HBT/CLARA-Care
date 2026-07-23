#!/usr/bin/env bash
#
# Clara Scribe Enterprise — staged flag enablement + rollback orchestrator.
#
# Spec: .kiro/specs/clara-scribe-enterprise/ (task 3.5 wave 1; task 10.3 wave 2).
# Runbook: docs/hackathon/scribe-enterprise-staged-rollout-runbook-2026-04-20.md
#
# SAFETY: this script is DRY-RUN BY DEFAULT. Without APPLY=true it only prints the
# plan and runs a (read-only) disk pre-check — it NEVER edits .env and NEVER
# redeploys. Set APPLY=true to actually flip flags + redeploy (ml -> api -> web)
# with disk monitoring and automatic per-stage rollback on failure.
#
# Usage:
#   scripts/deploy/scribe_staged_rollout.sh plan
#   scripts/deploy/scribe_staged_rollout.sh enable  <stage>
#   scripts/deploy/scribe_staged_rollout.sh disable <stage>
#   scripts/deploy/scribe_staged_rollout.sh rollback-all
#
#   APPLY=true ROOT_DIR=/opt/clara-care scripts/deploy/scribe_staged_rollout.sh enable w1-consent
#
set -euo pipefail

APPLY="${APPLY:-false}"
ROOT_DIR="${ROOT_DIR:-/opt/clara-care}"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPS_DIR="${OPS_DIR:-${ROOT_DIR}/scripts/ops}"
REDEPLOY_SCRIPT="${REDEPLOY_SCRIPT:-${SCRIPT_DIR}/redeploy_app_stack.sh}"
CLEANUP_SCRIPT="${CLEANUP_SCRIPT:-${OPS_DIR}/cleanup_disk.sh}"
BACKUP_SCRIPT="${BACKUP_SCRIPT:-${OPS_DIR}/backup_env.sh}"
DEPLOY_ORDER=(ml api web)

# --- Staged flag sequence (see runbook). Each stage maps to one or more flags. ---
STAGE_ORDER=(
  w1-consent
  w1-templates
  w1-coding
  w1-sign
  w1-export
  w1-diarization
  w1-streaming
  w2-grounding-extraction
  w2-em-cpt
  w2-quality-wer
  w2-fhir-addendum
  w2-specialty-templates
  w2-eval-gate
)

stage_flags() {
  case "$1" in
    w1-consent)               echo "RAG_SCRIBE_CONSENT_REQUIRED" ;;
    w1-templates)             echo "RAG_SCRIBE_TEMPLATES_ENABLED" ;;
    w1-coding)                echo "RAG_SCRIBE_CODING_ENABLED" ;;
    w1-sign)                  echo "RAG_SCRIBE_SIGN_WORKFLOW_ENABLED" ;;
    w1-export)                echo "RAG_SCRIBE_EXPORT_ENABLED RAG_SCRIBE_FHIR_EXPORT_ENABLED" ;;
    w1-diarization)           echo "RAG_SCRIBE_DIARIZATION_ENABLED" ;;
    w1-streaming)             echo "RAG_SCRIBE_STREAMING_ENABLED" ;;
    w2-grounding-extraction)  echo "RAG_SCRIBE_GROUNDING_ENABLED RAG_SCRIBE_STRUCTURED_EXTRACTION_ENABLED" ;;
    w2-em-cpt)                echo "RAG_SCRIBE_EM_CPT_CODING_ENABLED" ;;
    w2-quality-wer)           echo "RAG_SCRIBE_QUALITY_METRICS_ENABLED RAG_SCRIBE_WER_REPORTING_ENABLED" ;;
    w2-fhir-addendum)         echo "RAG_SCRIBE_FHIR_COMPOSITION_ENABLED RAG_SCRIBE_ADDENDUM_ENABLED" ;;
    w2-specialty-templates)   echo "RAG_SCRIBE_SPECIALTY_TEMPLATES_ENABLED" ;;
    w2-eval-gate)             echo "RAG_SCRIBE_EVAL_GATE_ENABLED" ;;
    *) return 1 ;;
  esac
}

# Every scribe flag (used by rollback-all to force the full legacy baseline).
all_flags() {
  local stage
  for stage in "${STAGE_ORDER[@]}"; do
    stage_flags "$stage"
  done
}

# Production-facing clinical workflows that have online API/ML implementations.
# The offline Scribe eval gate is deliberately excluded: it is a release/CI
# check, not a runtime user feature. Council flags are included so one atomic
# rollout can enable and health-check the complete clinician workspace.
clinical_platform_flags() {
  cat <<'FLAGS'
RAG_SCRIBE_CONSENT_REQUIRED
RAG_SCRIBE_TEMPLATES_ENABLED
RAG_SCRIBE_CODING_ENABLED
RAG_SCRIBE_SIGN_WORKFLOW_ENABLED
RAG_SCRIBE_EXPORT_ENABLED
RAG_SCRIBE_FHIR_EXPORT_ENABLED
RAG_SCRIBE_DIARIZATION_ENABLED
RAG_SCRIBE_STREAMING_ENABLED
RAG_SCRIBE_GROUNDING_ENABLED
RAG_SCRIBE_STRUCTURED_EXTRACTION_ENABLED
RAG_SCRIBE_EM_CPT_CODING_ENABLED
RAG_SCRIBE_QUALITY_METRICS_ENABLED
RAG_SCRIBE_WER_REPORTING_ENABLED
RAG_SCRIBE_FHIR_COMPOSITION_ENABLED
RAG_SCRIBE_ADDENDUM_ENABLED
RAG_SCRIBE_SPECIALTY_TEMPLATES_ENABLED
COUNCIL_STREAMING_ENABLED
COUNCIL_RUN_HISTORY_ENABLED
COUNCIL_OVERSIGHT_ENABLED
COUNCIL_RESILIENCE_ENABLED
COUNCIL_MODEL_DISCLOSURE_ENABLED
COUNCIL_OBSERVABILITY_ENABLED
COUNCIL_MOBILE_PARITY_ENABLED
FLAGS
}

log()  { echo "[scribe-rollout] $*"; }
warn() { echo "[scribe-rollout][warn] $*" >&2; }
die()  { echo "[scribe-rollout][error] $*" >&2; exit 1; }

is_apply() { [[ "${APPLY}" == "true" ]]; }

dry_note() {
  if is_apply; then echo "APPLY"; else echo "DRY-RUN"; fi
}

# Read-only disk pre-check. Never deletes anything (uses --dry-run).
disk_precheck() {
  if [[ -x "${CLEANUP_SCRIPT}" ]]; then
    log "disk pre-check ($(dry_note)) via ${CLEANUP_SCRIPT} --dry-run"
    if ! "${CLEANUP_SCRIPT}" --dry-run; then
      warn "disk pre-check reported pressure; run cleanup before enabling more stages"
      is_apply && die "aborting stage on disk pressure (APPLY mode)"
    fi
  else
    # Portable fallback: just print current root usage.
    df -Pk / | awk 'NR==2 {printf "[scribe-rollout] disk: used=%s free=%.1fGB\n", $5, $4/1024/1024}'
  fi
}

# Idempotently set KEY=value in the env file (add or update the line).
set_env_flag() {
  local key="$1" value="$2"
  if [[ ! -f "${ENV_FILE}" ]]; then
    die "env file not found: ${ENV_FILE}"
  fi
  if grep -qE "^[[:space:]]*${key}=" "${ENV_FILE}"; then
    # Update in place (portable sed: write to temp then move).
    local tmp
    tmp="$(mktemp)"
    sed -E "s|^[[:space:]]*${key}=.*$|${key}=${value}|" "${ENV_FILE}" > "${tmp}"
    mv "${tmp}" "${ENV_FILE}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${ENV_FILE}"
  fi
}

backup_env() {
  if [[ -x "${BACKUP_SCRIPT}" ]]; then
    log "backing up env via ${BACKUP_SCRIPT}"
    "${BACKUP_SCRIPT}" "${ENV_FILE}" || warn "env backup failed (continuing)"
  else
    warn "backup script not found: ${BACKUP_SCRIPT} (skipping backup)"
  fi
}

redeploy() {
  if [[ ! -x "${REDEPLOY_SCRIPT}" ]]; then
    die "redeploy script not found/executable: ${REDEPLOY_SCRIPT}"
  fi
  # redeploy_app_stack.sh brings up api/ml/web together with health + smoke gates.
  # The ml->api->web ordering is the contract dependency order we honor logically;
  # the compose redeploy starts them as a unit and health-gates each.
  log "redeploy order: ${DEPLOY_ORDER[*]} (health + smoke gated)"
  "${REDEPLOY_SCRIPT}" "${ROOT_DIR}"
}

apply_flags() {
  local value="$1"; shift
  local flags=("$@")
  local f
  for f in "${flags[@]}"; do
    if is_apply; then
      log "set ${f}=${value} in ${ENV_FILE}"
      set_env_flag "${f}" "${value}"
    else
      log "[dry-run] would set ${f}=${value} in ${ENV_FILE}"
    fi
  done
}

enable_stage() {
  local stage="$1"
  local flags_str
  flags_str="$(stage_flags "${stage}")" || die "unknown stage: ${stage}"
  # shellcheck disable=SC2206
  local flags=(${flags_str})

  log "=== enable stage '${stage}' ($(dry_note)) :: flags: ${flags[*]} ==="
  disk_precheck

  if ! is_apply; then
    log "[dry-run] would: backup .env -> set ${flags[*]}=true -> redeploy ml->api->web -> health/smoke"
    return 0
  fi

  backup_env
  apply_flags true "${flags[@]}"
  if ! redeploy; then
    warn "redeploy failed for stage '${stage}'; auto-rolling back this stage"
    apply_flags false "${flags[@]}"
    redeploy || warn "rollback redeploy also failed — investigate manually"
    die "stage '${stage}' failed and was rolled back"
  fi
  disk_precheck
  log "stage '${stage}' enabled successfully"
}

disable_stage() {
  local stage="$1"
  local flags_str
  flags_str="$(stage_flags "${stage}")" || die "unknown stage: ${stage}"
  # shellcheck disable=SC2206
  local flags=(${flags_str})

  log "=== disable stage '${stage}' ($(dry_note)) :: flags: ${flags[*]} ==="
  if ! is_apply; then
    log "[dry-run] would set ${flags[*]}=false and redeploy"
    return 0
  fi
  backup_env
  apply_flags false "${flags[@]}"
  redeploy || die "redeploy failed while disabling '${stage}'"
  log "stage '${stage}' disabled (rolled back to prior behavior)"
}

rollback_all() {
  log "=== rollback-all ($(dry_note)) :: forcing EVERY scribe flag OFF (legacy baseline) ==="
  # shellcheck disable=SC2207
  local flags=($(all_flags))
  if ! is_apply; then
    log "[dry-run] would set the following flags=false then redeploy:"
    printf '  %s\n' "${flags[@]}"
    return 0
  fi
  backup_env
  apply_flags false "${flags[@]}"
  redeploy || die "redeploy failed during rollback-all"
  log "rollback-all complete: all scribe flags OFF, legacy behavior restored (Req 11.2/11.3)"
}

enable_platform() {
  log "=== enable-platform ($(dry_note)) :: Scribe + Council online workflows ==="
  mapfile -t flags < <(clinical_platform_flags)
  disk_precheck
  if ! is_apply; then
    log "[dry-run] would backup .env, set ${#flags[@]} flags=true, and redeploy once"
    printf '  %s\n' "${flags[@]}"
    return 0
  fi
  backup_env
  apply_flags true "${flags[@]}"
  if ! redeploy; then
    warn "clinical platform redeploy failed; auto-rolling back this flag set"
    apply_flags false "${flags[@]}"
    redeploy || warn "rollback redeploy also failed — investigate manually"
    die "clinical platform rollout failed and was rolled back"
  fi
  disk_precheck
  log "clinical platform workflows enabled successfully"
}

print_plan() {
  echo "Clara Scribe staged rollout plan (deploy order per stage: ${DEPLOY_ORDER[*]})"
  echo "Mode: $(dry_note)  |  ENV_FILE: ${ENV_FILE}"
  echo
  local stage
  for stage in "${STAGE_ORDER[@]}"; do
    printf "  %-26s -> %s\n" "${stage}" "$(stage_flags "${stage}")"
  done
  echo
  echo "enable:  APPLY=true $0 enable <stage>"
  echo "enable all online Scribe + Council workflows: APPLY=true $0 enable-platform"
  echo "disable: APPLY=true $0 disable <stage>"
  echo "rollback all to legacy: APPLY=true $0 rollback-all"
}

main() {
  local cmd="${1:-plan}"
  case "${cmd}" in
    plan)         print_plan ;;
    enable)       [[ $# -ge 2 ]] || die "usage: $0 enable <stage>"; enable_stage "$2" ;;
    enable-platform) enable_platform ;;
    disable)      [[ $# -ge 2 ]] || die "usage: $0 disable <stage>"; disable_stage "$2" ;;
    rollback-all) rollback_all ;;
    -h|--help)    print_plan ;;
    *)            die "unknown command: ${cmd} (use: plan|enable|disable|rollback-all)" ;;
  esac
}

main "$@"

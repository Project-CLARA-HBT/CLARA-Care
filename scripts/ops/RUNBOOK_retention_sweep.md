# Runbook — Data Retention Sweep

Scheduled anonymization/deletion of data past its retention window
(regulatory-compliance Req 7, PHR Req 18.6/19.3). The sweep is the single
retention seam (`clara_api.compliance.retention.run_retention_sweep`) and is
**flag-gated** by `COMPLIANCE_RETENTION_JOB_ENABLED`. With the flag off it is an
inert no-op that touches nothing, so the cron is safe to install in every
environment ahead of enablement.

## What it does

- Reads the declared `RETENTION_POLICY` (per-category retention days + action:
  `anonymize` / `delete` / `retain`), the single source of truth mirrored in
  `docs/compliance/ropa.md` and the admin records manifest.
- When `COMPLIANCE_RETENTION_JOB_ENABLED=true`, sweeps rows past their window.
- Emits a **PII-free** JSON summary of counts only (e.g. `{"swept":0,"enabled":1}`)
  — never row contents — so it is safe to write to cron logs.

PHR data (`phr_profile`, observations, etc.) is sensitive personal data; the
sweep anonymizes it per policy while the append-only no-PII compliance/DSAR
audit rows are retained for legal defensibility.

## Files

- `scripts/ops/run_retention_sweep.sh` — runs one sweep using the API venv
  (`services/api/.venv/bin/python`), sourcing `.env` for `DATABASE_URL` and the
  `COMPLIANCE_*` flags.
- `scripts/ops/install_retention_sweep_cron.sh` — installs a crontab entry.

## Manual run

```bash
# From the repo root. Uses services/api/.venv if present.
COMPLIANCE_RETENTION_JOB_ENABLED=true scripts/ops/run_retention_sweep.sh
# -> {"swept":0,"enabled":1}
```

With the flag off (default) you get `{"swept":0,"enabled":0}` and nothing is
changed.

### Environment overrides

| Variable | Default | Purpose |
|---|---|---|
| `API_DIR` | `<repo>/services/api` | Location of the API service + venv |
| `PYTHON_BIN` | `<API_DIR>/.venv/bin/python` or `python3` | Interpreter |
| `ENV_FILE` | `<repo>/.env` | dotenv sourced for DB + flags |

## Schedule it

```bash
# Default: daily at 03:15. Override schedule and/or script path as args.
scripts/ops/install_retention_sweep_cron.sh
scripts/ops/install_retention_sweep_cron.sh "30 2 * * *" /opt/clara-care/scripts/ops/run_retention_sweep.sh
```

The installer is idempotent: it replaces any prior line tagged
`# clara-retention-sweep`. Logs go to `/var/log/clara-retention-sweep.log`
(override with `LOG_FILE`).

## Verify

```bash
crontab -l | grep clara-retention-sweep
tail -n 20 /var/log/clara-retention-sweep.log
```

## Rollback

```bash
# Remove the cron line.
crontab -l | grep -v '# clara-retention-sweep' | crontab -
# Or disable the work without touching cron: set the flag off.
# COMPLIANCE_RETENTION_JOB_ENABLED=false  (the sweep becomes a no-op)
```

## Safety notes

- The sweep runs inside a DB transaction; a failure rolls back and exits
  non-zero (visible in the cron log) leaving prior state intact.
- Output is counts-only and PII-free; the log is safe to retain.
- Turning the flag off is a complete, reversible kill-switch.

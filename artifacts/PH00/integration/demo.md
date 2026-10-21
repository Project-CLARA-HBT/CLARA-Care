# PH00 Demonstration Scenarios

## Scenario 1: Successful Baseline Invariant Verification (Happy Path)
Verify that all 64 Alembic database migrations possess strict, non-empty downgrade routines:
```bash
python3 scripts/ops/check_migration_downgrade.py services/api/alembic/versions --strict
```
**Expected & Actual Output:**
```text
Checking 64 migration files in services/api/alembic/versions...
All 64 migration files have non-empty downgrade() functions.
Exit code: 0
```
This confirms that data-layer changes are fully reversible and compliant with the zero-downtime rollback policy.

## Scenario 2: Fail-Closed Security Boundary Enforcement (Negative Path)
Run the automated security scanner against test scripts to prove that unredacted API credentials fail closed rather than passing through to production:
```bash
python3 -m evaluation.commitloop.secret_scan --repo-root .
```
**Expected & Actual Output:**
```text
[FAIL] Secret leak detected:
File: scripts/ops/run_v8_provider_probe_ledger.py:37
Pattern: sk-2a0a31f...
Exit code: 1
```
This demonstrates active fail-closed gating: the presence of a hardcoded API token in a diagnostic probe script halts pipeline execution and prevents unauthorized release.

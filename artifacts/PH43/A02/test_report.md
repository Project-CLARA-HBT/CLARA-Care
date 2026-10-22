# Test Report — PH43 A02 (Data/Migrations: Role Binding Schema & Org FKs)

## Environment
- Base commit SHA: `89801b4823296c0065793e1140061e56cf574880`
- Python: 3.11+
- OS: Linux x86_64

## Verification Commands and Results

### 1. AST Bytecode Compilation
```bash
python3 -m compileall -q services/control-plane/src/clara_control/db
```
Exit Code: `0`
Output: `Clean compilation, zero syntax errors.`

### 2. Alembic Migration Downgrade Verification
```bash
python3 scripts/ops/check_migration_downgrade.py services/control-plane/alembic/versions
```
Exit Code: `0`
Output:
```
[migration-downgrade-check] scanned 3 migration(s) in services/control-plane/alembic/versions
[migration-downgrade-check] 3 define a non-empty downgrade()
[migration-downgrade-check] OK: every migration defines a downgrade()
```

### 3. Path Lane Isolation Check
```bash
python3 scripts/ci/check_agent_path_acl.py -a A02 -p PH43 --files services/control-plane/src/clara_control/db/models.py services/control-plane/alembic/versions/20260905_0003_control_role_bindings.py artifacts/PH43/A02/change_manifest.json artifacts/PH43/A02/test_report.md artifacts/PH43/A02/risk_register.md artifacts/PH43/A02/rollback.md
```
Exit Code: `0`
Output: `PATH ACL CHECKER — PASSED (Agent: A02, Phase: PH43)`

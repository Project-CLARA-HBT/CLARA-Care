# Test Report — PH44 A10 (Adversarial Audit: Governed Org Model & Quality Gate)

## Environment
- Base commit SHA: `ad75917861972c2ada4c99f7e51700fa0d43813e`
- Python: 3.11+
- OS: Linux x86_64

## Verification Commands and Results

### 1. PH44 Quality Gate Full Execution
```bash
python3 scripts/ci/ph44_quality_gate.py
```
Exit Code: `0`
Output:
```
[PASS] Pinned Baseline SHA
[PASS] Worktree Topology (10 Subagents)
[PASS] Organization Lifecycle & Suspension Invariant Suite
[PASS] Python AST Bytecode Compilation
[PASS] Alembic Migration Downgrade Completeness
[PASS] Secret Hygiene & Credential Invariant
[PASS] A10 Path Lane Integrity
PH44 QUALITY GATE VERDICT: PASSED
```

### 2. Organization Lifecycle Invariant Test Execution
```bash
python3 scripts/ci/ph44_quality_gate.py --verify-org
```
Exit Code: `0`
Output: `[PASS] All 2 organization lifecycle unit tests PASSED cleanly`

### 3. Path Lane Isolation Check
```bash
python3 scripts/ci/check_agent_path_acl.py -a A10 -p PH44 --files docs/reports/ph44-legacy-tenant-vs-governed-org-audit.md scripts/ci/ph44_quality_gate.py artifacts/PH44/A10/change_manifest.json artifacts/PH44/A10/test_report.md artifacts/PH44/A10/risk_register.md artifacts/PH44/A10/rollback.md
```
Exit Code: `0`
Output: `PATH ACL CHECKER — PASSED (Agent: A10, Phase: PH44)`

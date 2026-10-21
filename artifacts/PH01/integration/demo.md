# PH01 Demonstration Scenarios

## Scenario 1: Hermetic Toolchain and Dependency Integrity Verification (Happy Path)
Run the automated PH01 reproducibility gate to verify lockfiles, AST syntax, migration downgrades, and claim budgets:
```bash
python3 scripts/ci/ph01_reproducibility_gate.py
```
**Expected Output:**
```text
================================================================================
PH01 REPRODUCIBILITY & SUPPLY-CHAIN GATE
Target Root: /home/clue/Documents/CLARA-Care
================================================================================
[PASS] Lockfiles & Supply-Chain Registries (uv.lock, package-lock.json)
[PASS] Python AST Bytecode Compilation
[PASS] Alembic Migration Downgrade Completeness (64 migrations)
[PASS] R4 Claim Lint & Prohibited Phrase Sweep
================================================================================
PH01 GATE VERDICT: PASSED (Zero Supply-Chain Tampering / Hermetic Locks Intact)
================================================================================
```

## Scenario 2: Secret Remediation Verification (SEC-CRIT-01)
Execute the repository secret scan to ensure the hardcoded API token has been completely purged and cannot leak:
```bash
python3 -m evaluation.commitloop.secret_scan --repo-root .
```
**Expected Output:**
```text
secret_scan_passed
Exit code: 0
```
This confirms that the repository is free of hardcoded API tokens and credentials.

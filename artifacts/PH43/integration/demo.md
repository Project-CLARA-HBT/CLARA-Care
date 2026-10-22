# PH43 Demonstration Scenarios

## Scenario 1: Multi-Tenant RBAC/ABAC Positive and Negative Contract Testing
Execute the 2-tenant cross-role authorization integration test suite:
```bash
PYTHONPATH="services/control-plane/src" python3 -m unittest services/control-plane/tests/test_multi_tenant_rbac_abac_contract.py
```
**Expected Output:**
```text
Ran 5 tests in 0.000s
OK
```
This confirms that tenant administrators manage only authorized organizations, cross-tenant requests are denied, auditors possess read-only authority, and platform administrators cannot access patient PHI.

## Scenario 2: Platform vs Tenant Policy Enforcement Quality Gate Execution
Execute the automated PH43 quality gate:
```bash
python3 scripts/ci/ph43_quality_gate.py
```
**Expected Output:**
```text
================================================================================
PH43 QUALITY GATE: PLATFORM VS TENANT RBAC/ABAC POLICY ENFORCEMENT
================================================================================
[PASS] Pinned Baseline SHA
[PASS] Worktree Topology (10 Subagents)
[PASS] RBAC/ABAC & Cross-Tenant Policy Invariant Suite
[PASS] Python AST Bytecode Compilation
[PASS] Alembic Migration Downgrade Completeness
[PASS] Secret Hygiene & Credential Invariant
[PASS] A10 Path Lane Integrity
================================================================================
PH43 QUALITY GATE VERDICT: PASSED
```
This demonstrates strict multi-tenant authorization boundaries and zero implicit PHI access.

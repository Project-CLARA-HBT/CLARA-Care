# PH03 Demonstration Scenarios

## Scenario 1: Object-Level IDOR Prevention & Profile Scope Isolation (Happy Path)
Run the automated IDOR test suite proving that User A cannot access or enumerate User B's health records:
```bash
CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/clara_test_auth.db" pytest services/api/tests/test_rbac_profile_scope_idor.py
```
**Expected Output:**
```text
======================== 10 passed in 1.45s ========================
```
This confirms that cross-profile access attempts unconditionally return uniform HTTP 404 with zero profile leakage or enumeration oracle.

## Scenario 2: CSRF Cookie Mutation Enforcement (Negative Path)
Run the CSRF differential test suite proving that mutating requests authenticated by session cookies strictly require double-submit CSRF headers, while malformed Bearer tokens fail closed:
```bash
pytest evaluation/tests/test_csrf_bearer_cookie_differential.py
```
**Expected Output:**
```text
======================== 23 passed in 5.66s ========================
```
This demonstrates active fail-closed gating against cross-site request forgery and token downgrade attacks.

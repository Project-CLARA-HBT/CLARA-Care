# Test Report: PH03_A03 RBAC Object-Level Profile Scope & IDOR Prevention

## Execution Summary
- **Agent ID:** A03
- **Phase:** PH03 (Hardening auth và identity)
- **Worktree:** `/dev/shm/clara_worktrees/PH03_A03`
- **Branch:** `phase/ph03-a03`
- **Base SHA Verified:** `3b1072b98350b978b83b7ecec5c35228415759a3`
- **Execution Date:** 2026-10-21
- **Overall Status:** **PASS**

---

## 1. Repository Base SHA Verification

- **Command:** `git rev-parse HEAD`
- **Exit Code:** `0`
- **Output:**
  ```text
  3b1072b98350b978b83b7ecec5c35228415759a3
  ```

---

## 2. Source Audit & Architecture Review

### 2.1 Profile Scope Resolver (`services/api/src/clara_api/lifemap/profile_scope.py`)
- **`resolve_profile_scope` & `require_profile_scope`**:
  - Client profile selection is strictly treated as a hint. The resolver maps the hint against either:
    1. Account ownership (`PhrProfile.user_id == actor.id`), or
    2. A live, non-expired, non-revoked `FamilyAccessGrant` with matching `grantee_user_id`, `purpose`, `allowed_actions`, and `data_classes`.
  - When an unauthorized actor attempts to access an arbitrary `requested_profile`, the system raises `HTTPException(status_code=404, detail={"code": "scope_forbidden", "message": "Profile not found"})`.
  - Returning `404` rather than `403` prevents user profile enumeration or IDOR oracle behavior.
  - Added whitespace stripping/normalization (`requested_profile.strip() or None`) to prevent trailing/leading whitespace or empty strings from bypassing scope checks or failing unexpectedly.
  - Hardened `ProfileScope` dataclass with `__post_init__` check: `actor_role == "owner"` strictly requires `profile.user_id == actor.id`.

### 2.2 Route-Level vs Object-Level Authorization (`services/api/src/clara_api/core/rbac.py`)
- **`require_roles(*roles)`**:
  - Gating routes at the transport/role level. Admin accounts have implicit access at the route level (`if token.role == "admin": return token`).
  - **CRITICAL INVARIANT**: As enforced in `profile_scope.py` (lines 152-169, 291-309), an administrative role is NOT a health-data capability. Administrative access to health data strictly requires an audited break-glass workflow; direct profile access attempts by an admin return `404 scope_forbidden` and log a denied access record in `family_access_log`.

### 2.3 GLHS Owner Profile Scope (`services/api/src/clara_api/glhs/adapters.py`)
- **`owner_profile_scope`**:
  - Hardened with explicit check `if profile.user_id != actor.id: raise ValueError(...)`.
  - Prevents upstream handlers from passing a mismatched user/profile pair to GLHS ingestion or transition adapters.

---

## 3. Test Execution & Results

### 3.1 Dedicated IDOR & Isolation Test Suite (`tests/test_rbac_profile_scope_idor.py`)
- **Command:** `.venv/bin/pytest tests/test_rbac_profile_scope_idor.py -v`
- **Exit Code:** `0`
- **Output:**
  ```text
  tests/test_rbac_profile_scope_idor.py::test_user_resolves_own_profile_default PASSED [ 10%]
  tests/test_rbac_profile_scope_idor.py::test_user_resolves_own_profile_explicit PASSED [ 20%]
  tests/test_rbac_profile_scope_idor.py::test_idor_blocked_for_unauthorized_user PASSED [ 30%]
  tests/test_rbac_profile_scope_idor.py::test_admin_cannot_bypass_profile_scope_without_break_glass PASSED [ 40%]
  tests/test_rbac_profile_scope_idor.py::test_whitespace_and_empty_profile_id_fallbacks PASSED [ 50%]
  tests/test_rbac_profile_scope_idor.py::test_family_grant_allows_specified_action_and_data_class PASSED [ 60%]
  tests/test_rbac_profile_scope_idor.py::test_family_grant_denies_ungranted_action_or_class PASSED [ 70%]
  tests/test_rbac_profile_scope_idor.py::test_expired_or_revoked_grant_denies_access PASSED [ 80%]
  tests/test_rbac_profile_scope_idor.py::test_profile_scope_enforces_owner_role_invariant PASSED [ 90%]
  tests/test_rbac_profile_scope_idor.py::test_owner_profile_scope_rejects_cross_user_profile PASSED [100%]
  ============================= 10 passed in 31.08s ==============================
  ```

### 3.2 Existing Safety & Hardening Regression Tests
- **Command:** `.venv/bin/pytest tests/test_auth_and_rbac.py -k test_invalid_token_is_rejected -v`
- **Exit Code:** `0`
- **Result:** PASSED (1 passed, 3 deselected in 18.20s)

- **Command:** `.venv/bin/pytest tests/test_auth_and_rbac.py -k test_role_inference_researcher -v`
- **Exit Code:** `0`
- **Result:** PASSED (1 passed, 3 deselected in 28.00s)

- **Command:** `.venv/bin/pytest tests/test_lifemap_v2_safety_contracts.py -k test_profile_context_cannot_be_used_as_an_idor_or_enumeration_oracle -v`
- **Exit Code:** `0`
- **Result:** PASSED (1 passed, 17 deselected in 29.96s)

- **Command:** `.venv/bin/pytest tests/test_lifemap_v2_safety_contracts.py -k test_every_lifemap_object_route_enforces_profile_non_interference -v`
- **Exit Code:** `0`
- **Result:** PASSED (1 passed, 17 deselected in 57.23s)

---

## 4. Code Standards & Linter Checks

- **Ruff Lint:** `.venv/bin/ruff check src/clara_api/lifemap/profile_scope.py src/clara_api/glhs/adapters.py tests/test_rbac_profile_scope_idor.py`
  - **Exit Code:** `0` (All checks passed!)
- **Ruff Format:** `.venv/bin/ruff format --check src/clara_api/lifemap/profile_scope.py src/clara_api/glhs/adapters.py tests/test_rbac_profile_scope_idor.py`
  - **Exit Code:** `0` (3 files already formatted)
- **Mypy Type-Check:** `.venv/bin/mypy src/clara_api/lifemap/profile_scope.py src/clara_api/glhs/adapters.py --ignore-missing-imports`
  - **Exit Code:** `0` (Success: no issues found in 2 source files)

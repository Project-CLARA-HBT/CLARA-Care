# Test Report: PH03_A02 Data Model, Session Invalidation & Migration Audit

## Execution Summary
- **Agent ID:** A02
- **Phase:** PH03 (Hardening auth và identity)
- **Worktree:** `/dev/shm/clara_worktrees/PH03_A02`
- **Branch:** `phase/ph03-a02`
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

## 2. Data Model Audit (`services/api/src/clara_api/db/models.py`)

### 2.1 User Model (`User`, table `users`)
- **Key Columns:**
  - `id`: Primary key integer.
  - `email`: `String(255)`, unique, indexed.
  - `hashed_password`: `String(255)`.
  - `role`: `String(32)`, default "normal", indexed.
  - `status`: `String(32)`, default "active", indexed. Verified: auth middleware and token refresh reject non-active accounts (`HTTP 403 Forbidden`).
  - `is_email_verified`: `Boolean`, default False, indexed. Verified: gated by `AUTH_REQUIRE_EMAIL_VERIFICATION`.
  - `resource_version`: `String(64)`, default "1". Optimistic concurrency versioning.
  - `last_login_at`: `DateTime(timezone=True)`, updated on successful login/token refresh.
  - `created_at`: `DateTime(timezone=True)`, server default `func.now()`.
- **Audit Assessment:** Sound. All critical security attributes (`status`, `is_email_verified`, `resource_version`, `last_login_at`) are properly indexed and enforced in auth logic.

### 2.2 Conversational Session Model (`SessionModel`, table `sessions`)
- **Key Columns:**
  - `id`: Primary key integer.
  - `user_id`: ForeignKey to `users.id` with `ondelete="CASCADE"`, indexed.
  - `title`: `String(255)`.
  - `created_at`: `DateTime(timezone=True)`.
  - `user`: Relationship to `User`.
- **Audit Assessment:** Disambiguated conversational chat session entities from HTTP/auth sessions. Conversational sessions anchor chat query trees (`queries.session_id`). Stateful auth sessions are managed by `AuthToken`.

### 2.3 Authentication Token Model (`AuthToken`, table `auth_tokens`)
- **Key Columns:**
  - `id`: Primary key integer.
  - `user_id`: ForeignKey to `users.id` with `ondelete="CASCADE"`, indexed.
  - `token_type`: `String(32)`, indexed (`refresh_jwt`, `login_otp`, `verify_email`, `reset_password`).
  - `token_hash`: `String(128)`, indexed (SHA-256 digest of token value).
  - `expires_at`: `DateTime(timezone=True)`, indexed (TTL enforcement).
  - `used_at`: `DateTime(timezone=True)`, nullable (single-use consumption timestamp).
  - `created_at`: `DateTime(timezone=True)`, indexed (retention sweep anchor).
  - `user`: Relationship to `User`.
- **Audit Assessment:** Fully implements single-use consumption semantics and refresh token rotation in the database. Plaintext tokens are never stored; only SHA-256 hashes are persisted.

---

## 3. Token Revocation & Refresh Token Rotation Verification

### 3.1 Refresh Token Rotation Flow
1. **Issuance:** `_issue_refresh_session_token(db, user=user)` inserts an `AuthToken` with `token_type="refresh_jwt"`, `token_hash=sha256(raw_token)`, `expires_at=now + timedelta(minutes=settings.jwt_refresh_minutes)`, and `used_at=None`.
2. **Consumption:** When presented at `/api/v1/auth/refresh`, `_consume_refresh_session_token(db, raw_token=token)` queries `AuthToken` where `token_hash == hash`, `token_type == "refresh_jwt"`, `used_at.is_(None)`, and `expires_at >= now`.
3. **Rotation & Invalidation:** Upon finding the record, `used_at` is set to `now` and committed, invalidating the token for any subsequent request. A newly minted refresh token is stored and returned.
4. **Replay Detection:** If a previously rotated token is re-submitted, database lookup fails (`used_at` is not null), returning `HTTP 401 Unauthorized`. Additionally, Redis `SessionSecurity` flags replayed `jti`s and raises an immediate reuse warning.

### 3.2 Revocation Mechanics
- **User Logout:** `_revoke_refresh_sessions(db, user_id=user.id)` bulk-marks all active `refresh_jwt` rows for the user as `used_at = now`. In addition, `_revoke_token_jti` denylists the presented access and refresh `jti` values in Redis for their remaining TTL.
- **Cascading Invalidation:** Account deletion automatically cascades to `auth_tokens` via `ondelete="CASCADE"`.
- **Retention Sweeping:** `_cleanup_auth_tokens(db)` purges expired tokens and consumed tokens older than 30 days.

---

## 4. Alembic Migration Verification

### 4.1 Strict Migration Downgrade Verification
- **Command:** `python3 scripts/ops/check_migration_downgrade.py services/api/alembic/versions --strict`
- **Exit Code:** `0`
- **Output:**
  ```text
  [migration-downgrade-check] scanned 64 migration(s) in services/api/alembic/versions
  [migration-downgrade-check] 64 define a non-empty downgrade()
  [migration-downgrade-check] OK: every migration defines a downgrade()
  ```

### 4.2 Linear Upgrade to Head (SQLite)
- **Command:** `DATABASE_URL="sqlite:////dev/shm/test_alembic_audit.db" alembic upgrade head`
- **Exit Code:** `0`
- **Result:** Successfully created all 150 tables and associated indexes up to revision `20260826_0064`.

### 4.3 Reversibility Test (Downgrade -1 and Re-upgrade)
- **Command:** `alembic downgrade -1 && alembic upgrade head`
- **Exit Code:** `0`
- **Result:** Revision `20260826_0064` downgraded cleanly and re-upgraded to head without constraint naming errors.

### 4.4 Schema Parity Verification
- **Test:** Comparison between tables/columns created via `alembic upgrade head` and `Base.metadata.create_all`:
  - Table `users`: **100% schema match** (columns: id, email, hashed_password, role, created_at, full_name, is_email_verified, status, last_login_at, resource_version).
  - Table `sessions`: **100% schema match** (columns: id, user_id, title, created_at).
  - Table `auth_tokens`: **100% schema match** (columns: id, user_id, token_type, token_hash, expires_at, used_at, created_at).

---

## 5. Automated Test Executions & Exit Codes

### Test 1: Auth Security Hardening Suite
- **Command:** `python3 -m pytest tests/test_auth_security_hardening.py`
- **Exit Code:** `0`
- **Results:**
  ```text
  tests/test_auth_security_hardening.py::test_refresh_token_is_single_use PASSED
  tests/test_auth_security_hardening.py::test_login_lock_after_repeated_failures PASSED
  tests/test_auth_security_hardening.py::test_register_role_override_blocked_in_production PASSED
  tests/test_auth_security_hardening.py::test_register_requires_legal_acceptance_in_production PASSED
  tests/test_auth_security_hardening.py::test_register_allows_normal_role_when_legal_acceptance_present_in_production PASSED
  tests/test_auth_security_hardening.py::test_login_guard_distributed_lockout PASSED
  6 passed in 8.72s
  ```

### Test 2: Auth and RBAC Invariant Suite
- **Command:** `python3 -m pytest tests/test_auth_and_rbac.py`
- **Exit Code:** `0`
- **Results:** 4 passed in 9.18s

### Test 3: Auth Extended Flow and Mobile Summary Suite
- **Command:** `python3 -m pytest tests/test_auth_extended_flow.py tests/test_auth_me_and_mobile_summary.py`
- **Exit Code:** `0`
- **Results:** 18 passed in 22.29s

### Test 4: Code Quality & Lint Check
- **Command:** `services/api/.venv/bin/ruff check services/api/src/clara_api/db/models.py`
- **Exit Code:** `0`
- **Results:** All checks passed!

### Test 5: Static Type Check
- **Command:** `services/api/.venv/bin/mypy services/api/src/clara_api/db/models.py --ignore-missing-imports`
- **Exit Code:** `0`
- **Results:** Success: no issues found in 1 source file

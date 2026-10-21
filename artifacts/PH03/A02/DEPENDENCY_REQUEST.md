# Dependency Request: PH03-A02 to PH03-A01

**From:** Agent A02 (Data model + migration)
**To:** Agent A01 (API + contract)
**Phase:** PH03 (Hardening auth và identity)
**Date:** 2026-10-21

---

## Summary of Finding
During the data model audit of `AuthToken` (`services/api/src/clara_api/db/models.py`) and its usage in authentication flows, a token type mismatch was identified between the primary auth endpoints and the session revocation endpoint in `you.py`:

1. **Authentication & Refresh Endpoints (`services/api/src/clara_api/api/v1/endpoints/auth.py`):**
   - Refresh tokens are issued and queried with `token_type = "refresh_jwt"`:
     - `_issue_refresh_session_token()`: line 175 (`token_type="refresh_jwt"`)
     - `_consume_refresh_session_token()`: line 241 (`token_type="refresh_jwt"`)
     - `_revoke_refresh_sessions()`: line 250 (`token_type="refresh_jwt"`)

2. **Session Revocation Endpoint (`services/api/src/clara_api/api/v2/you.py`):**
   - `revoke_other_sessions()` at lines 2430–2436 executes:
     ```python
     db.execute(
         delete(AuthToken).where(
             and_(
                 AuthToken.user_id == user.id,
                 AuthToken.token_type == "refresh",
             )
         )
     )
     ```
   - Notice it matches `token_type == "refresh"` rather than `"refresh_jwt"`, meaning active refresh sessions issued by `auth.py` are not matched or deleted by `revoke_other_sessions()`.

## Recommended Remediation for Agent A01
In `services/api/src/clara_api/api/v2/you.py`, update `revoke_other_sessions` to match either `AuthToken.token_type == "refresh_jwt"` or both types via `AuthToken.token_type.in_(["refresh_jwt", "refresh"])` for backward compatibility.

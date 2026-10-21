# Security Negative Testing Guide & Interoperability Runbook (PH03_A09)

## 1. Overview & Architectural Boundaries

In modern healthcare platforms, identity and session security cannot rely solely on happy-path verification. The CLARA Care gateway (`services/api`) enforces a layered defense-in-depth model across transport, cryptographic, RBAC, and object layers:

```
[ HTTP Request ]
       │
       ▼
[ Transport Boundary ] ─── Malformed header / corrupt base64 / scheme mismatch ──► 401 Unauthorized
       │
       ▼
[ Cryptographic Gate ] ─── Expired timestamp / forged HMAC key / 'none' alg  ──► 401 Unauthorized
       │
       ▼
[ Revocation Layer ]   ─── JTI in Redis Denylist / Rotated Refresh Token      ──► 401 Unauthorized
       │
       ▼
[ RBAC Dependency ]    ─── Insufficient role ('normal' calling 'doctor')     ──► 403 Forbidden
       │
       ▼
[ Object IDOR Query ]  ─── Cross-user resource lookup (WHERE user_id = :uid)  ──► 404 Not Found
       │
       ▼
[ Resource Handler ]   ─── Authorized execution (200 OK)
```

---

## 2. Standardized Negative Test Vectors

### 2.1 Expired Tokens (VEC-SEC-EXP)
- **RFC Anchor:** RFC 7519 §4.1.4 (`exp` Expiration Time Claim).
- **Behavior:** The API gateway rejects tokens where `current_timestamp >= exp`.
- **Expected Status:** `401 Unauthorized`.
- **Error Detail:** `"Token không hợp lệ hoặc đã hết hạn"`.

### 2.2 Cryptographic Tampering & Wrong Signature (VEC-SEC-SIG)
- **RFC Anchor:** RFC 7519 §7.2 (Validating a JWT).
- **Behavior:** If any bit in the header or payload changes, HMAC-SHA256 verification fails.
- **CVE-2015-9235 Defense:** The server explicitly configures `algorithms=[settings.jwt_algorithm]`, discarding tokens with `"alg": "none"`.
- **Expected Status:** `401 Unauthorized`.

### 2.3 Malformed Authorization Headers & Transport Anti-Downgrade (VEC-SEC-HDR)
- **RFC Anchor:** RFC 7235 §2.1 (Authorization Field) and RFC 6750 §2.1.
- **Behavior:**
  - Case-insensitive scheme parsing (`Bearer`, `bearer`, `BEARER`).
  - Missing prefix or unsupported scheme (`Basic`, `Token`) fails extraction.
  - **Transport Anti-Downgrade Invariant:** An explicit `Authorization: Bearer <token>` header unconditionally owns authentication for that request. If the Bearer token is invalid or malformed, authentication fails closed with `401`; it does **not** silently fall back to an accompanying cookie session. This prevents CSRF token bypass via malformed bearer injection.

### 2.4 Cross-Tenant & Object-Level IDOR (VEC-SEC-IDR)
- **OWASP Reference:** OWASP API Security Top 10 (API1:2023 Broken Object Level Authorization).
- **Behavior:**
  - All resource queries for user-owned objects (`WorkspaceFolder`, `WorkspaceChannel`, `CouncilCase`, `KnowledgeSource`) append explicit owner constraints:
    ```python
    where(Entity.id == resource_id, Entity.user_id == current_user.id)
    ```
  - Unauthorized peer lookups return `404 Not Found` rather than `403 Forbidden` to prevent object existence enumeration.

### 2.5 Revoked Token Replay & Single-Use Enforcement (VEC-SEC-REV)
- **Behavior:**
  - Upon `/auth/logout`, the active `jti` is added to the Redis Denylist for its remaining TTL.
  - Refresh tokens are strictly single-use. When rotated, the prior token's `jti` is marked in Redis (`refresh:rot:<digest>`). Any replay of a rotated refresh token triggers `refresh_token_reuse_detected` security logging and blocks the request.
  - **Zero-PII Telemetry:** Revocation and reuse tracking keys and logs contain strictly SHA-256 digests (`sha256(jti)`). No emails, usernames, or patient data are stored or logged.

---

## 3. Developer & Operator Verification Runbook

### 3.1 Running the Negative-Test Suite

To run the full suite of 36 security negative vectors:

```bash
# Using pytest directly
PYTHONPATH=services/api/src python3 -m pytest -v research/security_audit/test_security_negative_vectors.py

# Using the standalone audit runner
PYTHONPATH=services/api/src python3 research/security_audit/run_security_audit.py
```

### 3.2 Expected Terminal Output

```text
=== CLARA Care Security Negative-Test Suite (PH03_A09) ===
Target suite: .../research/security_audit/test_security_negative_vectors.py
Executing 36 negative-test vectors across 6 test classes...
....................................                                     [100%]
36 passed in 2.66s

--- Execution Summary ---
{
  "suite": "security_negative_vectors",
  "phase": "PH03",
  "agent": "A09",
  "total_test_vectors": 36,
  "elapsed_seconds": 3.171,
  "status": "PASS",
  "exit_code": 0,
  "categories_covered": [
    "expired_jwt_tokens",
    "wrong_signature_and_tampering",
    "malformed_authorization_headers",
    "cross_tenant_idor_object_isolation",
    "revoked_token_replay_denylist",
    "e2e_http_middleware_pipeline"
  ]
}
```

---

## 4. Continuous Integration Security Gate

The security negative suite is hermetic and requires zero network access, external Redis, or PostgreSQL instances, making it suitable for both pre-commit validation and continuous integration pipelines.

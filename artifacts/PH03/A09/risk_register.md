# Risk Register: PH03_A09 Security Negative-Test Suite & Audit

## 1. Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant Enforced | Status |
|---|---|---|---|---|---|---|
| **RR-PH03-A09-01** | Cryptographic Bypass | Attacker presents token with `"alg": "none"` or mismatched signature to impersonate admin. | Critical | Low | `decode_access_token` pins `algorithms=[settings.jwt_algorithm]` and enforces HMAC-SHA256 signature verification. Verified in `test_vec_sec_sig_01` & `test_vec_sec_sig_03`. | Controlled |
| **RR-PH03-A09-02** | Transport Session Hijacking | Attacker supplies valid cookie along with a malformed Bearer header to circumvent CSRF defenses while maintaining authenticated state. | High | Low | `_extract_access_token` and `has_valid_explicit_bearer_token` enforce the transport anti-downgrade invariant: explicit Bearer owns auth and does not fall back to cookie. Verified in `test_vec_sec_hdr_08`. | Controlled |
| **RR-PH03-A09-03** | Broken Object-Level Authorization (IDOR) | Malicious user manipulates resource IDs (`folder_id`, `case_id`, `source_id`) to read or alter another user's clinical or research data. | Critical | Medium | Database queries enforce strict owner scoping (`user_id == current_user.id`), returning `404 Not Found` to prevent enumeration. Verified in `test_vec_sec_idr_01` through `test_vec_sec_idr_04`. | Controlled |
| **RR-PH03-A09-04** | Token Replay After Logout | Attacker captures and replays JWT access token after patient clicks logout. | High | Medium | `session_security.revoke` inserts token `jti` into Redis denylist for remaining TTL; `_reject_if_revoked` rejects replay with `401 Unauthorized`. Verified in `test_vec_sec_rev_01`. | Controlled |
| **RR-PH03-A09-05** | Refresh Token Multi-Use Replay | Compromised refresh token replayed to mint multiple new access tokens. | High | Low | Single-use consumption in database (`AuthToken.used_at`) combined with Redis rotation tracking (`is_refresh_reused`) detects replay and revokes session. Verified in `test_vec_sec_rev_02`. | Controlled |
| **RR-PH03-A09-06** | Telemetry PII Leakage | Logging security revocation and replay events inadvertently leaks patient identifiers, emails, or raw tokens. | Critical | Low | Zero-PII telemetry invariant: `session_security` keys and log records persist and emit strictly SHA-256 digests (`sha256(jti)`). Verified in `test_vec_sec_rev_03`. | Controlled |
| **RR-PH03-A09-07** | Flaky Suite Execution | Security tests hanging on external network dependencies or unseeded PostgreSQL instances. | Medium | Low | Suite runs completely hermetically in-memory with zero external network or database calls, executing 36 vectors in < 3 seconds. | Controlled |

---

## 2. Invariant & Safety Guardrails Summary

1. **Fail-Closed Principle:** Any token with expired timestamp, invalid signature, unapproved algorithm, or unknown issuer is rejected with HTTP `401 Unauthorized`.
2. **Object Non-Enumeration:** Cross-tenant IDOR violations return HTTP `404 Not Found` rather than `403 Forbidden` to prevent resource probing.
3. **Transport Anti-Downgrade:** The gateway never silently falls back from an explicit Bearer header to an HTTP cookie.
4. **Hermetic & Isolated:** Tests require zero network, live Redis, or Postgres services.

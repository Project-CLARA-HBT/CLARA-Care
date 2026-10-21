# Research & Security Audit Specification: Negative-Test Suite (PH03_A09)

## 1. Executive Summary & Purpose

This specification establishes the comprehensive security negative-testing methodology and verification framework for Phase **PH03** ("Hardening auth và identity").

In medical AI applications, security failures directly endanger patient confidentiality and safety. A benign positive test suite confirms that expected requests work; a **negative test suite** guarantees that unauthorized, malformed, expired, tampered, or cross-tenant malicious requests **fail closed** with deterministic, non-leaking HTTP status codes and zero PII/PHI leakage.

This audit covers five critical vulnerability domains:
1. **Expired JWT Tokens:** Enforcing strict zero-tolerance expiration across both access and refresh lifecycles.
2. **Wrong Signature & Cryptographic Tampering:** Countering HMAC key confusion, payload tampering (privilege escalation), algorithm `none` attacks (CVE-2015-9235), and issuer mismatches.
3. **Malformed Authorization Headers:** Parsing RFC 7235 compliance, rejecting garbage/unsupported schemes, and strictly preserving the **transport anti-downgrade invariant** (never falling back to cookie sessions when an explicit Bearer header is presented).
4. **Cross-Tenant & Cross-User IDOR (Insecure Direct Object References):** Object-level isolation across clinical cases, workspace folders, channels, and research sources, combined with RBAC role hierarchy enforcement (`normal` < `doctor` < `admin`).
5. **Replay of Revoked Tokens:** Validation of session logout denylisting, refresh token single-use rotation, replay detection, and no-PII telemetry hashing.

---

## 2. Security Threat Model & Invariants

| Invariant ID | Security Property | Threat Vector / Attack Scenario | Enforced Countermeasure | HTTP Status |
|---|---|---|---|---|
| **INV-SEC-01** | **Temporal Expiry** | Attacker replays intercepted JWT past `exp` claim window. | PyJWT/Jose strict `verify_exp=True` checking. | `401 Unauthorized` |
| **INV-SEC-02** | **Signature Authenticity** | Attacker tampers with `role: admin` or signs with arbitrary key. | HMAC SHA-256 cryptographic verification against server secrets. | `401 Unauthorized` |
| **INV-SEC-03** | **Algorithm Whitelist** | Attacker crafts unsigned token with `"alg": "none"`. | Explicit algorithm pinning `algorithms=["HS256"]`. | `401 Unauthorized` |
| **INV-SEC-04** | **Transport Anti-Downgrade** | Attacker with valid cookie presents malformed Bearer to bypass CSRF. | Explicit Bearer scheme owns authentication; fails closed with no cookie fallback. | `401 Unauthorized` |
| **INV-SEC-05** | **Object-Level Isolation (IDOR)** | Authenticated user manipulates resource ID in path to read/modify peer data. | Explicit database predicate `WHERE user_id = :current_user_id`. | `404 Not Found` |
| **INV-SEC-06** | **Vertical Privilege Gate** | Non-clinician (`normal`) calls `/doctor/*` clinical surfaces. | Fast-path dependency `require_roles("doctor")` checks payload role. | `403 Forbidden` |
| **INV-SEC-07** | **Single-Use Revocation** | Attacker replays refresh token or post-logout access token. | Redis JTI denylist and DB `used_at` single-use consumption. | `401 Unauthorized` |
| **INV-SEC-08** | **Zero-PII Telemetry** | Security logging leaks patient email or token in logs. | Telemetry hashes token identifiers using SHA-256; zero plaintext PII emitted. | Non-leaking logs |

---

## 3. Comprehensive Negative Test Vector Matrix

The negative test suite implemented in `research/security_audit/test_security_negative_vectors.py` defines 36 distinct test vectors:

### 3.1 Expired JWT Vectors (`TestExpiredJWTVectors`)
- `test_vec_sec_exp_01_access_token_expired_in_past`: Access token with `exp` 2 hours in the past is rejected.
- `test_vec_sec_exp_02_access_token_expired_one_second_ago`: Strict boundary check: expired by 1 second is rejected.
- `test_vec_sec_exp_03_refresh_token_expired`: Expired refresh token rejected during token refresh.
- `test_vec_sec_exp_04_positive_control_valid_token_succeeds`: Control baseline: unexpired token resolves cleanly.

### 3.2 Wrong Signature & Tampering Vectors (`TestWrongSignatureVectors`)
- `test_vec_sec_sig_01_forged_secret_key`: Token signed with arbitrary foreign HMAC secret fails verification.
- `test_vec_sec_sig_02_payload_tampering_role_escalation`: Byte-modified payload with forged `role: admin` fails signature.
- `test_vec_sec_sig_03_none_algorithm_attack`: Token with header `{"alg": "none"}` is rejected fail-closed.
- `test_vec_sec_sig_04_issuer_mismatch`: Valid signature but foreign `iss` claim rejected.
- `test_vec_sec_sig_05_token_type_confusion_cross_surface`: Refresh token presented as access token (or vice versa) rejected.
- `test_vec_sec_sig_06_retired_signing_key_rejection`: Old key used after rotation window closed is rejected.

### 3.3 Malformed Header & Transport Vectors (`TestMalformedHeaderVectors`)
- `test_vec_sec_hdr_01_missing_authorization_header`: Missing header handled cleanly without 500 error.
- `test_vec_sec_hdr_02_empty_or_whitespace_header`: Header with empty/whitespace contents rejected.
- `test_vec_sec_hdr_03_missing_bearer_scheme_prefix`: Raw JWT token lacking `Bearer ` prefix rejected.
- `test_vec_sec_hdr_04_unsupported_auth_schemes`: Schemes `Basic`, `Token`, `OAuth` rejected.
- `test_vec_sec_hdr_05_case_insensitive_bearer_scheme_rfc7235`: RFC 7235 compliance (`bearer`, `BEARER`, `Bearer`).
- `test_vec_sec_hdr_06_truncated_jwt_segments`: Tokens with 1, 2, or 5 segments rejected fast.
- `test_vec_sec_hdr_07_corrupted_base64_payload`: Non-base64 characters rejected.
- `test_vec_sec_hdr_08_transport_anti_downgrade_invariant`: Explicit Bearer owns authentication; never downgrades to cookie.

### 3.4 Cross-Tenant & IDOR Vectors (`TestCrossTenantIDORVectors`)
- `test_vec_sec_idr_01_workspace_folder_horizontal_idor_prevention`: User B cannot access User A's workspace folder (404).
- `test_vec_sec_idr_02_workspace_channel_horizontal_idor_prevention`: User B cannot access User A's channel (404).
- `test_vec_sec_idr_03_council_case_clinician_cross_access_prevention`: Doctor B cannot access Doctor A's case (404).
- `test_vec_sec_idr_04_research_knowledge_source_isolation`: Researcher B cannot access Researcher A's source (404).
- `test_vec_sec_idr_05_vertical_privilege_escalation_normal_to_doctor`: `normal` user accessing clinician surface blocked (403).
- `test_vec_sec_idr_06_vertical_privilege_escalation_doctor_to_admin`: `doctor` user accessing admin surface blocked (403).
- `test_vec_sec_idr_07_admin_implicit_access_invariant`: `admin` has implicit access across roles.

### 3.5 Revocation, Rotation & Telemetry Vectors (`TestRevokedTokenReplayVectors`)
- `test_vec_sec_rev_01_replay_of_logged_out_access_token`: Access token logged out via JTI denylist rejected on replay (401).
- `test_vec_sec_rev_02_refresh_rotation_replay_detection`: Replay of rotated refresh token detected and blocked.
- `test_vec_sec_rev_03_zero_pii_security_telemetry_invariant`: Replay events log ONLY SHA-256 digests; zero plaintext PII emitted.

### 3.6 HTTP Middleware Integration Vectors (`TestHTTPPipelineIntegration`)
- `test_http_01_missing_auth_header_yields_401`: End-to-end pipeline emits 401 on missing auth.
- `test_http_02_garbage_token_yields_401`: End-to-end pipeline emits 401 on malformed token.
- `test_http_03_expired_token_yields_401`: End-to-end pipeline emits 401 on expired token.
- `test_http_04_tampered_token_yields_401`: End-to-end pipeline emits 401 on signature mismatch.
- `test_http_05_role_gate_rejection_normal_on_doctor_surface`: End-to-end pipeline emits 403 on role shortfall.
- `test_http_06_role_gate_success_doctor_on_doctor_surface`: End-to-end pipeline emits 200 for authorized role.
- `test_http_07_admin_implicit_access_on_doctor_surface`: End-to-end pipeline permits admin implicitly.
- `test_http_08_revoked_token_via_denylist_yields_401`: End-to-end pipeline rejects revoked JTI with 401.

---

## 4. Execution Guidance & Integration

The security negative suite is completely hermetic, zero-network, and runs in sub-3 seconds:

```bash
# Direct runner execution:
PYTHONPATH=services/api/src python3 research/security_audit/run_security_audit.py

# Direct pytest execution:
PYTHONPATH=services/api/src python3 -m pytest -v research/security_audit/test_security_negative_vectors.py
```

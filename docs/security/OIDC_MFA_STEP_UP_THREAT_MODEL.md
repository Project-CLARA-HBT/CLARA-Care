# OIDC Privileged Identity, MFA Bypass & Token Theft Threat Model (PH42)

## Executive Summary
This security threat model evaluates attack surfaces targeting privileged administrative sessions, Multi-Factor Authentication (MFA) step-up mechanisms, and session token persistence in The CLARA Care control plane.

## Threat Vectors & Invariants

### 1. MFA Bypass & Privileged Action Elevation
- **Threat Vector:** An attacker with compromised primary credentials (email + password) attempts to execute destructive administrative operations (e.g. tenant data deletion or key rotation) without completing secondary factor authentication.
- **Countermeasure:**
  - Control-plane endpoints enforce tiered step-up authorization (`STANDARD` vs `PRIVILEGED`).
  - Sensitive operations (`POST /control/v1/tenants/suspend`, `POST /control/v1/keys/rotate`) strictly require `session.step_up_level == "PRIVILEGED"`.
  - Elevation requires cryptographic TOTP or FIDO2 WebAuthn verification (`amr: ["mfa"]`).
  - Elevated sessions possess a constrained TTL (maximum 30 minutes) before automatic downgrade to `STANDARD`.

### 2. Cross-Site Request Forgery (CSRF) on Admin Interfaces
- **Threat Vector:** An authenticated administrator browsing an external website is tricked into submitting forged state-changing requests to the control plane.
- **Countermeasure:**
  - Administrative cookies are issued with the `__Host-` prefix and `SameSite=Strict`.
  - Mutating HTTP methods (`POST`, `PUT`, `DELETE`) require custom anti-CSRF request headers (`X-Control-CSRF-Token` or Bearer header).
  - Malformed or missing CSRF tokens fail closed with HTTP 403 Forbidden.

### 3. Refresh Token Theft & Replay Protection
- **Threat Vector:** An attacker intercepts an administrative refresh token via network monitoring or memory extraction.
- **Countermeasure:**
  - Every token refresh issues a new cryptographically random refresh token while immediately revoking the predecessor (single-use rotation).
  - Replay of an already-consumed refresh token triggers automated invalidation of the entire token family, forcing re-authentication across all sessions.
  - Refresh tokens are bound to the client physical device identifier (`device_id`).

## Threat Evaluation Matrix

| Threat ID | Threat Category | Likelihood | Impact | Primary Defense | Residual Risk |
|---|---|---|---|---|---|
| TM-MFA-01 | Phishing of primary password | Medium | High | Mandatory MFA step-up for privileged mutations | Negligible |
| TM-MFA-02 | Session fixation via pre-seeded cookie | Low | High | Regenerate session ID and device binding upon login | None |
| TM-MFA-03 | CSRF state mutation | Low | Critical | `__Host-` prefix + `SameSite=Strict` + double submit header | None |
| TM-MFA-04 | Stolen long-lived refresh token | Low | Critical | Single-use rotation + token family invalidation | Negligible |
| TM-MFA-05 | Device spoofing | Low | Medium | Strict device fingerprint check on introspection | Negligible |

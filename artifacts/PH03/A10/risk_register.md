# Risk Register — PH03 Auth Hardening & Key Rotation (Subagent A10)

**Phase:** PH03 — Hardening Auth & Identity
**Subagent:** Subagent A10 — Adversarial Audit + Integration Proposals
**Worktree:** `/dev/shm/clara_worktrees/PH03_A10`
**Branch:** `phase/ph03-a10`
**Base SHA:** `3b1072b98350b978b83b7ecec5c35228415759a3`
**Status:** ACTIVE AUDIT REGISTER · GATE VERIFIED

---

## 1. Scope & Objective

Phase PH03 strengthens cryptographic identity boundaries, tokens, and multi-tenant scoping. This register analyzes adversarial attack vectors and failure modes associated with secret rotation, token lifecycle, and session invalidation.

---

## 2. Identified Risks & Automated Mitigations

| Risk ID | Category | Severity | Likelihood | Impact | Threat & Vulnerability Summary | Mitigations & Verification Controls |
|---|---|---|---|---|---|---|
| **RISK-PH03-01** | Availability / UX | **HIGH** | High | High | **Mass User Logout During Key Rotation**<br>Rotating `JWT_SECRET_KEY` without an overlap mechanism instantly invalidates signatures across all active web, mobile, and clinician sessions. | **Mitigated in `core/security.py` & `auth-hardening-and-key-rotation.md`**:<br>`_signing_keys()` checks `JWT_SECRET_KEY` then `JWT_SECRET_KEY_PREVIOUS`. Tokens issued under the prior key continue to verify until natural expiration. Verified by `test_overlap_window_accepts_both_old_and_new`. |
| **RISK-PH03-02** | Security / Revocation | **HIGH** | Medium | High | **Compromised Key Persistence During Emergency Rotation**<br>In an active breach where the signing key is exfiltrated, an overlap window would allow attacker-minted tokens to remain valid. | **Mitigated in Runbook §4 (Scenario A)**:<br>Clear emergency protocol instructions mandate setting `JWT_SECRET_KEY_PREVIOUS=""` immediately on compromise, terminating 100% of forged tokens at the gateway boundary. |
| **RISK-PH03-03** | Session Security | **HIGH** | Medium | High | **Refresh Token Replay & Family Hijacking**<br>Stolen refresh tokens reused by an attacker to obtain fresh access tokens. | **Mitigated in `core/session_security.py` & `endpoints/auth.py`**:<br>Refresh tokens are single-use. When refreshed, the old `jti` hash is logged in Redis. Attempted reuse revokes the active token family. Verified by `test_refresh_token_is_single_use`. |
| **RISK-PH03-04** | Confidentiality / Privacy | **HIGH** | Low | High | **PII Infiltration in Security Denylists & Telemetry**<br>Persisting plaintext emails, names, or patient queries into Redis revocation keys or Prometheus counters. | **Mitigated in `SessionSecurity`**:<br>Only SHA-256 digests (`_digest(jti)`) are stored in Redis keys (`security:jti:deny:<hash>`). Telemetry counts use opaque counters with zero PHI/PII. |
| **RISK-PH03-05** | Identity / Privileges | **CRITICAL** | Low | Critical | **Horizontal/Vertical Role Escalation via Insecure Registration**<br>Self-service user registration exploiting open parameters to claim `admin` or `doctor` roles. | **Mitigated in `_resolve_auto_provision_role` & `endpoints/auth.py`**:<br>Production environment blocks non-normal roles during self-registration (`HTTP 403`). Role claims are cryptographically signed within the token payload. |
| **RISK-PH03-06** | Supply Chain / Ops | **HIGH** | Medium | Medium | **Insecure Secret Default Values in Production Deployments**<br>Containers starting in production using default `change-me` JWT keys or weak bootstrap admin passwords. | **Mitigated in `main.py:62` (Startup Guards)**:<br>The API gateway evaluates secrets on boot and crashes immediately (`RuntimeError`) if placeholder keys are detected in production. |

---

## 3. Residual Risk Assessment

With the adoption of the dual-key rotation runbook, single-use refresh token constraints, and automated quality gates in `scripts/ci/ph03_quality_gate.py`, the residual probability and impact of auth failure have been reduced to acceptable levels for staging and production rollout.

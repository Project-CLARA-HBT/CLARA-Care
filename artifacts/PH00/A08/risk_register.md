# Security and Privacy Risk Register — CLARA-Care (PH00 / A08)

**Document Status:** Sealed Audit Baseline · Subagent A08  
**Repository Branch:** `phase/ph00-a08`  
**Frozen HEAD Commit SHA:** `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`  
**Audit Scope Lane:** `docs/security/`, `docs/compliance/`, `scripts/ops/`, `services/api/`, `services/ml/`, `deploy/`, `apps/web/`  
**Date:** October 2026  

---

## 1. Executive Summary

As part of Phase PH00 (Subagent A08: Security + Privacy), an exhaustive code and configuration security audit was executed across the CLARA-Care monorepo at frozen commit `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`.

The audit evaluated six primary risk domains:
1. **Secrets & Credential Leakage:** Hardcoded API keys, bearer tokens, passwords, and placeholder values in code, configs, and documentation.
2. **Patient Data & Protected Health Information (PHI):** Zero-PII telemetry invariants, Zero-CoT guarantees, redaction pipelines, anonymization sweeps, and potential PHI exposure across test fixtures and datasets.
3. **Cross-Site Request Forgery (CSRF):** Protection for cookie-authenticated mutations, strictness of Bearer header exemptions, and path-level exemptions.
4. **Role-Based Access Control (RBAC) & Object Boundaries:** Route-level authorization gates, administrative boundaries, clinician live-grant requirements, and IDOR protection via `ProfileScope`.
5. **Regulatory Compliance & Privacy Policies:** Adherence to Vietnam Decree No. 13/2023/NĐ-CP (PDPD), AI Law No. 134/2025/QH15, DPIA/ROPA/TIA accuracy, and public privacy notices.
6. **Infrastructure & Deployment Security:** Docker Compose specifications, Nginx reverse proxy policies, and CI/CD artifact safety filters.

### Key Finding Highlight
The automated secret scan (`python3 -m evaluation.commitloop.secret_scan`) discovered an active API key (`sk-2a0a31f...`) committed to both a script (`scripts/ops/run_v8_provider_probe_ledger.py`) and a specification markdown file (`research/glhs_journal/q3_r3/provider_run_ledger_spec.md`). This constitutes the sole **CRITICAL** vulnerability identified during this audit. All other core security boundaries (CSRF enforcement with cryptographic token verification, RBAC profile isolation, no-PII logging, and PDPD/AI Law compliance files) were found structurally sound and verified with passing test suites.

---

## 2. Risk Matrix & Severity Definitions

| Severity | Definition | Action Required |
|:---|:---|:---|
| **CRITICAL** | Active secret exposure, unauthorized access to PHI, or remote code execution vulnerability. | Immediate key rotation and removal from repository. |
| **HIGH** | Insecure network boundary, missing access control on sensitive internal endpoints, or lack of authentication fallback in production. | Mandatory remediation prior to production deployment. |
| **MEDIUM** | Inconsistent CSRF boundary, fail-open state on auxiliary security services (e.g. Redis), or legacy configuration drift. | Prioritize in hardening sprint. |
| **LOW / INFO** | Development placeholders, public author emails in scientific bibliographies, or documentation discrepancies. | Address during routine maintenance. |

---

## 3. Comprehensive Risk Inventory

| Risk ID | Category | Title | Severity | Likelihood | Impact | Status |
|:---|:---|:---|:---|:---|:---|:---|
| **SEC-CRIT-01** | Credentials | Hardcoded Router API Key in Ops Script & Research Spec | **CRITICAL** | High | Severe | **Open** (Key Rotation Required) |
| **SEC-HIGH-01** | Network / Boundary | Public Reverse Proxy Upstream Exposure of ML Service | **HIGH** | Medium | High | **Open** (Nginx Scoping Recommended) |
| **SEC-MED-01** | CSRF | CSRF Exemption on `/api/v1/auth/refresh` | **MEDIUM** | Medium | Medium | **Accepted** (Documented Follow-up) |
| **SEC-MED-02** | Auth / Limiters | Fail-Open Fallback for Redis Distributed Limiters & Denylist | **MEDIUM** | Low | High | **Accepted** (Availability Tradeoff) |
| **SEC-LOW-01** | Credentials | Insecure Default Secrets in `.env.example` & Deploy Script | **LOW** | Low | Low | **Mitigated** (Startup Guards Enforced) |
| **SEC-LOW-02** | Privacy | Public Author Email in Acquired Medical PDF Metadata | **LOW** | Low | Negligible | **Informational** (Public HMU Author) |
| **SEC-INFO-01**| RBAC | Implicit Admin Access Across `require_roles` Dependencies | **INFO** | Low | Medium | **Design Invariant** (Intended Admin Superuser) |
| **SEC-INFO-02**| PHI / LifeMap | Break-Glass Support Access Denied / Admin Non-Access to PHR | **INFO** | Low | Low | **Enforced Control** (Admin Blocked by Default) |

---

## 4. Detailed Risk Assessments & Verified Anchors

### 4.1 Secrets & Credential Leakage

#### SEC-CRIT-01: Hardcoded Router API Key in Ops Script & Research Spec
- **Severity:** **CRITICAL**
- **Affected Anchors:**
  - `scripts/ops/run_v8_provider_probe_ledger.py:37`:  
    `API_KEY` defined with static string [REDACTED]
  - `research/glhs_journal/q3_r3/provider_run_ledger_spec.md:32`:  
    `- **Authentication Header:** [REDACTED]`
- **Mechanism & Impact:**  
  The probe script `run_v8_provider_probe_ledger.py` targets `https://router.theclaracare.com/v1` and embeds an actual `sk-` token in plain text. This directly causes the repository's secret scanner (`python3 -m evaluation.commitloop.secret_scan`) to fail closed:  
  `secret_scan_failed:.../research/glhs_journal/q3_r3/provider_run_ledger_spec.md,.../scripts/ops/run_v8_provider_probe_ledger.py`.  
  Any party with repository access can consume credits or query the router upstream.
- **Compensating Controls:** The key appears to be provisioned for model router evaluation; other services use environment variables.
- **Remediation:**  
  1. Immediately revoke and regenerate key in the router gateway.  
  2. Replace assignment in `scripts/ops/run_v8_provider_probe_ledger.py` with `os.environ["ROUTER_API_KEY"]`.  
  3. Redact the bearer token in `research/glhs_journal/q3_r3/provider_run_ledger_spec.md` to `[REDACTED]`.

---

#### SEC-LOW-01: Insecure Default Secrets in `.env.example` & Redeploy Script
- **Severity:** **LOW** (Mitigated by Runtime Startup Guards)
- **Affected Anchors:**
  - `.env.example:89`: `JWT_SECRET_KEY` [REDACTED] (placeholder)
  - `.env.example:96`: `AUTH_BOOTSTRAP_ADMIN_PASSWORD` [REDACTED] (placeholder)
  - `deploy/docker/searxng/settings.yml:17`: `secret_key` [REDACTED] (placeholder)
  - `scripts/deploy/redeploy_app_stack.sh:386`: `local password` [REDACTED] (test smoke placeholder)
- **Mechanism & Impact:**  
  Example files contain known weak secrets. If an operator were to copy `.env.example` directly into production, sessions could be forged or admin accounts compromised.
- **Compensating Controls (Strict Verification):**  
  - `services/api/src/clara_api/main.py:62-67` enforces:  
    `if settings.environment.lower() == "production": if settings.jwt_secret_key.strip().lower() in _INSECURE_JWT_SECRET_VALUES: raise RuntimeError(...)`
  - `services/api/src/clara_api/main.py:92-99` enforces:  
    `if settings.auth_bootstrap_admin_enabled and bootstrap_password in _INSECURE_BOOTSTRAP_PASSWORDS: raise RuntimeError(...)`
  - `deploy/docker/docker-compose.deploy.yml:12`: `JWT_SECRET_KEY` requires non-empty environment variable
  - `scripts/security/check_ci_artifact_policy.py:30-38`: Blocks deploy configs retaining legacy SearXNG secrets or omitting `SEARXNG_SECRET`.
- **Remediation:** Ensure ops documentation emphasizes generating high-entropy random keys via `openssl rand -hex 32`.

---

### 4.2 Network & Service Boundaries

#### SEC-HIGH-01: Public Reverse Proxy Upstream Exposure of ML Service
- **Severity:** **HIGH**
- **Affected Anchors:**
  - `deploy/nginx/clara.thiennn.icu.conf:72-82`:
    ```nginx
    location /ml/ {
        proxy_http_version 1.1;
        proxy_pass http://127.0.0.1:8110/;
    }
    ```
  - `services/ml/src/clara_ml/main.py:1051-1072`: `enforce_internal_api_key` middleware
- **Mechanism & Impact:**  
  The external Nginx configuration exposes the entire ML microservice to the public internet under `/ml/`. While ML middleware enforces `X-ML-Internal-Key` on `/v1/*`, `/metrics`, `/metrics/json`, and `/health/details`, endpoints such as `/health` (and potentially unmapped routes) are exposed directly without passing through API's rate limiters, AuthContextMiddleware, or CSRF protection. In non-production environments (`settings.environment != "production"`), if `ml_internal_api_key` is empty, ML fails open and allows unauthenticated calls (`services/ml/src/clara_ml/main.py:1064`).
- **Compensating Controls:** In production, missing `ML_INTERNAL_API_KEY` returns `503 ML internal auth misconfigured`.
- **Remediation:** Remove `location /ml/` from public Nginx ingress entirely. All client traffic must traverse `services/api` (port 8000/8100), keeping ML completely isolated on the internal Docker network.

---

### 4.3 CSRF Enforcement Architecture

#### SEC-MED-01: CSRF Protection & Bearer Exemption Strictness
- **Severity:** **MEDIUM** (Design Follow-up)
- **Affected Anchors:**
  - `services/api/src/clara_api/main.py:315-347`: `enforce_csrf_for_cookie_session`
  - `services/api/src/clara_api/core/rbac.py:15-39`: `_has_bearer_scheme`, `extract_bearer_token`
  - `services/api/src/clara_api/core/rbac.py:92-108`: `has_valid_explicit_bearer_token`
  - `services/api/src/clara_api/main.py:133-144`: `_CSRF_EXEMPT_PATHS`
- **Assessment of Enforced Controls:**  
  1. **Strict Exemption Guard:** Prior threat model vulnerability (malformed or mixed-case `bearer` header bypassing CSRF and falling back to cookies) was verified **CLOSED**. `has_valid_explicit_bearer_token(request)` parses the Authorization header using RFC 7235 case-insensitive logic, decodes the JWT signature, and checks revocation (`_reject_if_revoked`). A bogus or expired Bearer token evaluates to `False`, forcing the request through full CSRF verification if cookies are present.
  2. **Timing-Safe Comparison:** `secrets.compare_digest(csrf_cookie, csrf_header)` at line 341 protects against timing side-channel attacks on CSRF tokens.
  3. **Refresh Route Exemption:** `/api/v1/auth/refresh` is listed in `_CSRF_EXEMPT_PATHS` (`main.py:138`). While this maintains compatibility with non-browser clients, browser clients sending refresh cookies without CSRF could theoretically be triggered by external sites. However, `services/api/src/clara_api/api/v1/endpoints/auth.py:575-595` enforces single-use refresh token rotation and cookie/payload conflict checks (`401` token conflict).
- **Remediation / Follow-up:** Implement an explicit separate endpoint for mobile token refresh or require CSRF header on cookie-authenticated refresh requests.

---

### 4.4 RBAC & Access Boundaries

#### SEC-INFO-01: Administrative Privilege & Separation of Roles
- **Severity:** **INFORMATIONAL** (Core Architecture Invariant)
- **Affected Anchors:**
  - `services/api/src/clara_api/core/rbac.py:138-148`:
    Role checking dependency evaluates `token.role == "admin"` before inspecting specific target role list.
  - `services/api/src/clara_api/core/rbac.py:51-57`: `_reject_if_revoked`
  - `services/api/src/clara_api/core/session_security.py:48-52, 148-157`: `is_revoked`
- **Assessment:**  
  - Administrative role has system-wide privilege across route endpoints.
  - However, in health data access (LifeMap V2 / PHR), administrative role alone does **not** grant access to patient records (`docs/security/lifemap-v2-threat-model.md:21`).
  - Clinicians require an active, live grant (`FamilyAccessGrant`) bound to patient ID, object, data class, and time window (`test_doctor_requires_a_live_grant_and_admin_role_is_not_profile_access`).
  - Denylisted/revoked tokens are rejected across all authenticated endpoints when `HARDENING_TOKEN_DENYLIST_ENABLED=true`.

---

#### SEC-MED-02: Fail-Open State for Auxiliary Security Stores
- **Severity:** **MEDIUM** (Availability vs. Security Tradeoff)
- **Affected Anchors:**
  - `services/api/src/clara_api/core/login_guard.py:35-50`: In-memory fallback if Redis is unreachable.
  - `services/api/src/clara_api/core/session_security.py:128-135, 153-157`: Revocation/reuse checks fail-open (return `False`) if Redis is offline.
  - `docs/security/security-remediation-2026-04-03.md:94-98`: Tracked remaining risk.
- **Assessment:**  
  When Redis is down, login lockout and token revocation fail open to preserve service availability for legitimate users. In high-security environments, an unmanaged Redis outage would allow brute-force attempts.
- **Recommendation:** Add a `SECURITY_FAIL_CLOSED=true` configuration flag to block login mutations if Redis fails.

---

### 4.5 Patient Data, Privacy & PHI Invariants

#### PRIV-INV-01: Zero-PII Telemetry & Logging
- **Affected Anchors:**
  - `services/api/src/clara_api/main.py:274-290`: Exception handler logs only `type(exc).__name__`; suppresses raw exception messages, tracebacks, and request parameters.
  - `services/api/src/clara_api/core/metrics.py:1-150` & `services/api/tests/test_metrics_no_pii.py`: Prometheus metrics export only bounded labels (method, status code, route path); never query text, user IDs, or clinical terms.
  - `services/ml/src/clara_ml/nlp/pii_filter.py:6-28`: Regex redactors for Vietnamese phone numbers (`\b(?:\+84|0)\d{9,10}\b`), national citizen IDs (9-12 digits), and email addresses.
  - `services/api/src/clara_api/compliance/redaction.py`: `redact_meta` projects compliance logs to counts/flags only.
  - `scripts/security/check_ci_artifact_safety.py:18-31`: CI pre-upload guard blocks files containing emails, phones, tokens, or credential assignments.
- **Verification Evidence:** `tests/compliance/test_no_pii_logs.py` (5 passed) and `tests/test_metrics_no_pii.py` (3 passed).

---

#### PRIV-INV-02: Data Retention & Automated Anonymization Sweep
- **Affected Anchors:**
  - `docs/compliance/ropa.md:108-125`: Declared retention schedule (PHR profile 1095 days, query log 365 days, auth tokens 90 days, compliance audit 3650 days).
  - `services/api/src/clara_api/compliance/retention.py:1-180`: `run_retention_sweep` executes anonymization/deletion.
  - `scripts/ops/run_retention_sweep.sh:1-61`: Cron wrapper outputs PII-free JSON line `{"swept": ..., "enabled": ...}`.
  - `scripts/ops/RUNBOOK_retention_sweep.md:1-103`: Operational runbook for crontab installation and rollback.
- **Assessment:**  
  The sweep is transactionally safe: failures roll back. Output logs contain counts only, guaranteeing that cron logs never accumulate PHI.

---

### 4.6 Compliance with Vietnam PDPD (Decree 13/2023) & AI Law (Law 134/2025)

#### COMP-PDPD-01: Data Subject Rights (DSAR) & Consent Governance
- **Affected Anchors:**
  - `docs/compliance/dpia.md:42-56`: Consent types (`core_service`, `personalization`, `research`, `cross_border_processing`, `sharing`, `ai_transparency`).
  - `docs/compliance/dpia.md:63-76`: DSAR matrix (export, correct, delete, restrict, withdraw) with 30-day statutory response SLA.
  - `docs/compliance/transfer-impact-assessments.md:23-96`: Transfer Impact Assessments for offshore processors `yescale-deepseek` and `yescale-embeddings`.
  - `apps/web/app/legal/privacy/page.tsx:44-75`: Third-party processor transparency table matching `TransferRegistry`.
  - `apps/web/app/legal/privacy/page.tsx:81-91`: Explicit Zero-PII Telemetry and Zero-CoT public commitment.
- **Assessment:**  
  The repository maintains comprehensive, living compliance records matching the deployed backend models and schemas. All required regulatory dossiers are versioned in `docs/compliance/`.

---

## 5. Summary of Recommended Actions

1. **Immediate (P0):**
   - Rotate router API key `<REDACTED_API_KEY>`.
   - Update `scripts/ops/run_v8_provider_probe_ledger.py` to ingest `ROUTER_API_KEY` from the environment.
   - Redact the plain text token in `research/glhs_journal/q3_r3/provider_run_ledger_spec.md`.
2. **Next Release (P1):**
   - Remove `location /ml/` from `deploy/nginx/clara.thiennn.icu.conf` to enforce API gateway isolation.
   - Introduce `SECURITY_FAIL_CLOSED` mode for high-security environments when Redis is unavailable.
3. **Hardening Maintenance (P2):**
   - Add CSRF header requirement to cookie-authenticated calls on `/api/v1/auth/refresh`.
   - Add automated pre-commit hook executing `evaluation.commitloop.secret_scan` across all tracked files.

---
**Audit Attestation:**  
Completed by Subagent A08 (Security + Privacy) under Phase PH00. All path:line anchors verified against commit `8a48afab1dafa2f8ccb4ac9f320505452d18b30f`.

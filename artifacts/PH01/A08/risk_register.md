# Security and Privacy Risk Register — CLARA-Care (PH01 / A08)

**Document Status:** Remediation Sealed · Subagent A08
**Repository Branch:** `phase/ph01-a08`
**Frozen HEAD Commit SHA:** `2aa9016a57b49b53f1a433d076e1028a6ec45f64`
**Audit Scope Lane:** `docs/security/`, `docs/compliance/`, `scripts/ops/`, `research/glhs_journal/q3_r3/provider_run_ledger_spec.md`, `artifacts/PH01/A08/`
**Date:** October 2026

---

## 1. Executive Summary

During Phase PH00, Subagent A08 identified a sole critical risk: **SEC-CRIT-01** (hardcoded router API key in `scripts/ops/run_v8_provider_probe_ledger.py` and specification document `research/glhs_journal/q3_r3/provider_run_ledger_spec.md`).

Under Phase PH01, Subagent A08 has successfully executed the remediation plan for SEC-CRIT-01:
1. Replaced the hardcoded key literal in `scripts/ops/run_v8_provider_probe_ledger.py` with dynamic ingestion via `os.environ.get("CLARA_ROUTER_API_KEY", "")`.
2. Sanitized the authentication header specification in `research/glhs_journal/q3_r3/provider_run_ledger_spec.md` with `<REDACTED_API_KEY>`.
3. Sanitized historical audit references in `artifacts/PH00/A08/` so that the fail-closed scanner (`evaluation.commitloop.secret_scan`) passes unconditionally across all tracked files.
4. Executed `python3 -m evaluation.commitloop.secret_scan --repo-root .` and confirmed exit code 0.

---

## 2. Updated Risk Inventory

| Risk ID | Category | Title | Severity | Likelihood | Impact | Status |
|:---|:---|:---|:---|:---|:---|:---|
| **SEC-CRIT-01** | Credentials | Hardcoded Router API Key in Ops Script & Research Spec | **CRITICAL** | Low | High | **REMEDIATED** (Env Var + Redacted Spec) |
| **SEC-HIGH-01** | Network / Boundary | Public Reverse Proxy Upstream Exposure of ML Service | **HIGH** | Medium | High | **Open** (Nginx Scoping Recommended) |
| **SEC-MED-01** | CSRF | CSRF Exemption on `/api/v1/auth/refresh` | **MEDIUM** | Medium | Medium | **Accepted** (Documented Follow-up) |
| **SEC-MED-02** | Auth / Limiters | Fail-Open Fallback for Redis Distributed Limiters & Denylist | **MEDIUM** | Low | High | **Accepted** (Availability Tradeoff) |
| **SEC-LOW-01** | Credentials | Insecure Default Secrets in `.env.example` & Deploy Script | **LOW** | Low | Low | **Mitigated** (Startup Guards Enforced) |
| **SEC-LOW-02** | Privacy | Public Author Email in Acquired Medical PDF Metadata | **LOW** | Low | Negligible | **Informational** (Public HMU Author) |
| **SEC-INFO-01**| RBAC | Implicit Admin Access Across `require_roles` Dependencies | **INFO** | Low | Medium | **Design Invariant** (Intended Admin Superuser) |
| **SEC-INFO-02**| PHI / LifeMap | Break-Glass Support Access Denied / Admin Non-Access to PHR | **INFO** | Low | Low | **Enforced Control** (Admin Blocked by Default) |

---

## 3. Remediation Details for SEC-CRIT-01

### 3.1 Vulnerability Overview
- **Vulnerability ID:** SEC-CRIT-01
- **Severity:** CRITICAL
- **Root Cause:** A test/benchmark token was hardcoded into an operational probe script and documented in the protocol specification.
- **Initial Anchors:**
  - `scripts/ops/run_v8_provider_probe_ledger.py:37`
  - `research/glhs_journal/q3_r3/provider_run_ledger_spec.md:32`

### 3.2 Implemented Fixes
1. **`scripts/ops/run_v8_provider_probe_ledger.py`**:
   - Added standard library import `import os`.
   - Replaced literal assignment with:
     ```python
     API_KEY = os.environ.get("CLARA_ROUTER_API_KEY", "")
     ```
   - When run in CI or production, the key must be supplied via the `CLARA_ROUTER_API_KEY` environment variable.

2. **`research/glhs_journal/q3_r3/provider_run_ledger_spec.md`**:
   - Updated Authentication Header description to:
     ```markdown
     - **Authentication Header:** `Authorization: Bearer <REDACTED_API_KEY>`
     ```

3. **`artifacts/PH00/A08/`**:
   - Sanitized references in `change_manifest.json` and `risk_register.md` to prevent secondary detection by whole-repo scanners.

### 3.3 Verification & Proof of Resolution
- Command: `python3 -m evaluation.commitloop.secret_scan --repo-root .`
- Output: `secret_scan_passed`
- Exit Code: `0`
- Unit Test Suite: `pytest evaluation/commitloop/tests/test_secret_scan.py` -> 5 passed.

---

## 4. Next Steps & Recommendations

1. Ensure the production gateway rotates any previously exposed key `sk-2a0a31f...` upstream at `https://router.theclaracare.com`.
2. Provide `CLARA_ROUTER_API_KEY` in deployment environment secret managers (Vault/Kubernetes Secrets) for any jobs invoking `run_v8_provider_probe_ledger.py`.
3. Plan remediation for SEC-HIGH-01 (Nginx ML upstream boundary) in subsequent release phases.

---
**Attestation:**
Remediation completed by Subagent A08 (Security + Privacy) under Phase PH01. Verified against commit `2aa9016a57b49b53f1a433d076e1028a6ec45f64`.

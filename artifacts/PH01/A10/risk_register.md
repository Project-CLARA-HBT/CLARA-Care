# Risk Register — PH01 Adversarial Audit & Quality Gate (Subagent A10)

**Phase:** PH01 — Toolchain Reproducibility & Dependency Supply-Chain
**Agent:** A10 — Adversarial Audit + Integration Proposals
**Target Worktree:** `/dev/shm/clara_worktrees/PH01_A10`
**Branch:** `phase/ph01-a10`
**Base SHA:** `2aa9016a57b49b53f1a433d076e1028a6ec45f64`
**Status:** ACTIVE AUDIT REGISTER · PH01 GATE APPROVED

---

## 1. Executive Summary & Defect Remediation Status

During Phase PH01, Subagent A10 tracked and audited the remediation of baseline defects identified in PH00. All three primary engineering defects (SEC-CRIT-01, DEFECT-01, DEFECT-02) have been successfully remediated and verified in their respective subagent lanes.

| Defect ID | Severity | Status in PH00 | Status in PH01 | Remediation Worktree | Verification Command & Exit Code |
|---|---|---|---|---|---|
| **SEC-CRIT-01** | **CRITICAL** | Open (Hardcoded token) | **REMEDIATED** | `PH01_A08` | `python3 -m evaluation.commitloop.secret_scan` -> Exit 0 |
| **DEFECT-01** | **MEDIUM** | Open (Test fail) | **REMEDIATED** | `PH01_A01` | `pytest tests/test_route_inventory_public_boundaries.py` -> Exit 0 |
| **DEFECT-02** | **HIGH** | Open (Migration SQLite error) | **REMEDIATED** | `PH01_A02` | `alembic upgrade head && downgrade -1` -> Exit 0 |

---

## 2. Updated Platform Risk Register

| Risk ID | Category | Severity | Likelihood | Impact | Title & Vulnerability Summary | Mitigations & Integration Gate |
|---|---|---|---|---|---|---|
| **RISK-01** | Security / Auth | **CRITICAL** | Low | High | **Token Invalidation Post-SEC-CRIT-01 Remediation**<br>While working tree literals have been replaced with `os.environ.get('CLARA_ROUTER_API_KEY')`, the historical token `<REDACTED_API_KEY>` exists in git history. | Invalidate and rotate the token on the router gateway (`router.theclaracare.com`). Enforce secret scan gate on all PRs. |
| **RISK-02** | Toolchain / Mobile | **HIGH** | High | Medium | **Flutter / Dart SDK Range Drift in Mobile Client**<br>`apps/mobile/pubspec.yaml` specifies `sdk: '>=3.3.0 <4.0.0'`, but resolved dependencies (`markdown: 7.3.1`, `flutter_lints: 5.0.0`) require modern Dart `^3.9.0` (Flutter `3.47+`). Environments with older Dart fail package resolution. | Update `pubspec.yaml` to `sdk: '>=3.9.0 <4.0.0'` and lock Flutter toolchain via `.fvm/fvm_config.json` in Phase PH02/PH40. |
| **RISK-03** | Supply Chain | **MEDIUM** | Medium | Medium | **Asymmetric Lockfile Coverage in Sidecar Services**<br>`services/asr` and `services/ocr` do not utilize `uv.lock`. `services/asr` uses `requirements.lock` while `services/ocr` relies on unpinned `pip install` in Dockerfile. | Transition sidecar services to `uv` with checked-in `uv.lock` files during Phase PH02 container modernization. |
| **RISK-04** | Vulnerability Mgmt | **MEDIUM** | High | Low | **Expired Accepted Security Finding GHSA-wj6h-64fc-37mp**<br>Advisory for `ecdsa` (transitive dependency of `python-jose`) had review date `2026-09-24`, which has passed. CLARA uses HMAC algorithms, not ECDSA, but policy requires active review. | Re-certify finding in `docs/security/accepted-findings.md` or replace `python-jose` with `PyJWT` during Phase PH03 (Hardening Auth & Identity). |
| **RISK-05** | Performance / CI | **LOW** | High | Low | **SQLite Disk Fsync Latency During Test Setup**<br>Executing `Base.metadata.create_all` against a physical disk file in `/tmp` takes ~38 seconds due to synchronous file creation across 147 tables, compared to <0.5s in `/dev/shm` or in-memory. | CI and local test harnesses must set `CLARA_TEST_DATABASE_URL="sqlite+pysqlite:////dev/shm/clara_test.db"` to prevent test execution timeouts. |
| **RISK-06** | Research / Regulatory | **HIGH** | Low | High | **Unproven GLHS Research Claims C-001..C-010**<br>All 10 claims in `docs/research/glhs_claim_ledger.yaml` remain `gate_passed: false`. External claims of algorithmic superiority remain blocked. | Maintain CI gate `scripts/ci/r4_claim_lint.py` to prevent premature promotion of scientific claims into product documentation. |

---

## 3. Escalation & Quality Gate Directives for Integration

1. **Gate Acceptance:** PH01 is cleared for integration fan-in by Root Integrator. All subagent deliverables are aligned without file merge conflicts across assigned lanes.
2. **Phase Fan-In Order:**
   - Step 1: Database Migration Fix (A02 -> `20260824_0062_social_bookmarks_and_threading.py`)
   - Step 2: Route Inventory Public Boundary Fix (A01 -> `route_inventory.py`)
   - Step 3: Secret Sanitation (A08 -> `run_v8_provider_probe_ledger.py`, `provider_run_ledger_spec.md`)
   - Step 4: Infrastructure & Mobile Config (A06 -> `AndroidManifest.xml`)
   - Step 5: Local Bootstrap Scripts (A09 -> `bootstrap_dev.sh`)
   - Step 6: SBOM & Dependency Report (A07 -> `generate_sbom.py`, manifests)
   - Step 7: Toolchain Reproducibility Runbook & Gate (A10 -> `ph01-reproducibility-and-rollback.md`, `ph01_reproducibility_gate.py`)
3. **Emergency Rollback Ready:** If any integration anomaly occurs, execute Procedure 4.4 from `docs/runbooks/ph01-reproducibility-and-rollback.md` to restore baseline SHA `2aa9016a57b49b53f1a433d076e1028a6ec45f64`.

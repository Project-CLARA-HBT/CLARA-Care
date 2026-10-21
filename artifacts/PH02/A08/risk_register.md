# Security & Privacy Risk Register — CLARA-Care (PH02 / A08)

**Document Status:** Sealed · Subagent A08
**Repository Branch:** `phase/ph02-a08`
**Frozen Base HEAD Commit SHA:** `879dc5dcfcaae91b3626e28062043d934294478b`
**Audit Scope Lane:** `docs/security/`, `docs/compliance/`, `scripts/ops/`, `scripts/security/`, `artifacts/PH02/A08/`
**Date:** October 2026

---

## 1. Executive Summary

In Phase PH02, Subagent A08 was assigned to implement the **Deterministic Red-Team Manifest Checker** to audit subagent deliverables across phases for simulated/fake test results, hardcoded credentials, PHI leakage, bypassed safety invariants, and commit integrity.

All deliverables have been implemented and verified. This risk register catalogs identified risks, threat vectors, mitigations, and residual exposure across concurrent subagent operations.

---

## 2. Risk Inventory & Threat Matrix

| Risk ID | Category | Title | Severity | Likelihood | Impact | Status | Mitigation / Control |
|:---|:---|:---|:---|:---|:---|:---|:---|
| **RR-PH02-A08-01** | Adversarial Simulation | Subagents reporting fabricated or mocked test results | **CRITICAL** | Medium | Critical | **CONTROLLED** | `redteam_manifest_checker.py` statically enforces non-empty test reports, regex detection of mock markers (`MOCK_ALL_TESTS`), rejects trivial shell commands (`true`, `exit 0`), and cross-checks failing exit codes. |
| **RR-PH02-A08-02** | Credential Leakage | Subagents committing live API keys, bearer tokens, or private keys | **CRITICAL** | Medium | Critical | **CONTROLLED** | Automated scan for `sk-*`, `ROUTER_API_KEY`, Bearer tokens, unencrypted private keys, and JWTs. Verified via `evaluation.commitloop.secret_scan`. |
| **RR-PH02-A08-03** | Privacy / PHI Exposure | Real patient identifiers or clinical diagnoses committed into reports | **CRITICAL** | Low | Critical | **CONTROLLED** | Strict regex scanning for Vietnamese phone numbers, 9/12 digit Citizen IDs (CCCD/CMND), unapproved email addresses, and unredacted clinical logs. |
| **RR-PH02-A08-04** | Guardrail Bypass | Agents disabling RBAC, CSRF, Consent gate, or FIDES drug gates | **CRITICAL** | Low | Critical | **CONTROLLED** | Direct rule detection for invariant bypass flags (`bypass_rbac`, `disable_csrf`, `skip_consent`, `bypass_emergency`, `bypass_fides`, `disable_legal_guard`). |
| **RR-PH02-A08-05** | Commit Provenance Drift | Fabricated git commit hashes or tampered commit signatures | **HIGH** | Low | High | **CONTROLLED** | Checker queries `git cat-file -e <sha>^{commit}` directly against git object database and checks signature state `%G?` (rejects status 'B'). |
| **RR-PH02-A08-06** | Worktree Path Lane Contamination | Subagents modifying files outside assigned directory lanes | **HIGH** | Medium | High | **CONTROLLED** | Checker parses `path_lane` from manifest and strictly verifies all `files_changed` against allowlisted prefixes. |
| **RR-PH02-A08-07** | Non-Deterministic Toolchain / Network Flakiness | Checker depending on external network or fluctuating LLM prompts | **MEDIUM** | Low | Medium | **CONTROLLED** | Purely deterministic, offline Python 3 script with zero external network or non-deterministic heuristic dependencies. |

---

## 3. Residual Risk & Architectural Recommendations

1. **Phase 2 Integration Preflight:** Prior to merging phase branches into trunk, the root integrator should execute:
   ```bash
   python3 scripts/security/redteam_manifest_checker.py artifacts/PH02
   ```
2. **Pre-Commit Hook Integration:** Consider invoking `scripts/security/redteam_manifest_checker.py` in `.github/workflows/ci.yml` on pull requests modifying `artifacts/`.
3. **Commit Signature Enforcement:** When GPG/SSH commit signing is enabled across subagent worktrees, enforce `--strict` mode to require valid signature status (`G` or `U`).

---

**Attestation:**
All controls and mitigations verified by Subagent A08 (Security + Privacy). Baseline HEAD verified as `879dc5dcfcaae91b3626e28062043d934294478b`.

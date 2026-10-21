# Rollback Runbook: PH03_A09 Security Negative-Test Suite & Audit

## 1. Overview & Blast Radius

- **Phase:** PH03 (Hardening auth và identity)
- **Subagent:** A09 (Docs + research evidence)
- **Task:** Security negative-test suite; document and audit comprehensive negative test vectors: expired JWT, wrong signature, malformed authorization header, cross-tenant IDOR, replay of revoked tokens.
- **Blast Radius:** Research negative test modules, security audit runbooks, specifications, and phase artifacts.
- **Data/Schema Changes:** None. No database migrations, schemas, or existing API endpoints are modified.
- **Safety Invariant Impact:** None. No security guardrails or existing production code modified.

---

## 2. Modified / Created Files

The following files were introduced by agent A09:
- `research/security_audit/__init__.py`
- `research/security_audit/test_security_negative_vectors.py`
- `research/security_audit/run_security_audit.py`
- `docs/research/SECURITY_NEGATIVE_TEST_SPECIFICATION.md`
- `docs/implementation/SECURITY_NEGATIVE_TEST_GUIDE.md`
- `artifacts/PH03/A09/change_manifest.json`
- `artifacts/PH03/A09/test_report.md`
- `artifacts/PH03/A09/risk_register.md`
- `artifacts/PH03/A09/rollback.md`

No pre-existing tracked files were modified.

---

## 3. Rollback Procedure

### Step 1: Remove Created Deliverables
Remove all files introduced in this change lane:

```bash
git rm -rf \
  research/security_audit \
  docs/research/SECURITY_NEGATIVE_TEST_SPECIFICATION.md \
  docs/implementation/SECURITY_NEGATIVE_TEST_GUIDE.md \
  artifacts/PH03/A09
```

### Step 2: Reset Branch to Frozen Base SHA
Reset worktree HEAD to the frozen commit:

```bash
git reset --hard 3b1072b98350b978b83b7ecec5c35228415759a3
```

### Step 3: Verification Post-Rollback
Verify that the working tree is clean and matches the frozen commit SHA:

```bash
git rev-parse HEAD
# Expected: 3b1072b98350b978b83b7ecec5c35228415759a3

git status
# Expected: nothing to commit, working tree clean
```

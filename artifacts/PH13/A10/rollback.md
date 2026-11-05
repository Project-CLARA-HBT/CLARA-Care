# Rollback Procedure — Phase PH13 / Subagent A10

Auditor: Subagent A10 (Adversarial Reviewer & Quality Gate)  
Phase: PH13 — Connected Health và wearables  
Branch: `phase/ph13-a10`  
Base SHA: `bce92340e1f7a0709a96e9526e0682fa0fcb1e32`  

---

## 1. Scope & Impact

Subagent A10 delivered documentation, CI validation scripts, adversarial audit reports, and phase gate manifests:
- `docs/runbooks/connected-health-vendor-sandbox-instructions.md`
- `docs/reports/ph13-adversarial-wearable-replay-audit.md`
- `scripts/ci/ph13_quality_gate.py`
- `artifacts/phase-gates/PH13_gate_manifest.json`
- `artifacts/PH13/A10/change_manifest.json`
- `artifacts/PH13/A10/test_report.md`
- `artifacts/PH13/A10/risk_register.md`
- `artifacts/PH13/A10/rollback.md`

Because Subagent A10 does not mutate production database tables or backend runtime code, rolling back A10 deliverables entails removing these artifacts or resetting the branch to the base commit SHA.

---

## 2. Immediate Worktree Rollback Commands

To clean up all A10 deliverables from the worktree:

```bash
# 1. Navigate to worktree
cd /dev/shm/clara_worktrees/PH13_A10

# 2. Remove generated documentation and reports
rm -f docs/runbooks/connected-health-vendor-sandbox-instructions.md
rm -f docs/reports/ph13-adversarial-wearable-replay-audit.md

# 3. Remove CI quality gate script
rm -f scripts/ci/ph13_quality_gate.py

# 4. Remove phase gate manifest
rm -f artifacts/phase-gates/PH13_gate_manifest.json

# 5. Remove A10 artifact directory
rm -rf artifacts/PH13/A10

# 6. Verify clean git working tree
git status --short
```

---

## 3. Git Reset Procedure (Alternative)

If changes have already been committed to `phase/ph13-a10`:

```bash
cd /dev/shm/clara_worktrees/PH13_A10
git reset --hard bce92340e1f7a0709a96e9526e0682fa0fcb1e32
git clean -fd
```

---

## 4. Post-Rollback Verification

Confirm worktree matches base state:
```bash
git rev-parse HEAD
# Expected: bce92340e1f7a0709a96e9526e0682fa0fcb1e32

git status
# Expected: nothing to commit, working tree clean
```

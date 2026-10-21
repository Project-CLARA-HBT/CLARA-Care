# Rollback Runbook: Mobile Flutter (PH01_A06)

## 1. Scope of Changes

This runbook covers the rollback procedure for all changes made by subagent `A06` in phase `PH01`:
1. `apps/mobile/android/app/src/debug/AndroidManifest.xml`: Added `android:usesCleartextTraffic="true"` to `<application>`.
2. `artifacts/PH01/A06/`: Deliverable reports and manifests.

---

## 2. Reversion Steps

### 2.1 Reverting Android Debug Cleartext Configuration
To revert `apps/mobile/android/app/src/debug/AndroidManifest.xml` back to base commit `2aa9016a57b49b53f1a433d076e1028a6ec45f64`:
```bash
git checkout 2aa9016a57b49b53f1a433d076e1028a6ec45f64 -- apps/mobile/android/app/src/debug/AndroidManifest.xml
```

### 2.2 Reverting Phase Artifacts
To remove the deliverables generated for `PH01/A06`:
```bash
rm -rf artifacts/PH01/A06
```

### 2.3 Verification After Rollback
```bash
git diff --check
git status
```
Working directory should return to clean state matching `2aa9016a57b49b53f1a433d076e1028a6ec45f64`.

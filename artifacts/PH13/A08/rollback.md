# PH13-A08 Rollback Procedure & Operational Runbook

**Phase:** PH13 — Connected Health và wearables  
**Agent:** A08 (Security + privacy)  
**Worktree:** `/dev/shm/clara_worktrees/PH13_A08`  
**Branch:** `phase/ph13-a08`  
**Base Commit SHA:** `bce92340e1f7a0709a96e9526e0682fa0fcb1e32`  
**Date:** November 2026  

---

## 1. Scope of Changes

Subagent A08 was assigned the `out-of-order replay simulations and wearable security threat model` for Connected Health và wearables. All modifications are strictly confined to A08's designated path lanes:
- `docs/security/WEARABLE_CONNECTED_HEALTH_THREAT_MODEL.md`
- `docs/compliance/WEARABLE_DATA_RETENTION_AND_PRIVACY_IMPACT_ASSESSMENT.md`
- `scripts/ops/simulate_wearable_security_threats.py`
- `scripts/ops/test_audit_wearable_security_simulations.py`
- `artifacts/PH13/A08/change_manifest.json`
- `artifacts/PH13/A08/test_report.md`
- `artifacts/PH13/A08/risk_register.md`
- `artifacts/PH13/A08/rollback.md`

No shared core application code, database migrations, or public schemas outside A08's lane were modified.

---

## 2. Fast Rollback via Feature Flags (Zero-Downtime Kill-Switch)

If any unexpected regression, batch replay anomaly, or token synchronization issue is observed in production, connected health capabilities can be disabled immediately without service downtime:

```bash
# Disable Connected Health UI
export CLARA_CONNECTED_HEALTH_UI=false

# Disable Health Connect device-side reading
export CLARA_HEALTH_CONNECT_READ=false

# Disable Huawei Health device-side reading
export CLARA_HUAWEI_HEALTH_READ=false

# Disable Fitbit cloud OAuth integration
export CLARA_FITBIT_OAUTH=false

# Disable Wearable LifeMap daily projection recomputation
export CLARA_WEARABLE_LIFEMAP_PROJECTION=false

# Disable Wearable context injection into Chat/Research harness
export CLARA_WEARABLE_ANSWER_CONTEXT=false
```

### Immediate Operational Effect:
- Client applications hide wearable connection prompts and transition to manual/neutral views.
- `POST /api/v1/connectors/{id}/imports` can be paused via `POST /api/v1/connectors/{id}/pause` or rejected.
- Daily aggregate recomputations are bypassed without affecting historical manual records.
- LifeMap and Ask CLARA continue serving confirmed clinical records without external wearable telemetry.

---

## 3. Git Worktree Rollback Procedure

To revert all changes committed by Subagent A08 in this worktree:

```bash
# 1. Navigate to the isolated worktree
cd /dev/shm/clara_worktrees/PH13_A08

# 2. Reset worktree hard to base commit SHA
git reset --hard bce92340e1f7a0709a96e9526e0682fa0fcb1e32

# 3. Clean untracked files and test artifacts
git clean -fd

# 4. Confirm clean status
git status
# Output: On branch phase/ph13-a08, nothing to commit, working tree clean
```

---

## 4. Operational Recovery & Disaster Containment

### 4.1 Token Exposure Incident Containment
If a third-party OAuth token or refresh credential is suspected of compromise:
1. Immediately invoke `disconnect()` on the affected connector:
   ```bash
   curl -X DELETE "https://api.clara.vn/api/v1/connectors/{connector_id}" \
     -H "Authorization: Bearer $ADMIN_OR_USER_TOKEN"
   ```
2. This atomically sets `token_ciphertext = NULL` and marks `ConnectorConsent.revoked_at = NOW()`.
3. Revoke the client token directly at the provider dashboard (e.g. Fitbit Developer Portal).

### 4.2 Replay or Corrupted Aggregate Remediation
If an out-of-order batch corrupts daily step aggregates:
1. Invoke imported data deletion:
   ```bash
   curl -X DELETE "https://api.clara.vn/api/v1/connectors/{connector_id}/imported-data" \
     -H "Authorization: Bearer $USER_TOKEN"
   ```
2. Re-trigger a fresh bounded sync from the client device adapter using the latest valid cursor.

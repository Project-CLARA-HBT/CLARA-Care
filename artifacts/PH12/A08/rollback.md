# PH12-A08 Rollback Procedure & Operational Runbook

**Phase:** PH12 — LifeMap longitudinal intelligence  
**Agent:** A08 (Security + privacy)  
**Worktree:** `/dev/shm/clara_worktrees/PH12_A08`  
**Branch:** `phase/ph12-a08`  
**Base Commit SHA:** `36e5b95fac7e65712f0779de253d8ed18dc693d7`  
**Date:** October 2026  

---

## 1. Scope of Changes

Subagent A08 was assigned the `longitudinal regression suite` and security/privacy review for LifeMap longitudinal intelligence. All modifications are strictly confined to A08's designated path lanes:
- `docs/security/LIFEMAP_LONGITUDINAL_SECURITY_AND_PRIVACY_THREAT_MODEL.md`
- `docs/compliance/LIFEMAP_LONGITUDINAL_DATA_RETENTION_AND_PRIVACY_ASSESSMENT.md`
- `scripts/ops/audit_longitudinal_security_regression.py`
- `scripts/ops/test_audit_longitudinal_security_regression.py`
- `artifacts/PH12/A08/change_manifest.json`
- `artifacts/PH12/A08/test_report.md`
- `artifacts/PH12/A08/risk_register.md`
- `artifacts/PH12/A08/rollback.md`

No shared core application code, database migrations, or public schemas outside A08's lane were modified.

---

## 2. Fast Rollback via Feature Flags (Zero-Downtime Kill-Switch)

If any unexpected regression, temporal boundary leakage, or projection cache anomaly is observed in production, longitudinal intelligence capabilities can be disabled immediately without service downtime:

```bash
# Disable Ask My LifeMap AI queries and semantic routing
export LIFEMAP_ASK_AI_ENABLED=false
export LIFEMAP_ASK_SEMANTIC_ROUTING_ENABLED=false

# Disable personal baseline computation if projection DAG issues arise
export LIFEMAP_BASELINES_V2_ENABLED=false

# Disable automated compliance retention cron sweep if lock contention occurs
export COMPLIANCE_RETENTION_JOB_ENABLED=false

# If running under Docker Compose
docker compose -f deploy/docker/docker-compose.app.yml exec api sh -c "
  export LIFEMAP_ASK_AI_ENABLED=false
  export LIFEMAP_ASK_SEMANTIC_ROUTING_ENABLED=false
  export LIFEMAP_BASELINES_V2_ENABLED=false
  export COMPLIANCE_RETENTION_JOB_ENABLED=false
"
```

### Immediate Operational Effect:
- `POST /api/v1/lifemap/v2/ask` returns HTTP 404 (`{"code": "feature_disabled"}`).
- Baseline recomputation drops back to inert static responses.
- Timeline queries (`GET /api/v1/lifemap/timeline`) continue serving confirmed clinical facts without AI synthesis.

---

## 3. Git Worktree Rollback Procedure

### Step 1: Revert Specific Files (Pre-Commit / Unstaged)
```bash
cd /dev/shm/clara_worktrees/PH12_A08

# Check working tree status
git status

# Revert unstaged modifications to security docs and ops scripts
git checkout 36e5b95fac7e65712f0779de253d8ed18dc693d7 -- \
  docs/security/LIFEMAP_LONGITUDINAL_SECURITY_AND_PRIVACY_THREAT_MODEL.md \
  docs/compliance/LIFEMAP_LONGITUDINAL_DATA_RETENTION_AND_PRIVACY_ASSESSMENT.md \
  scripts/ops/audit_longitudinal_security_regression.py \
  scripts/ops/test_audit_longitudinal_security_regression.py
```

### Step 2: Remove Generated Artifacts (Pre-Commit)
```bash
rm -rf artifacts/PH12/A08
```

### Step 3: Hard Reset to Base Commit (If Committed on Branch)
```bash
git checkout phase/ph12-a08
git reset --hard 36e5b95fac7e65712f0779de253d8ed18dc693d7
git clean -fd
```

### Step 4: Verification of Clean Worktree State
```bash
git rev-parse HEAD
# Expected output: 36e5b95fac7e65712f0779de253d8ed18dc693d7

git status --porcelain
# Expected output: (empty)
```

---

## 4. Post-Incident Cache Invalidation & Draft Cleanup

If an invalid or corrupted projection state is detected across longitudinal timelines:

### 4.1 Global Projection Cache Invalidation
To force complete invalidation of all cached projections for a given patient profile:
```python
from clara_api.db.session import SessionLocal
from clara_api.lifemap.projection_invalidation import invalidate_projection_graph

session = SessionLocal()
try:
    # Invalidate all projection nodes for target profile
    invalidated = invalidate_projection_graph(
        session,
        profile_id=TARGET_PROFILE_ID,
        reason="incident_rollback_purged",
        invalidate_all=True,
    )
    session.commit()
    print(f"Invalidated {len(invalidated)} projection nodes.")
finally:
    session.close()
```

### 4.2 Emergency Capture Draft Expiry Sweep
To immediately purge all expired or abandoned Universal Capture drafts and unlinked media objects:
```python
from clara_api.db.session import SessionLocal
from clara_api.lifemap.capture_cleanup import expire_capture_drafts

# Supply active object storage client
session = SessionLocal()
try:
    expired_count = expire_capture_drafts(session, store=storage_client, batch_size=500)
    print(f"Swept {expired_count} expired capture sessions and purged storage artifacts.")
finally:
    session.close()
```

Confirmed health events (`LifeMapEvent`, `LifeMapEventRevision`, `LifeMapEpisode`) remain safe, immutable, and preserved.

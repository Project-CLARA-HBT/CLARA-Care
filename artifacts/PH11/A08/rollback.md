# PH11-A08 Rollback Procedure & Operational Runbook

**Phase:** PH11 — FHIR R4 interoperability production profiles
**Agent:** A08 (Security + privacy)
**Worktree:** `/dev/shm/clara_worktrees/PH11_A08`
**Branch:** `phase/ph11-a08`
**Base Commit SHA:** `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`
**Date:** October 2026

---

## 1. Scope of Changes

Subagent A08 was assigned the `official validator conformance matrix` and security/privacy review for FHIR R4 interoperability. Changes are strictly confined to A08's designated path lanes:
- `docs/security/FHIR_R4_VALIDATOR_CONFORMANCE_AND_SECURITY_THREAT_MODEL.md`
- `docs/security/FHIR_PATIENT_IDENTIFICATION_AND_DEIDENTIFICATION_SPEC.md`
- `docs/compliance/FHIR_R4_INTEROPERABILITY_COMPLIANCE_ASSESSMENT.md`
- `scripts/ops/audit_fhir_validator_conformance.py`
- `scripts/ops/test_audit_fhir_validator_conformance.py`
- `artifacts/PH11/A08/*`

Zero database migrations or core API code changes were modified by A08.

---

## 2. Fast Rollback via Feature Flags (Zero-Downtime Kill-Switch)

If any security, privacy, or conformance regression occurs in a running deployment, FHIR export and import capabilities must be disabled immediately via environment configuration:

```bash
# Set environment variables to disable all FHIR R4 endpoints
export LIFEMAP_FHIR_EXPORT_ENABLED=false
export LIFEMAP_FHIR_IMPORT_ENABLED=false
export RAG_SCRIBE_FHIR_COMPOSITION_ENABLED=false

# If running under Docker Compose
docker compose -f deploy/docker/docker-compose.app.yml exec api sh -c "
  export LIFEMAP_FHIR_EXPORT_ENABLED=false
  export LIFEMAP_FHIR_IMPORT_ENABLED=false
  export RAG_SCRIBE_FHIR_COMPOSITION_ENABLED=false
"
```

### Immediate Effect:
- `GET /api/v1/lifemap/v2/export/fhir-r4` returns HTTP 404 (`{"code": "feature_disabled"}`).
- `POST /api/v1/lifemap/v2/import/fhir-r4` returns HTTP 404 (`{"code": "feature_disabled"}`).
- Zero clinical data can be imported or exfiltrated through FHIR channels.

---

## 3. Git Worktree Rollback Procedure

### Step 1: Revert Specific Files (Pre-Commit / Unstaged)
```bash
cd /dev/shm/clara_worktrees/PH11_A08

# Check working tree status
git status

# Revert any unstaged modifications
git checkout 85cef4b2d9a0e926ca684e9eeeba5e588ab11600 -- \
  docs/security/ \
  docs/compliance/ \
  scripts/ops/
```

### Step 2: Remove Generated Artifacts (Pre-Commit)
```bash
rm -rf artifacts/PH11/A08
```

### Step 3: Hard Reset to Base Commit (If Committed on Branch)
```bash
git checkout phase/ph11-a08
git reset --hard 85cef4b2d9a0e926ca684e9eeeba5e588ab11600
git clean -fd
```

### Step 4: Verification of Clean Worktree State
```bash
git rev-parse HEAD
# Expected output: 85cef4b2d9a0e926ca684e9eeeba5e588ab11600

git status --porcelain
# Expected output: (empty)
```

---

## 4. Quarantined Draft Ingestion Cleanup (Post-Incident)

If an invalid or untrusted external FHIR bundle was partially ingested before the kill-switch was toggled:
1. All imported items reside exclusively in the `LifeMapCaptureCandidate` table under `source_kind == 'fhir_r4_import'`.
2. To purge or quarantine the unreviewed candidates without touching confirmed medical truth:
   ```sql
   -- Identify unreviewed FHIR import candidates
   SELECT id, profile_id, candidate_type, created_at
   FROM lifemap_capture_candidates
   WHERE source_kind = 'fhir_r4_import'
     AND review_status = 'pending';

   -- Soft-delete / reject untrusted candidates
   UPDATE lifemap_capture_candidates
   SET review_status = 'rejected',
       notes = 'Incident rollback: unverified FHIR import purge'
   WHERE source_kind = 'fhir_r4_import'
     AND review_status = 'pending';
   ```
3. Confirmed health events (`LifeMapEvent`, `LifeMapEpisode`, `MedicationCourse`) remain intact and uncorrupted.

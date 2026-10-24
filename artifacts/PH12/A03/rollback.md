# Rollback Plan — Phase PH12 / Agent A03 (LifeMap Capture Extraction Service)

## Rollback Triggers
- Any regression in existing capture or timeline review endpoints (`/api/v1/lifemap/capture/*`).
- Unexpected OCC lock contention or deadlock under concurrent capture linking operations.
- Failure of GLHS continuity verification or cryptographic lineage mismatches.

## Fast Feature Flag Kill-Switch
The service is guarded behind the `lifemap_capture_extraction_service_enabled` feature flag. To instantly disable the service without redeploying:
```bash
export LIFEMAP_CAPTURE_EXTRACTION_SERVICE_ENABLED=false
```
When set to `false`, the domain service rejects incoming extraction operations with `CaptureExtractionServiceDisabledError` and zero data modifications take place.

## Code Rollback Procedure

To revert the entire changeset back to base commit `36e5b95facf155985012354e6005bb7097c36d0b`:

### Step 1: Revert Modified Core Files
```bash
git checkout 36e5b95facf155985012354e6005bb7097c36d0b -- \
  services/api/src/clara_api/core/config.py \
  services/api/src/clara_api/glhs/occ_locking_adapters.py
```

### Step 2: Remove Newly Created Service Module
```bash
rm -f services/api/src/clara_api/lifemap/capture_extraction_service.py
```

### Step 3: Remove Phase Artifacts
```bash
rm -rf artifacts/PH12/A03
```

### Step 4: Verify Repository State
```bash
git status
python3 -m compileall services/api/src/clara_api/
```
Ensure working tree is completely clean and matches `36e5b95facf155985012354e6005bb7097c36d0b`.

# Rollback Plan — PH11 A01 (FHIR CapabilityStatement API)

## 1. Fast Rollback (Configuration Toggle)
To immediately deactivate the FHIR CapabilityStatement API without code redeployment:
```bash
export FHIR_CAPABILITY_STATEMENT_ENABLED=false
```
When `FHIR_CAPABILITY_STATEMENT_ENABLED` is `false` (default), all queries to `/api/v1/fhir/metadata`, `/api/v1/fhir/CapabilityStatement`, and `/api/v1/fhir/conformance-rules` immediately fail closed with HTTP 404 (`fhir_capability_disabled`).

## 2. Full Code Rollback (Worktree Reversion)
To revert code changes back to the frozen baseline SHA `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`:

```bash
cd /dev/shm/clara_worktrees/PH11_A01

# Revert modified files
git checkout 85cef4b2d9a0e926ca684e9eeeba5e588ab11600 -- \
  services/api/src/clara_api/api/router.py \
  services/api/src/clara_api/schemas.py

# Remove new endpoints, contracts, and artifacts
rm -f services/api/src/clara_api/api/v1/endpoints/fhir.py
rm -rf contracts/fhir
rm -rf artifacts/PH11/A01
```

## 3. Post-Rollback Verification
Verify that the worktree is completely clean and matches the baseline commit:
```bash
git status --porcelain
git rev-parse HEAD
python3 -m compileall -q services/api/src/clara_api/api services/api/src/clara_api/schemas.py
```
Expected output: No untracked/modified files; commit matches `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`.

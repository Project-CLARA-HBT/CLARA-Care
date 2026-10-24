# Rollback Plan — Phase PH11 / A03 (MedicationStatement & AllergyIntolerance Domain Services)

## Impacted Artifacts & Scope
The changes introduced in branch `phase/ph11-a03` comprise:
1. `services/api/src/clara_api/core/config.py`: Added `fhir_r4_domain_mapping_enabled: bool = False`.
2. `services/api/src/clara_api/lifemap/fhir_r4.py`: Expanded `_RESOURCE_KEYS` for `MedicationStatement` and `AllergyIntolerance`.
3. `services/api/src/clara_api/glhs/fhir_mapping_service.py`: Domain mapping service and continuity engine.
4. `services/api/src/clara_api/lifemap/fhir_mapping.py`: LifeMap candidate mapping integration bridge.
5. `artifacts/PH11/A03/`: Verification tests and phase deliverables.

## Safe Rollback Procedure

To revert the entire changeset back to the base SHA `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`:

### Step 1: Revert Modified Core Files
```bash
git checkout 85cef4b2d9a0e926ca684e9eeeba5e588ab11600 -- \
  services/api/src/clara_api/core/config.py \
  services/api/src/clara_api/lifemap/fhir_r4.py
```

### Step 2: Remove Newly Added Modules
```bash
rm -f services/api/src/clara_api/glhs/fhir_mapping_service.py
rm -f services/api/src/clara_api/lifemap/fhir_mapping.py
```

### Step 3: Remove Phase Artifacts
```bash
rm -rf artifacts/PH11/A03
```

### Step 4: Verify Clean Tree
```bash
git status
```
Ensure working tree is completely clean and matches `85cef4b2d9a0e926ca684e9eeeba5e588ab11600`.

# Rollback Plan — PH11 A06 (Mobile Flutter: Web Integration Status Dashboard and FHIR Export View)

## 1. Zero-Deployment Rollback (Instant Kill-Switch)
The FHIR interoperability dashboard and consented export view are gated by the feature flag `fhir_interoperability_mobile_enabled`.
- In server response (`GET /api/v1/mobile/summary`): ensure `"fhir_interoperability_mobile_enabled": false`.
- Build-time constant defaults to `false` via `--dart-define=FHIR_INTEROPERABILITY_MOBILE_ENABLED=false`.
- When disabled, `MobileFeatureFlagResolver.fhirInteroperabilityEnabled` resolves to `false`, and `ProfileHub` completely omits the FHIR navigation entry, making the feature dark immediately without client updates.

## 2. Code Revert Procedure
If a complete code revert is required:
```bash
# Revert the phase commit on branch phase/ph11-a06
git revert --no-edit <commit-sha>

# Or remove created files and restore modified files:
git checkout 85cef4b2d9a0e926ca684e9eeeba5e588ab11600 -- \
  apps/mobile/lib/core/api_client.dart \
  apps/mobile/lib/core/feature_flags.dart \
  apps/mobile/lib/experience/connected_health/connected_health_screen.dart \
  apps/mobile/lib/experience/unified/profile_hub.dart

rm -rf apps/mobile/lib/experience/fhir/
rm -f apps/mobile/test/api_client_fhir_test.dart
rm -f apps/mobile/test/fhir_export_view_test.dart
rm -f apps/mobile/test/fhir_feature_flag_test.dart
rm -f apps/mobile/test/fhir_sync_dashboard_test.dart
rm -rf artifacts/PH11/A06/
```

## 3. Post-Rollback Verification
Run tests to verify the mobile suite remains green:
```bash
cd apps/mobile
/home/clue/development/flutter/bin/flutter test --no-pub test/a11y_test.dart
```
Verify path isolation and git status:
```bash
git status
```

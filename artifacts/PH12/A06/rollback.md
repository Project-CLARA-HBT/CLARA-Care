# Rollback Plan — PH12 A06 (Mobile Flutter: LifeMap Longitudinal Health Timeline)

## 1. Zero-Deployment Rollback (Instant Kill-Switch)
The LifeMap longitudinal health timeline is guarded by the feature flag `lifemap_timeline_mobile_enabled`.
- In server response (`GET /api/v1/mobile/summary`): ensure `"lifemap_timeline_mobile_enabled": false`.
- Build-time constant defaults to `false` via `--dart-define=LIFEMAP_TIMELINE_MOBILE_ENABLED=false`.
- When disabled, `MobileFeatureFlagResolver.lifeMapTimelineEnabled` resolves to `false`, allowing the feature to remain completely dark without client binary updates.

## 2. Code Revert Procedure
If a full code revert is required on branch `phase/ph12-a06`:
```bash
# Revert the phase commit on branch phase/ph12-a06:
git revert --no-edit <commit-sha>

# Or restore pre-change base files and remove new files:
git checkout 36e5b95fac7e65712f0779de253d8ed18dc693d7 -- \
  apps/mobile/lib/core/api_client.dart \
  apps/mobile/lib/core/feature_flags.dart \
  apps/mobile/lib/core/session_store.dart \
  apps/mobile/pubspec.yaml \
  apps/mobile/pubspec.lock \
  apps/mobile/test/api_client_lifemap_test.dart \
  apps/mobile/test/fakes/fake_api_client.dart \
  apps/mobile/test/feature_flags_test.dart

rm -f apps/mobile/lib/core/lifemap_timeline_cache.dart
rm -f apps/mobile/lib/core/lifemap_timeline_models.dart
rm -f apps/mobile/lib/widgets/lifemap_timeline_widget.dart
rm -f apps/mobile/test/lifemap_timeline_test.dart
rm -rf artifacts/PH12/A06/
```

## 3. Post-Rollback Verification
Run tests to verify the base mobile test suite passes cleanly:
```bash
cd apps/mobile
export PATH="/home/clue/development/flutter/bin:$PATH"
flutter test test/feature_flags_test.dart
flutter test test/lifemap_read_cache_test.dart
```

Verify git status is clean:
```bash
git status
```

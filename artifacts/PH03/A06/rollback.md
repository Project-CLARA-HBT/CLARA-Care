# Rollback Plan — PH03 A06 (Mobile Flutter)

## Rollback Triggers
1. Fatal crash or unhandled platform exception in `flutter_secure_storage` during hydration on legacy devices.
2. Users trapped in `_BiometricUnlockScreen` without fallback to password/re-login.
3. Cache eviction failure during password reset.

## Rollback Procedure
1. Revert branch commit on `phase/ph03-a06`:
   ```bash
   git revert <HANDOFF_COMMIT_SHA> -m 1
   ```
2. Or checkout specific files back to base commit `3b1072b98350b978b83b7ecec5c35228415759a3`:
   ```bash
   git checkout 3b1072b98350b978b83b7ecec5c35228415759a3 -- apps/mobile/
   ```
3. Verification:
   ```bash
   cd apps/mobile && flutter test --no-pub test/session_store_test.dart
   ```

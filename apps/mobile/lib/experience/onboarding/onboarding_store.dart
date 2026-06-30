import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Minimal key/value abstraction over the platform secure storage.
///
/// Mirrors the pattern in `lib/core/session_store.dart`: defining this
/// interface keeps [OnboardingStore] testable — production code uses
/// [FlutterSecureOnboardingStorage] (backed by `flutter_secure_storage`)
/// while tests can inject an in-memory implementation without platform
/// channels.
abstract class OnboardingSecureStorage {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
}

/// Default [OnboardingSecureStorage] backed by `flutter_secure_storage`.
class FlutterSecureOnboardingStorage implements OnboardingSecureStorage {
  FlutterSecureOnboardingStorage([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);
}

/// Persists the first-run "onboarding seen" flag for Experience_V2.
///
/// Thin, UI-free wrapper over `flutter_secure_storage` (no new dependency).
/// Graceful degradation is the core contract: if secure storage is
/// unavailable or a read fails, the store **fails open to "not seen"** so
/// onboarding still shows and launch never crashes — mirroring the
/// fail-closed/degrade discipline described in the design's Error Handling
/// section.
///
/// Callers (the onboarding carousel) are responsible for emitting any
/// analytics events; this store deliberately contains no analytics.
///
/// Validates: Requirements 1.5, 5.3, 9.2.
class OnboardingStore {
  OnboardingStore({OnboardingSecureStorage? storage})
      : _storage = storage ?? FlutterSecureOnboardingStorage();

  /// Secure-storage key for the persisted "onboarding seen" flag.
  ///
  /// Versioned (`_v2`) so it is namespaced to Experience_V2 and can be
  /// migrated independently of any future onboarding revision.
  static const String seenKey = 'clara_onboarding_seen_v2';

  /// Stored value written by [markSeen] to indicate onboarding was seen.
  static const String _seenValue = 'true';

  final OnboardingSecureStorage _storage;

  /// Whether the user has already completed or skipped onboarding.
  ///
  /// Returns `true` only when a truthy flag is persisted. On any storage read
  /// failure this returns `false` (degrade to "not seen"), so onboarding is
  /// shown rather than skipped and launch is never blocked.
  Future<bool> hasSeenOnboarding() async {
    try {
      final value = await _storage.read(seenKey);
      return value == _seenValue;
    } catch (_) {
      // Storage unavailable/unreadable: fail open to "not seen" so onboarding
      // still shows and the app never crashes on launch.
      return false;
    }
  }

  /// Persists that onboarding has been completed or skipped.
  ///
  /// A write failure is swallowed: persistence is best-effort and must never
  /// crash the flow. If the write fails, [hasSeenOnboarding] will simply
  /// return `false` next launch and onboarding will show again.
  Future<void> markSeen() async {
    try {
      await _storage.write(seenKey, _seenValue);
    } catch (_) {
      // Best-effort persistence; ignore storage failures.
    }
  }
}

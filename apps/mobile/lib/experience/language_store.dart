import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Minimal key/value abstraction over the platform secure storage.
///
/// Mirrors the pattern in `lib/core/session_store.dart`: defining this
/// interface keeps [LanguageStore] testable — production code uses
/// [FlutterSecureLanguageStorage] (backed by `flutter_secure_storage`)
/// while tests can inject an in-memory implementation without platform
/// channels.
abstract class LanguageSecureStorage {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
}

/// Default [LanguageSecureStorage] backed by `flutter_secure_storage`.
class FlutterSecureLanguageStorage implements LanguageSecureStorage {
  FlutterSecureLanguageStorage([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);
}

/// Persists the app-wide language preference for Experience_V2.
///
/// Thin, UI-free wrapper over `flutter_secure_storage` (no new dependency).
/// CLARA is **Vietnamese-first**: the default language code is `'vi'`. Graceful
/// degradation is the core contract — if secure storage is unavailable or a
/// read fails (or holds an empty value), [readLanguage] falls back to the
/// Vietnamese default and never crashes launch, mirroring the design's Error
/// Handling discipline.
///
/// Callers (the language controller) are responsible for emitting any analytics
/// events; this store deliberately contains no analytics.
///
/// Validates: Requirements 1.5, 5.3, 9.2.
class LanguageStore {
  LanguageStore({LanguageSecureStorage? storage})
      : _storage = storage ?? FlutterSecureLanguageStorage();

  /// Secure-storage key for the persisted language code.
  static const String languageKey = 'clara_language_v2';

  /// Vietnamese-first default language code, used on first run and whenever
  /// persistence is unavailable.
  static const String defaultLanguage = 'vi';

  final LanguageSecureStorage _storage;

  /// Returns the persisted language code, or [defaultLanguage] (`'vi'`).
  ///
  /// Falls back to the Vietnamese default when no value is stored, the stored
  /// value is empty, or the read fails for any reason — so the app always has
  /// a usable locale and launch is never blocked.
  Future<String> readLanguage() async {
    try {
      final value = await _storage.read(languageKey);
      if (value == null || value.isEmpty) {
        return defaultLanguage;
      }
      return value;
    } catch (_) {
      // Storage unavailable/unreadable: degrade to the Vietnamese default.
      return defaultLanguage;
    }
  }

  /// Persists the selected language [code].
  ///
  /// A write failure is swallowed: persistence is best-effort and must never
  /// crash the flow. If the write fails, [readLanguage] will return the
  /// Vietnamese default on the next launch.
  Future<void> writeLanguage(String code) async {
    try {
      await _storage.write(languageKey, code);
    } catch (_) {
      // Best-effort persistence; ignore storage failures.
    }
  }
}

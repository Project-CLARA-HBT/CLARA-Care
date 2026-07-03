import 'package:flutter/material.dart' show ThemeMode;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Minimal key/value abstraction over platform secure storage.
///
/// Mirrors `lib/experience/language_store.dart`: defining this interface keeps
/// [ThemePreferenceStore] testable \u2014 production uses
/// [FlutterSecureThemeStorage] (backed by `flutter_secure_storage`) while tests
/// inject an in-memory implementation without platform channels.
abstract class ThemeSecureStorage {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
}

/// Default [ThemeSecureStorage] backed by `flutter_secure_storage`.
class FlutterSecureThemeStorage implements ThemeSecureStorage {
  FlutterSecureThemeStorage([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);
}

/// Persists the app-wide theme-mode preference for the redesign
/// (clara-mobile-redesign, Requirement 1.2, 4.1).
///
/// Thin, UI-free wrapper over `flutter_secure_storage` (no new dependency). The
/// redesign is **light-mode-first**: the default is [ThemeMode.light], used on
/// first run and whenever persistence is unavailable. Graceful degradation is
/// the core contract \u2014 a missing/empty/unparseable value or a read failure
/// resolves to light and never blocks launch.
class ThemePreferenceStore {
  ThemePreferenceStore({ThemeSecureStorage? storage})
      : _storage = storage ?? FlutterSecureThemeStorage();

  /// Secure-storage key for the persisted theme mode.
  static const String themeKey = 'clara_theme_mode_v3';

  /// Light-mode-first default, used on first run and whenever persistence is
  /// unavailable (Requirement 1.2).
  static const ThemeMode defaultMode = ThemeMode.light;

  final ThemeSecureStorage _storage;

  /// Serializes a [ThemeMode] to its stored string form.
  static String encode(ThemeMode mode) {
    switch (mode) {
      case ThemeMode.light:
        return 'light';
      case ThemeMode.dark:
        return 'dark';
      case ThemeMode.system:
        return 'system';
    }
  }

  /// Parses a stored string into a [ThemeMode], falling back to [defaultMode]
  /// for anything missing/unknown (light-mode-first).
  static ThemeMode decode(String? value) {
    switch (value) {
      case 'light':
        return ThemeMode.light;
      case 'dark':
        return ThemeMode.dark;
      case 'system':
        return ThemeMode.system;
      default:
        return defaultMode;
    }
  }

  /// Returns the persisted theme mode, or [defaultMode] (light).
  ///
  /// Falls back to light when no value is stored, the value is empty/unknown,
  /// or the read fails for any reason \u2014 so the app always launches in a usable
  /// (light-first) theme.
  Future<ThemeMode> readThemeMode() async {
    try {
      final value = await _storage.read(themeKey);
      if (value == null || value.isEmpty) {
        return defaultMode;
      }
      return decode(value);
    } catch (_) {
      return defaultMode;
    }
  }

  /// Persists the selected [mode]. Best-effort: a write failure is swallowed so
  /// persistence never crashes the flow.
  Future<void> writeThemeMode(ThemeMode mode) async {
    try {
      await _storage.write(themeKey, encode(mode));
    } catch (_) {
      // Best-effort persistence; ignore storage failures.
    }
  }
}

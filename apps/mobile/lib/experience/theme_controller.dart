// App-wide theme-mode controller for the CLARA_Mobile redesign
// (clara-mobile-redesign, Requirement 1.2, 4.1).
//
// Holds the current [ThemeMode] for the redesigned experience and is read at the
// app root to drive `MaterialApp.themeMode`. The redesign is **light-mode-first**:
// the default mode is [ThemeMode.light] and any missing/unparseable stored value
// falls back to it (see `ThemePreferenceStore`).
//
// Responsibilities (this file):
//   * Hold the current [ThemeMode] as a `ChangeNotifier` so listeners (the app
//     root, the Settings theme control) rebuild when it changes.
//   * Load the persisted preference from [ThemePreferenceStore] on startup,
//     defaulting to light when nothing is stored or storage is unavailable.
//   * Persist a new selection, update state, and notify listeners.
//
// The store dependency is injectable so the controller is testable without
// platform channels (mirrors `LanguageController`).

import 'package:flutter/material.dart' show ChangeNotifier, ThemeMode;

import 'theme_store.dart';

/// App-wide theme-mode state for the redesign (Requirement 1.2, 4.1).
///
/// A [ChangeNotifier] holding the current [ThemeMode] (default
/// [ThemeMode.light]). Call [load] once at startup to hydrate from
/// [ThemePreferenceStore], then [setThemeMode] to change it; listeners (the app
/// root and the Settings theme control) rebuild on change.
class ThemeController extends ChangeNotifier {
  ThemeController({ThemePreferenceStore? store})
      : _store = store ?? ThemePreferenceStore();

  final ThemePreferenceStore _store;

  /// Current theme mode; starts light-first so the app always has a usable
  /// theme even before [load] completes.
  ThemeMode _themeMode = ThemePreferenceStore.defaultMode;

  /// The current [ThemeMode] for `MaterialApp.themeMode`.
  ThemeMode get themeMode => _themeMode;

  /// Hydrates the current theme mode from [ThemePreferenceStore].
  ///
  /// The store already defaults to light and degrades gracefully on failure;
  /// this notifies listeners only when the value actually changes. Safe to call
  /// once at startup.
  Future<void> load() async {
    final stored = await _store.readThemeMode();
    if (stored == _themeMode) {
      return;
    }
    _themeMode = stored;
    notifyListeners();
  }

  /// Selects [mode] as the app-wide theme mode.
  ///
  /// No-ops when the mode is unchanged. Otherwise persists the selection
  /// (best-effort; the store swallows storage failures), updates state, and
  /// notifies listeners so the theme applies app-wide.
  Future<void> setThemeMode(ThemeMode mode) async {
    if (mode == _themeMode) {
      return;
    }
    _themeMode = mode;
    await _store.writeThemeMode(mode);
    notifyListeners();
  }
}

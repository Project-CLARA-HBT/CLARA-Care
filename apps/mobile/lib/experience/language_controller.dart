// App-wide language controller for CLARA_Mobile Experience_V2 (Req 9.1, 9.2, 9.6).
//
// Holds the current UI language for the modern experience and is read at the
// app root to apply the locale app-wide (the actual `MaterialApp` locale wiring
// is task 9.2). CLARA is **Vietnamese-first**: the default language code is
// `'vi'` and any unsupported/unknown code falls back to it.
//
// Responsibilities (this file):
//   * Hold the current language code as a `ChangeNotifier` so listeners (the
//     Settings toggle, the app root) rebuild when it changes.
//   * Load the persisted preference from [LanguageStore] on startup, defaulting
//     to Vietnamese when nothing is stored or storage is unavailable.
//   * Persist a new selection via [LanguageStore.writeLanguage], update state,
//     notify listeners, and emit a single coarse, **no-PII** analytics event.
//
// Privacy (Req 9.6): the analytics event carries only the 2-letter language
// code (`'vi'` / `'en'`) under the key `'language'`. A locale code is NOT PII —
// no names, contact info, free text, or medical content is ever attached. The
// event is emitted through the shared consent/PII-guarded client, which no-ops
// without consent/credentials and never throws.
//
// The widget/store/analytics dependencies are injectable so the controller is
// testable without platform channels (mirrors the `OnboardingGate` pattern).

import 'package:flutter/widgets.dart';

import '../core/analytics.dart';
import 'language_store.dart';

/// Coarse, no-PII analytics event emitted when the user changes the language.
///
/// Passed as a string literal (rather than a `MobileAnalyticsEvents` constant)
/// because `analytics.dart` is owned by another concern and is not edited here.
/// It carries only a 2-letter language code under [kLanguageEventProp] — a
/// locale code is not PII (Req 9.6).
const String kLanguageChangedEvent = 'mobile_language_changed';

/// Property key for the (non-PII) 2-letter language code on
/// [kLanguageChangedEvent].
const String kLanguageEventProp = 'language';

/// App-wide language state for Experience_V2 (Req 9.1, 9.2, 9.6).
///
/// A [ChangeNotifier] holding the current 2-letter language code (default
/// `'vi'`). Call [load] once at startup to hydrate from [LanguageStore], then
/// [setLanguage] to change it; listeners (e.g. the app root and the Settings
/// toggle) rebuild on change.
///
/// Validates: Requirements 9.1, 9.2, 9.6.
class LanguageController extends ChangeNotifier {
  LanguageController({LanguageStore? store, Analytics? analytics})
      : _store = store ?? LanguageStore(),
        _analytics = analytics ?? getAnalyticsClient();

  /// Supported language codes. CLARA is Vietnamese-first, so `'vi'` is first
  /// and is the default/fallback; `'en'` is the secondary option.
  static const List<String> supported = <String>['vi', 'en'];

  final LanguageStore _store;
  final Analytics _analytics;

  /// Current 2-letter language code; starts at the Vietnamese default so the
  /// app always has a usable locale even before [load] completes.
  String _languageCode = LanguageStore.defaultLanguage;

  /// The current 2-letter language code (`'vi'` or `'en'`).
  String get languageCode => _languageCode;

  /// The current [Locale], derived from [languageCode], for `MaterialApp`.
  Locale get locale => Locale(_languageCode);

  /// Whether [code] is a supported language code.
  static bool isSupported(String code) => supported.contains(code);

  /// Normalizes [code] to a supported code, falling back to the Vietnamese
  /// default for anything unknown (Req 9.1).
  static String _normalize(String code) =>
      isSupported(code) ? code : LanguageStore.defaultLanguage;

  /// Hydrates the current language from [LanguageStore].
  ///
  /// Reads the persisted code (the store already defaults to `'vi'` and
  /// degrades gracefully on storage failure), normalizes any unknown value to
  /// the Vietnamese default, and notifies listeners only when the value
  /// actually changes. Safe to call once at startup.
  Future<void> load() async {
    final stored = await _store.readLanguage();
    final next = _normalize(stored);
    if (next == _languageCode) {
      return;
    }
    _languageCode = next;
    notifyListeners();
  }

  /// Selects [code] as the app-wide language.
  ///
  /// Unsupported codes are ignored (no state change, no persistence, no event)
  /// so the controller always holds a valid, supported code (Req 9.1). For a
  /// supported, changed code this persists the selection via
  /// [LanguageStore.writeLanguage] (Req 9.2), updates state, notifies
  /// listeners so the locale applies app-wide, and emits a single coarse,
  /// no-PII analytics event carrying only the 2-letter code (Req 9.6).
  Future<void> setLanguage(String code) async {
    if (!isSupported(code) || code == _languageCode) {
      return;
    }
    _languageCode = code;
    // Persist first (best-effort; the store swallows storage failures), then
    // notify so the UI/locale update even if persistence is unavailable.
    await _store.writeLanguage(code);
    notifyListeners();
    // Coarse, no-PII event: a 2-letter locale code is not PII (Req 9.6). The
    // shared client no-ops without consent/credentials and never throws.
    _analytics.track(
      kLanguageChangedEvent,
      props: <String, Object?>{kLanguageEventProp: code},
    );
  }
}

// Wave 10 quality-gate: language persistence + Vietnamese default
// (CLARA mobile experience spec, task 10.4 — Property P6).
//
// Property P6 (design §"Correctness Properties"): the app defaults to
// Vietnamese, and a persisted language selection round-trips across a restart
// and applies app-wide.
//   Validates: Requirements 9.1, 9.2.
//
// These cases exercise the real `LanguageController` + `LanguageStore` against
// an in-memory `LanguageSecureStorage` (no platform channels, Requirement 10.5)
// and assert the controller's `locale` (what `app.dart` feeds `MaterialApp`)
// follows the persisted selection. A fresh controller over the SAME storage
// models an app restart.

import 'package:clara_mobile/experience/language_controller.dart';
import 'package:clara_mobile/experience/language_store.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

/// In-memory [LanguageSecureStorage] so the controller's persistence is
/// exercised deterministically without `flutter_secure_storage`.
class _InMemoryLanguageStorage implements LanguageSecureStorage {
  _InMemoryLanguageStorage([Map<String, String>? seed])
      : _data = <String, String>{...?seed};

  final Map<String, String> _data;

  bool containsKey(String key) => _data.containsKey(key);

  @override
  Future<String?> read(String key) async => _data[key];

  @override
  Future<void> write(String key, String value) async => _data[key] = value;
}

void main() {
  group('Language default (Property P6, Req 9.1)', () {
    test('a brand-new controller defaults to Vietnamese before load', () {
      final controller = LanguageController(
        store: LanguageStore(storage: _InMemoryLanguageStorage()),
      );
      expect(controller.languageCode, 'vi');
      expect(controller.locale, const Locale('vi'));
    });

    test('load over empty storage keeps the Vietnamese default', () async {
      final controller = LanguageController(
        store: LanguageStore(storage: _InMemoryLanguageStorage()),
      );
      await controller.load();
      expect(controller.languageCode, 'vi');
      expect(controller.locale, const Locale('vi'));
    });

    test('an unknown persisted code degrades to the Vietnamese default',
        () async {
      final storage = _InMemoryLanguageStorage(
        <String, String>{LanguageStore.languageKey: 'zz'},
      );
      final controller =
          LanguageController(store: LanguageStore(storage: storage));
      await controller.load();
      // Unknown/unsupported codes normalize to the Vietnamese default (Req 9.1).
      expect(controller.languageCode, 'vi');
    });
  });

  group('Language persistence round-trip (Property P6, Req 9.2)', () {
    test(
        'selecting English persists and a fresh controller restores it across '
        'restart', () async {
      final storage = _InMemoryLanguageStorage();

      // Session 1: user switches to English.
      final controller = LanguageController(
        store: LanguageStore(storage: storage),
      );
      await controller.load();
      expect(controller.languageCode, 'vi');

      await controller.setLanguage('en');
      expect(controller.languageCode, 'en');
      expect(controller.locale, const Locale('en'));
      // The selection is persisted (Req 9.2).
      expect(storage.containsKey(LanguageStore.languageKey), isTrue);

      // Session 2 (restart): a fresh controller over the SAME storage restores
      // the persisted selection app-wide.
      final restored = LanguageController(
        store: LanguageStore(storage: storage),
      );
      await restored.load();
      expect(restored.languageCode, 'en');
      expect(restored.locale, const Locale('en'));
    });

    test('switching back to Vietnamese also round-trips across restart',
        () async {
      final storage = _InMemoryLanguageStorage(
        <String, String>{LanguageStore.languageKey: 'en'},
      );

      final controller = LanguageController(
        store: LanguageStore(storage: storage),
      );
      await controller.load();
      expect(controller.languageCode, 'en');

      await controller.setLanguage('vi');
      expect(controller.languageCode, 'vi');

      final restored = LanguageController(
        store: LanguageStore(storage: storage),
      );
      await restored.load();
      expect(restored.languageCode, 'vi');
    });

    test('selection notifies listeners so the locale applies app-wide',
        () async {
      final controller = LanguageController(
        store: LanguageStore(storage: _InMemoryLanguageStorage()),
      );
      await controller.load();

      var notifications = 0;
      controller.addListener(() => notifications++);

      await controller.setLanguage('en');
      // A change notifies listeners (the app root rebuilds MaterialApp.locale).
      expect(notifications, greaterThanOrEqualTo(1));

      // Re-selecting the same code is a no-op (no extra notification).
      final before = notifications;
      await controller.setLanguage('en');
      expect(notifications, before);
    });

    test('an unsupported selection is ignored (no state change, no persist)',
        () async {
      final storage = _InMemoryLanguageStorage();
      final controller = LanguageController(
        store: LanguageStore(storage: storage),
      );
      await controller.load();

      await controller.setLanguage('fr');
      expect(controller.languageCode, 'vi');
      // Nothing persisted for an unsupported code.
      expect(storage.containsKey(LanguageStore.languageKey), isFalse);
    });
  });
}

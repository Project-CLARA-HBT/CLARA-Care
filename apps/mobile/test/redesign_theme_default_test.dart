// clara-mobile-redesign, Requirement 1.2 (light-mode-first) regression lock.
//
// The redesign must default to light on first launch, regardless of OS setting.
// These tests pin that contract at the persistence + controller seam (the app
// root reads `ThemeController.themeMode` into `MaterialApp.themeMode`), using an
// in-memory secure-storage fake so no platform channel is needed.

import 'package:flutter/material.dart' show ThemeMode;
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/experience/theme_controller.dart';
import 'package:clara_mobile/experience/theme_store.dart';

/// In-memory [ThemeSecureStorage] so tests run without platform channels.
class _InMemoryThemeStorage implements ThemeSecureStorage {
  _InMemoryThemeStorage([Map<String, String>? seed])
      : _data = <String, String>{...?seed};

  final Map<String, String> _data;

  @override
  Future<String?> read(String key) async => _data[key];

  @override
  Future<void> write(String key, String value) async {
    _data[key] = value;
  }
}

void main() {
  group('ThemePreferenceStore (Req 1.2 light-mode-first)', () {
    test('defaultMode is light', () {
      expect(ThemePreferenceStore.defaultMode, ThemeMode.light);
    });

    test('empty storage resolves to light on first launch', () async {
      final store = ThemePreferenceStore(storage: _InMemoryThemeStorage());
      expect(await store.readThemeMode(), ThemeMode.light);
    });

    test('unknown/garbage stored value falls back to light', () async {
      final store = ThemePreferenceStore(
        storage: _InMemoryThemeStorage({
          ThemePreferenceStore.themeKey: 'not-a-mode',
        }),
      );
      expect(await store.readThemeMode(), ThemeMode.light);
    });

    test('encode/decode round-trips every mode', () async {
      for (final mode in ThemeMode.values) {
        final store = ThemePreferenceStore(storage: _InMemoryThemeStorage());
        await store.writeThemeMode(mode);
        expect(await store.readThemeMode(), mode);
      }
    });
  });

  group('ThemeController (Req 1.2, 4.1)', () {
    test('starts light before load and stays light with empty storage',
        () async {
      final controller = ThemeController(
        store: ThemePreferenceStore(storage: _InMemoryThemeStorage()),
      );
      expect(controller.themeMode, ThemeMode.light);
      await controller.load();
      expect(controller.themeMode, ThemeMode.light);
    });

    test('setThemeMode persists and notifies; reload restores it', () async {
      final storage = _InMemoryThemeStorage();
      final controller = ThemeController(
        store: ThemePreferenceStore(storage: storage),
      );

      var notified = 0;
      controller.addListener(() => notified++);

      await controller.setThemeMode(ThemeMode.dark);
      expect(controller.themeMode, ThemeMode.dark);
      expect(notified, 1);

      // A fresh controller over the same storage restores the dark choice.
      final restored = ThemeController(
        store: ThemePreferenceStore(storage: storage),
      );
      await restored.load();
      expect(restored.themeMode, ThemeMode.dark);
    });

    test('setThemeMode to the current mode is a no-op (no notify)', () async {
      final controller = ThemeController(
        store: ThemePreferenceStore(storage: _InMemoryThemeStorage()),
      );
      var notified = 0;
      controller.addListener(() => notified++);
      await controller.setThemeMode(ThemeMode.light); // already light
      expect(notified, 0);
    });
  });
}

// Unit tests for ThemeController.

import 'package:clara_mobile/experience/theme_controller.dart';
import 'package:clara_mobile/experience/theme_store.dart';
import 'package:flutter/material.dart' show ThemeMode;
import 'package:flutter_test/flutter_test.dart';

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
  group('ThemeController', () {
    test('defaults to ThemeMode.light before load', () {
      final controller = ThemeController(
        store: ThemePreferenceStore(storage: _InMemoryThemeStorage()),
      );
      expect(controller.themeMode, ThemeMode.light);
    });

    test('load hydrates stored ThemeMode and notifies listeners if changed', () async {
      final storage = _InMemoryThemeStorage({
        ThemePreferenceStore.themeKey: 'dark',
      });
      final controller = ThemeController(
        store: ThemePreferenceStore(storage: storage),
      );

      var notifications = 0;
      controller.addListener(() => notifications++);

      await controller.load();

      expect(controller.themeMode, ThemeMode.dark);
      expect(notifications, 1);
    });

    test('load does not notify listeners if stored mode matches current mode', () async {
      final storage = _InMemoryThemeStorage({
        ThemePreferenceStore.themeKey: 'light',
      });
      final controller = ThemeController(
        store: ThemePreferenceStore(storage: storage),
      );

      var notifications = 0;
      controller.addListener(() => notifications++);

      await controller.load();

      expect(controller.themeMode, ThemeMode.light);
      expect(notifications, 0);
    });

    test('setThemeMode updates state, persists mode, and notifies listeners', () async {
      final storage = _InMemoryThemeStorage();
      final controller = ThemeController(
        store: ThemePreferenceStore(storage: storage),
      );

      var notifications = 0;
      controller.addListener(() => notifications++);

      await controller.setThemeMode(ThemeMode.dark);

      expect(controller.themeMode, ThemeMode.dark);
      expect(notifications, 1);
      expect(storage._data[ThemePreferenceStore.themeKey], 'dark');
    });

    test('setThemeMode with identical value is a no-op', () async {
      final storage = _InMemoryThemeStorage();
      final controller = ThemeController(
        store: ThemePreferenceStore(storage: storage),
      );

      var notifications = 0;
      controller.addListener(() => notifications++);

      await controller.setThemeMode(ThemeMode.light);

      expect(controller.themeMode, ThemeMode.light);
      expect(notifications, 0);
      expect(storage._data.containsKey(ThemePreferenceStore.themeKey), isFalse);
    });

    test('persisted mode round-trips across controller instances', () async {
      final storage = _InMemoryThemeStorage();
      final controller1 = ThemeController(
        store: ThemePreferenceStore(storage: storage),
      );

      await controller1.setThemeMode(ThemeMode.system);
      expect(controller1.themeMode, ThemeMode.system);

      final controller2 = ThemeController(
        store: ThemePreferenceStore(storage: storage),
      );
      await controller2.load();
      expect(controller2.themeMode, ThemeMode.system);
    });
  });
}

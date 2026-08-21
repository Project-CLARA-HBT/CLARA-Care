// Unit tests for ThemePreferenceStore and ThemeSecureStorage.

import 'package:clara_mobile/experience/theme_store.dart';
import 'package:flutter/material.dart' show ThemeMode;
import 'package:flutter_test/flutter_test.dart';

class _InMemoryThemeStorage implements ThemeSecureStorage {
  _InMemoryThemeStorage([Map<String, String>? seed])
      : _data = <String, String>{...?seed};

  final Map<String, String> _data;
  bool throwOnRead = false;
  bool throwOnWrite = false;

  @override
  Future<String?> read(String key) async {
    if (throwOnRead) {
      throw StateError('Simulated read failure');
    }
    return _data[key];
  }

  @override
  Future<void> write(String key, String value) async {
    if (throwOnWrite) {
      throw StateError('Simulated write failure');
    }
    _data[key] = value;
  }
}

void main() {
  group('ThemePreferenceStore', () {
    test('defaultMode is ThemeMode.light (light-mode-first)', () {
      expect(ThemePreferenceStore.defaultMode, ThemeMode.light);
    });

    test('encode serializes ThemeMode values correctly', () {
      expect(ThemePreferenceStore.encode(ThemeMode.light), 'light');
      expect(ThemePreferenceStore.encode(ThemeMode.dark), 'dark');
      expect(ThemePreferenceStore.encode(ThemeMode.system), 'system');
    });

    test('decode parses serialized values and falls back safely', () {
      expect(ThemePreferenceStore.decode('light'), ThemeMode.light);
      expect(ThemePreferenceStore.decode('dark'), ThemeMode.dark);
      expect(ThemePreferenceStore.decode('system'), ThemeMode.system);
      expect(ThemePreferenceStore.decode(null), ThemePreferenceStore.defaultMode);
      expect(ThemePreferenceStore.decode(''), ThemePreferenceStore.defaultMode);
      expect(ThemePreferenceStore.decode('invalid_mode'), ThemePreferenceStore.defaultMode);
    });

    test('readThemeMode returns defaultMode when storage is empty', () async {
      final storage = _InMemoryThemeStorage();
      final store = ThemePreferenceStore(storage: storage);

      final mode = await store.readThemeMode();
      expect(mode, ThemeMode.light);
    });

    test('readThemeMode restores stored valid modes', () async {
      for (final mode in ThemeMode.values) {
        final storage = _InMemoryThemeStorage({
          ThemePreferenceStore.themeKey: ThemePreferenceStore.encode(mode),
        });
        final store = ThemePreferenceStore(storage: storage);

        expect(await store.readThemeMode(), mode);
      }
    });

    test('readThemeMode gracefully recovers on storage error', () async {
      final storage = _InMemoryThemeStorage()..throwOnRead = true;
      final store = ThemePreferenceStore(storage: storage);

      expect(await store.readThemeMode(), ThemeMode.light);
    });

    test('writeThemeMode persists mode and swallows write error', () async {
      final storage = _InMemoryThemeStorage();
      final store = ThemePreferenceStore(storage: storage);

      await store.writeThemeMode(ThemeMode.dark);
      expect(storage._data[ThemePreferenceStore.themeKey], 'dark');

      storage.throwOnWrite = true;
      // Should not throw
      await store.writeThemeMode(ThemeMode.system);
    });
  });
}

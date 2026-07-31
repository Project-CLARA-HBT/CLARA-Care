// Widget tests for the redesign Settings surface (Experience_V3).
//
// clara-mobile-redesign, Task 4.3 + Requirement 4 / 11. These lock the
// surface's behavior and safety invariants:
//
//   * The theme radio list drives `ThemeController.setThemeMode` (Req 4.2/1.3),
//     and the selected mode is conveyed by a text/semantics value (not color
//     alone).
//   * The language section is shown only when a `LanguageController` is
//     injected, and hidden otherwise (Req 4.3 / fail-closed rendering).
//   * Sign-out fully clears the session via `SessionStore.clear()` — the
//     authoritative step that routes the app root back to login (Req 4.4, 4.5).
//   * Account shows the signed-in email + a Vietnamese role label, never a raw
//     token/secret.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/experience/language_controller.dart';
import 'package:clara_mobile/experience/language_store.dart';
import 'package:clara_mobile/experience/redesign/settings_screen_v3.dart';
import 'package:clara_mobile/experience/theme_controller.dart';
import 'package:clara_mobile/experience/theme_store.dart';

import 'fakes/fakes.dart';

/// In-memory [ThemeSecureStorage] so the theme controller runs without platform
/// channels.
class _MemThemeStorage implements ThemeSecureStorage {
  final Map<String, String> _data = <String, String>{};
  @override
  Future<String?> read(String key) async => _data[key];
  @override
  Future<void> write(String key, String value) async => _data[key] = value;
}

/// In-memory [LanguageSecureStorage] so the language controller runs without
/// platform channels.
class _MemLangStorage implements LanguageSecureStorage {
  final Map<String, String> _data = <String, String>{};
  @override
  Future<String?> read(String key) async => _data[key];
  @override
  Future<void> write(String key, String value) async => _data[key] = value;
}

Future<PersistentSessionStore> _session({String role = 'normal'}) {
  return FakeSessionStore.authenticated(
    email: 'demo@example.com',
    role: role,
  );
}

Widget _host(Widget child) => MaterialApp(home: child);

void main() {
  group('SettingsScreenV3 (Requirement 4)', () {
    testWidgets('renders theme, account, and static sections', (tester) async {
      final store = await _session();
      final theme = ThemeController(
          store: ThemePreferenceStore(
        storage: _MemThemeStorage(),
      ));

      await tester.pumpWidget(_host(SettingsScreenV3(
        apiClient: FakeApiClient(),
        sessionStore: store,
        themeController: theme,
      )));
      await tester.pumpAndSettle();

      // Appearance section with all three modes.
      expect(find.text('Giao diện'), findsOneWidget);
      expect(find.text('Sáng'), findsOneWidget);
      expect(find.text('Tối'), findsOneWidget);
      expect(find.text('Hệ thống'), findsOneWidget);

      // Account section shows the signed-in email (no raw token).
      expect(find.text('demo@example.com'), findsOneWidget);
      expect(find.textContaining('test-access-token'), findsNothing);
    });

    testWidgets('picking a theme mode drives the controller', (tester) async {
      final store = await _session();
      final theme = ThemeController(
          store: ThemePreferenceStore(
        storage: _MemThemeStorage(),
      ));
      // Default is light.
      expect(theme.themeMode, ThemeMode.light);

      await tester.pumpWidget(_host(SettingsScreenV3(
        apiClient: FakeApiClient(),
        sessionStore: store,
        themeController: theme,
      )));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('theme-option-dark')));
      await tester.pumpAndSettle();

      expect(theme.themeMode, ThemeMode.dark);
    });

    testWidgets('language section is hidden without a controller',
        (tester) async {
      final store = await _session();
      await tester.pumpWidget(_host(SettingsScreenV3(
        apiClient: FakeApiClient(),
        sessionStore: store,
        // no languageController
      )));
      await tester.pumpAndSettle();

      expect(find.text('Ngôn ngữ'), findsNothing);
    });

    testWidgets('language section shows when a controller is injected',
        (tester) async {
      final store = await _session();
      final lang = LanguageController(
        store: LanguageStore(storage: _MemLangStorage()),
      );

      await tester.pumpWidget(_host(SettingsScreenV3(
        apiClient: FakeApiClient(),
        sessionStore: store,
        languageController: lang,
      )));
      await tester.pumpAndSettle();

      expect(find.text('Ngôn ngữ'), findsOneWidget);
    });

    testWidgets('updates Settings safety copy when the app language changes',
        (tester) async {
      final store = await _session();
      final lang = LanguageController(
        store: LanguageStore(storage: _MemLangStorage()),
      );

      await tester.pumpWidget(_host(SettingsScreenV3(
        apiClient: FakeApiClient(),
        sessionStore: store,
        languageController: lang,
      )));
      await tester.pumpAndSettle();

      expect(find.text('Quyền riêng tư & đồng ý'), findsOneWidget);
      expect(find.text('Thông báo minh bạch về AI'), findsOneWidget);

      await lang.setLanguage('en');
      await tester.pumpAndSettle();

      expect(find.text('Privacy & consent'), findsOneWidget);
      expect(find.text('AI transparency notice'), findsOneWidget);
      // The governed model identity remains a stable disclosure, not a
      // translated or fabricated model claim.
      expect(find.text('deepseek v4-pro'), findsOneWidget);
    });

    testWidgets('sign-out clears the session (routes app root to login)',
        (tester) async {
      final store = await _session();
      expect(store.isAuthenticated, isTrue);

      final api = FakeApiClient();
      // Best-effort server logout; the authoritative step is clear().
      api.stub('logout', response: const {});

      await tester.pumpWidget(_host(SettingsScreenV3(
        apiClient: api,
        sessionStore: store,
      )));
      await tester.pumpAndSettle();

      // Open the sign-out affordance and confirm.
      await tester.tap(find.text('Đăng xuất').first);
      await tester.pumpAndSettle();

      // A confirm dialog appears; confirm it.
      final confirm = find.text('Đăng xuất').last;
      await tester.tap(confirm);
      await tester.pumpAndSettle();

      expect(store.isAuthenticated, isFalse);
    });
  });
}

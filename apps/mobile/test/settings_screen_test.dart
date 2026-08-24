// Widget tests for unified Settings & Notifications surfaces (Spec v5 Section 7.9, 7.10).

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/lifemap_read_cache.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/experience/language_controller.dart';
import 'package:clara_mobile/experience/language_store.dart';
import 'package:clara_mobile/experience/theme_controller.dart';
import 'package:clara_mobile/experience/theme_store.dart';
import 'package:clara_mobile/experience/unified/notifications_surface.dart';
import 'package:clara_mobile/experience/unified/settings_surface.dart';

import 'fakes/fakes.dart';

class _MemThemeStorage implements ThemeSecureStorage {
  final Map<String, String> _data = <String, String>{};
  @override
  Future<String?> read(String key) async => _data[key];
  @override
  Future<void> write(String key, String value) async => _data[key] = value;
}

class _MemLangStorage implements LanguageSecureStorage {
  final Map<String, String> _data = <String, String>{};
  @override
  Future<String?> read(String key) async => _data[key];
  @override
  Future<void> write(String key, String value) async => _data[key] = value;
}

class _MemSessionStorage implements SessionSecureStorage {
  final Map<String, String> data = <String, String>{};
  @override
  Future<String?> read(String key) async => data[key];
  @override
  Future<void> write(String key, String value) async => data[key] = value;
  @override
  Future<void> delete(String key) async => data.remove(key);
}

Future<PersistentSessionStore> _session({String role = 'normal'}) {
  return FakeSessionStore.authenticated(
    email: 'user@example.com',
    role: role,
  );
}

Widget _host(Widget child) => MaterialApp(
      locale: const Locale('vi'),
      supportedLocales: const [Locale('vi'), Locale('en')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: child,
    );

void main() {
  group('SettingsSurface (Spec v5 Section 7.9)', () {
    testWidgets('renders theme selector with Light, Dark, and System options', (tester) async {
      final store = await _session();
      final theme = ThemeController(store: ThemePreferenceStore(storage: _MemThemeStorage()));

      await tester.pumpWidget(_host(SettingsSurface(
        apiClient: FakeApiClient(),
        sessionStore: store,
        themeController: theme,
      )));
      await tester.pumpAndSettle();

      expect(find.text('Giao diện'), findsOneWidget);
      expect(find.text('Sáng'), findsOneWidget);
      expect(find.text('Tối'), findsOneWidget);
      expect(find.text('Hệ thống'), findsOneWidget);

      expect(theme.themeMode, ThemeMode.light);
      await tester.tap(find.byKey(const Key('theme-option-dark')));
      await tester.pumpAndSettle();
      expect(theme.themeMode, ThemeMode.dark);

      await tester.tap(find.byKey(const Key('theme-option-system')));
      await tester.pumpAndSettle();
      expect(theme.themeMode, ThemeMode.system);
    });

    testWidgets('toggles Biometric authentication (FaceID/Fingerprint)', (tester) async {
      final store = await _session();

      await tester.pumpWidget(_host(SettingsSurface(
        apiClient: FakeApiClient(),
        sessionStore: store,
        initialBiometricEnabled: false,
      )));
      await tester.pumpAndSettle();

      final switchFinder = find.byKey(const Key('settings-biometric-switch'));
      await tester.scrollUntilVisible(
        switchFinder,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(switchFinder, findsOneWidget);
      expect(find.text('Bảo mật sinh trắc học'), findsOneWidget);
      expect(find.textContaining('FaceID / Vân tay'), findsOneWidget);

      await tester.tap(switchFinder);
      await tester.pumpAndSettle();

      final switchWidget = tester.widget<SwitchListTile>(switchFinder);
      expect(switchWidget.value, isTrue);
    });

    testWidgets('purges offline cache upon confirmation', (tester) async {
      final store = await _session();
      final sessionStorage = _MemSessionStorage();
      final cache = LifeMapReadCache(storage: sessionStorage, enabled: true);
      await cache.save({'tasks': [{'id': 't1', 'title': 'Take medicine'}]});
      expect(sessionStorage.data.containsKey(LifeMapReadCache.storageKey), isTrue);

      bool purgedCallbackCalled = false;

      await tester.pumpWidget(_host(SettingsSurface(
        apiClient: FakeApiClient(),
        sessionStore: store,
        lifeMapReadCache: cache,
        secureStorage: sessionStorage,
        onCachePurged: () => purgedCallbackCalled = true,
      )));
      await tester.pumpAndSettle();

      final purgeButtonFinder = find.byKey(const Key('settings-purge-cache-button'));
      await tester.scrollUntilVisible(
        purgeButtonFinder,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(purgeButtonFinder, findsOneWidget);

      await tester.tap(purgeButtonFinder);
      await tester.pumpAndSettle();

      // Confirmation dialog shows
      expect(find.byKey(const Key('confirm-purge-cache-dialog-button')), findsOneWidget);
      expect(find.text('Xóa dữ liệu'), findsOneWidget);

      await tester.tap(find.byKey(const Key('confirm-purge-cache-dialog-button')));
      await tester.pumpAndSettle();

      expect(purgedCallbackCalled, isTrue);
      expect(find.text('Đã xóa bộ nhớ đệm ngoại tuyến thành công.'), findsOneWidget);
    });

    testWidgets('displays security sessions and clears session on sign out', (tester) async {
      final store = await _session(role: 'consumer');
      final api = FakeApiClient();
      api.stub('logout', response: const {'logged_out': true});

      await tester.pumpWidget(_host(SettingsSurface(
        apiClient: api,
        sessionStore: store,
      )));
      await tester.pumpAndSettle();

      expect(find.text('Phiên đăng nhập & Bảo mật'), findsOneWidget);
      expect(find.text('user@example.com'), findsOneWidget);
      expect(find.text('Phiên thiết bị hiện tại'), findsOneWidget);
      expect(find.text('Ứng dụng CLARA Mobile • Đang hoạt động'), findsOneWidget);

      final signOutBtn = find.byKey(const Key('settings-sign-out-button'));
      await tester.tap(signOutBtn);
      await tester.pumpAndSettle();

      expect(find.textContaining('Bạn có chắc muốn đăng xuất khỏi CLARA'), findsOneWidget);
      await tester.tap(find.byKey(const Key('confirm-sign-out-dialog-button')));
      await tester.pumpAndSettle();

      expect(store.isAuthenticated, isFalse);
    });

    testWidgets('revoking other sessions triggers confirmation dialog and snackbar', (tester) async {
      final store = await _session();

      await tester.pumpWidget(_host(SettingsSurface(
        apiClient: FakeApiClient(),
        sessionStore: store,
      )));
      await tester.pumpAndSettle();

      final revokeBtn = find.byKey(const Key('settings-revoke-sessions-button'));
      await tester.tap(revokeBtn);
      await tester.pumpAndSettle();

      expect(find.text('Đăng xuất các thiết bị khác'), findsOneWidget);
      await tester.tap(find.text('Chấm dứt tất cả'));
      await tester.pumpAndSettle();

      expect(find.text('Đã chấm dứt tất cả các phiên đăng nhập khác.'), findsOneWidget);
    });

    testWidgets('tapping notifications tile invokes navigation or callback', (tester) async {
      final store = await _session();
      bool tapped = false;

      await tester.pumpWidget(_host(SettingsSurface(
        apiClient: FakeApiClient(),
        sessionStore: store,
        onNotificationsTap: () => tapped = true,
      )));
      await tester.pumpAndSettle();

      final tileFinder = find.byKey(const Key('settings-notifications-tile'));
      await tester.scrollUntilVisible(
        tileFinder,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      await tester.tap(tileFinder);
      await tester.pumpAndSettle();

      expect(tapped, isTrue);
    });
  });

  group('NotificationsSurface (Spec v5 Section 7.10)', () {
    testWidgets('renders push, email, SMS channel toggles and quiet hours', (tester) async {
      await tester.pumpWidget(_host(const NotificationsSurface()));
      await tester.pumpAndSettle();

      expect(find.text('Tùy chọn thông báo'), findsOneWidget);
      expect(find.text('Kênh nhận thông báo'), findsOneWidget);

      final pushSwitch = find.byKey(const Key('notification-channel-push-switch'));
      final emailSwitch = find.byKey(const Key('notification-channel-email-switch'));
      final smsSwitch = find.byKey(const Key('notification-channel-sms-switch'));
      final quietSwitch = find.byKey(const Key('notification-quiet-hours-switch'));

      expect(pushSwitch, findsOneWidget);
      expect(emailSwitch, findsOneWidget);
      expect(smsSwitch, findsOneWidget);
      expect(quietSwitch, findsOneWidget);

      // Toggle Push off then on
      await tester.tap(pushSwitch);
      await tester.pumpAndSettle();
      expect(tester.widget<SwitchListTile>(pushSwitch).value, isFalse);

      await tester.tap(pushSwitch);
      await tester.pumpAndSettle();
      expect(tester.widget<SwitchListTile>(pushSwitch).value, isTrue);
    });

    testWidgets('configures medication reminder schedules and safety alerts', (tester) async {
      await tester.pumpWidget(_host(const NotificationsSurface()));
      await tester.pumpAndSettle();

      final medToggle = find.byKey(const Key('notification-medication-toggle'));
      await tester.scrollUntilVisible(
        medToggle,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Lịch nhắc uống thuốc'), findsOneWidget);
      expect(medToggle, findsOneWidget);

      final morningSwitch = find.byKey(const Key('reminder-morning-switch'));
      final noonSwitch = find.byKey(const Key('reminder-noon-switch'));
      final eveningSwitch = find.byKey(const Key('reminder-evening-switch'));
      final nightSwitch = find.byKey(const Key('reminder-night-switch'));

      expect(morningSwitch, findsOneWidget);
      expect(noonSwitch, findsOneWidget);
      expect(eveningSwitch, findsOneWidget);
      expect(nightSwitch, findsOneWidget);

      expect(find.text('08:00'), findsOneWidget);
      expect(find.text('12:00'), findsOneWidget);
      expect(find.text('18:00'), findsOneWidget);
      expect(find.text('21:00'), findsOneWidget);

      // DDI Safety alert switch
      final ddiAlertSwitch = find.byKey(const Key('notification-ddi-alerts-switch'));
      await tester.scrollUntilVisible(
        ddiAlertSwitch,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      expect(ddiAlertSwitch, findsOneWidget);

      // Toggle noon slot checkbox
      await tester.tap(noonSwitch);
      await tester.pumpAndSettle();
      expect(tester.widget<Checkbox>(noonSwitch).value, isFalse);
    });

    testWidgets('configures care journey alerts and lifeMap milestone switches', (tester) async {
      await tester.pumpWidget(_host(const NotificationsSurface()));
      await tester.pumpAndSettle();

      final careJourneyToggle = find.byKey(const Key('notification-care-journey-toggle'));
      await tester.scrollUntilVisible(
        careJourneyToggle,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(careJourneyToggle, findsOneWidget);

      final milestonesSwitch = find.byKey(const Key('care-journey-milestones-switch'));
      final checkinsSwitch = find.byKey(const Key('care-journey-checkins-switch'));
      final vitalsSwitch = find.byKey(const Key('care-journey-vitals-switch'));

      await tester.scrollUntilVisible(
        vitalsSwitch,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(milestonesSwitch, findsOneWidget);
      expect(checkinsSwitch, findsOneWidget);
      expect(vitalsSwitch, findsOneWidget);

      await tester.tap(vitalsSwitch);
      await tester.pumpAndSettle();
      expect(tester.widget<SwitchListTile>(vitalsSwitch).value, isFalse);
    });

    testWidgets('configures family circle updates and proxy reminders', (tester) async {
      await tester.pumpWidget(_host(const NotificationsSurface()));
      await tester.pumpAndSettle();

      final familyToggle = find.byKey(const Key('notification-family-toggle'));
      await tester.scrollUntilVisible(
        familyToggle,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(familyToggle, findsOneWidget);

      final recordsSwitch = find.byKey(const Key('family-records-switch'));
      final emergencySwitch = find.byKey(const Key('family-emergency-switch'));
      final sharingSwitch = find.byKey(const Key('family-sharing-requests-switch'));

      await tester.scrollUntilVisible(
        sharingSwitch,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(recordsSwitch, findsOneWidget);
      expect(emergencySwitch, findsOneWidget);
      expect(sharingSwitch, findsOneWidget);

      await tester.tap(emergencySwitch);
      await tester.pumpAndSettle();
      expect(tester.widget<SwitchListTile>(emergencySwitch).value, isFalse);
    });

    testWidgets('displays not-a-doctor safety invariant notice and saves preferences', (tester) async {
      bool saved = false;
      await tester.pumpWidget(_host(NotificationsSurface(
        onSaved: () => saved = true,
      )));
      await tester.pumpAndSettle();

      final saveButton = find.byKey(const Key('save-notification-preferences-button'));
      await tester.scrollUntilVisible(
        saveButton,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      // Safety invariant notice
      expect(find.text('Lưu ý an toàn'), findsOneWidget);
      expect(
        find.textContaining('CLARA là trợ lý hỗ trợ y tế, không tự ý kê đơn'),
        findsOneWidget,
      );

      // Save action
      await tester.tap(saveButton);
      await tester.pumpAndSettle();

      expect(saved, isTrue);
      expect(find.text('Đã lưu tùy chọn thông báo thành công.'), findsOneWidget);
    });

    testWidgets('supports English localization dynamically', (tester) async {
      final lang = LanguageController(store: LanguageStore(storage: _MemLangStorage()));
      await lang.setLanguage('en');

      await tester.pumpWidget(_host(NotificationsSurface(
        languageController: lang,
      )));
      await tester.pumpAndSettle();

      expect(find.text('Notification Preferences'), findsOneWidget);
      expect(find.text('Delivery Channels'), findsOneWidget);
      expect(find.text('Medication Reminders'), findsOneWidget);

      final careJourneyTitle = find.text('Care Journey Alerts');
      await tester.scrollUntilVisible(
        careJourneyTitle,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      expect(careJourneyTitle, findsOneWidget);

      final familyTitle = find.text('Family Updates');
      await tester.scrollUntilVisible(
        familyTitle,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      expect(familyTitle, findsOneWidget);

      final saveBtn = find.text('Save Preferences');
      await tester.scrollUntilVisible(
        saveBtn,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      expect(saveBtn, findsOneWidget);
    });
  });
}

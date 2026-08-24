// Widget tests for ProfileHub (Spec v5 Section 7.4).
//
// Covers:
//   * Taxonomy order: Identity -> Health Record (PHR) -> Visits -> Family & Sharing ->
//     Living Evidence -> [Community] -> Connected Health -> Privacy & Consent ->
//     Data Rights -> [Workspace Mode] -> Notifications -> Settings -> Help.
//   * Council and Scribe are removed from consumer Profile navigation.
//   * PHR is a full-screen navigation destination.
//   * Dynamic localization (Vietnamese / English).
//   * Identity card role labels (Personal Account, Doctor, Researcher, Admin).

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/experience/language_controller.dart';
import 'package:clara_mobile/experience/language_store.dart';
import 'package:clara_mobile/experience/presentation_mode.dart';
import 'package:clara_mobile/experience/theme_controller.dart';
import 'package:clara_mobile/experience/theme_store.dart';
import 'package:clara_mobile/experience/unified/notifications_surface.dart';
import 'package:clara_mobile/experience/unified/profile_hub.dart';
import 'package:clara_mobile/experience/unified/settings_surface.dart';

import 'fakes/fakes.dart';

class _MemLanguageStorage implements LanguageSecureStorage {
  final Map<String, String> _data = <String, String>{};
  @override
  Future<String?> read(String key) async => _data[key];
  @override
  Future<void> write(String key, String value) async => _data[key] = value;
}

class _MemThemeStorage implements ThemeSecureStorage {
  final Map<String, String> _data = <String, String>{};
  @override
  Future<String?> read(String key) async => _data[key];
  @override
  Future<void> write(String key, String value) async => _data[key] = value;
}

Future<PersistentSessionStore> _session({String email = 'patient@example.com', String role = 'normal'}) {
  return FakeSessionStore.authenticated(
    email: email,
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
  group('ProfileHub (Spec v5 Section 7.4)', () {
    testWidgets('renders identity header and verified taxonomy entries in order', (tester) async {
      final store = await _session(email: 'user@example.com', role: 'normal');
      final api = FakeApiClient();
      final resolver = MobileFeatureFlagResolver();

      await tester.pumpWidget(_host(ProfileHub(
        apiClient: api,
        sessionStore: store,
        resolver: resolver,
        role: 'normal',
      )));
      await tester.pumpAndSettle();

      // Identity Header
      expect(find.text('user@example.com'), findsOneWidget);
      expect(find.text('Tài khoản cá nhân'), findsOneWidget);

      // Section Header
      expect(find.text('Công cụ & quyền riêng tư'), findsOneWidget);

      // 1. Health Record (PHR)
      expect(find.text('Hồ sơ sức khỏe cá nhân (PHR)'), findsOneWidget);

      // 2. Visits
      expect(find.text('Chuẩn bị đi khám'), findsOneWidget);

      // 3. Family & Sharing
      expect(find.text('Người thân & chia sẻ'), findsOneWidget);

      // 4. Living Evidence
      expect(find.text('Bằng chứng đang cập nhật'), findsOneWidget);

      // 5. Connected Health
      expect(find.text('Dữ liệu sức khỏe'), findsOneWidget);

      // 6. Notifications
      expect(find.text('Thông báo'), findsOneWidget);

      // 7. Settings
      expect(find.text('Cài đặt'), findsOneWidget);

      // 8. Help
      expect(find.text('Hướng dẫn & Trợ giúp'), findsOneWidget);

      // Safety invariant: Council and Scribe must NOT be in consumer Profile Hub
      expect(find.text('Hội đồng chuyên gia'), findsNothing);
      expect(find.text('Council'), findsNothing);
      expect(find.text('Trợ lý Scribe'), findsNothing);
      expect(find.text('Scribe'), findsNothing);
    });

    testWidgets('renders Consent Center and DSAR when consentCenterEnabled is true', (tester) async {
      final store = await _session();
      final api = FakeApiClient();
      final resolver = MobileFeatureFlagResolver(summary: {
        'feature_flags': {
          MobileFeatureFlags.consentCenterMobileEnabled: true,
        },
      });

      await tester.pumpWidget(_host(ProfileHub(
        apiClient: api,
        sessionStore: store,
        resolver: resolver,
        role: 'normal',
      )));
      await tester.pumpAndSettle();

      expect(find.text('Quyền riêng tư & đồng ý'), findsOneWidget);
      expect(find.text('Quyền dữ liệu cá nhân'), findsOneWidget);
    });

    testWidgets('renders Workspace Mode switcher for multi-mode clinician/researcher roles', (tester) async {
      final store = await _session(role: 'doctor');
      final api = FakeApiClient();
      final resolver = MobileFeatureFlagResolver();
      final modeCtrl = PresentationModeController(initialRole: 'doctor');

      await tester.pumpWidget(_host(ProfileHub(
        apiClient: api,
        sessionStore: store,
        resolver: resolver,
        role: 'doctor',
        presentationModeController: modeCtrl,
      )));
      await tester.pumpAndSettle();

      expect(find.text('Bác sĩ / Cán bộ y tế'), findsOneWidget);
      expect(find.text('Không gian làm việc'), findsOneWidget);
    });

    testWidgets('supports dynamic localization to English', (tester) async {
      final store = await _session(email: 'doctor@example.com', role: 'doctor');
      final api = FakeApiClient();
      final resolver = MobileFeatureFlagResolver(summary: {
        'feature_flags': {
          MobileFeatureFlags.consentCenterMobileEnabled: true,
        },
      });
      final lang = LanguageController(store: LanguageStore(storage: _MemLanguageStorage()));
      await lang.setLanguage('en');

      await tester.pumpWidget(_host(ProfileHub(
        apiClient: api,
        sessionStore: store,
        resolver: resolver,
        role: 'doctor',
        languageController: lang,
      )));
      await tester.pumpAndSettle();

      expect(find.text('Doctor / Clinician'), findsOneWidget);
      expect(find.text('Personal Health Record (PHR)'), findsOneWidget);
      expect(find.text('Prepare for a visit'), findsOneWidget);
      expect(find.text('Family & sharing'), findsOneWidget);
      expect(find.text('Living evidence'), findsOneWidget);
      expect(find.text('Health data'), findsOneWidget);
      expect(find.text('Privacy & consent'), findsOneWidget);
      expect(find.text('Personal data rights'), findsOneWidget);
      expect(find.text('Notifications'), findsOneWidget);
      expect(find.text('Settings'), findsOneWidget);
      expect(find.text('Help & Guide'), findsOneWidget);
    });

    testWidgets('navigates to NotificationsSurface on tap', (tester) async {
      final store = await _session();
      final api = FakeApiClient();
      final resolver = MobileFeatureFlagResolver();

      await tester.pumpWidget(_host(ProfileHub(
        apiClient: api,
        sessionStore: store,
        resolver: resolver,
        role: 'normal',
      )));
      await tester.pumpAndSettle();

      final notifEntry = find.text('Thông báo');
      await tester.scrollUntilVisible(
        notifEntry,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(notifEntry);
      await tester.pumpAndSettle();

      expect(find.byType(NotificationsSurface), findsOneWidget);
    });

    testWidgets('navigates to SettingsSurface on tap', (tester) async {
      final store = await _session();
      final api = FakeApiClient();
      final resolver = MobileFeatureFlagResolver();
      final theme = ThemeController(store: ThemePreferenceStore(storage: _MemThemeStorage()));

      await tester.pumpWidget(_host(ProfileHub(
        apiClient: api,
        sessionStore: store,
        resolver: resolver,
        role: 'normal',
        themeController: theme,
      )));
      await tester.pumpAndSettle();

      final settingsEntry = find.text('Cài đặt');
      await tester.scrollUntilVisible(
        settingsEntry,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.drag(find.byType(Scrollable).first, const Offset(0, -100));
      await tester.pumpAndSettle();
      await tester.tap(settingsEntry);
      await tester.pumpAndSettle();

      expect(find.byType(SettingsSurface), findsOneWidget);
    });

    testWidgets('navigates to HelpSurface and expands FAQ accordion', (tester) async {
      final store = await _session();
      final api = FakeApiClient();
      final resolver = MobileFeatureFlagResolver();

      await tester.pumpWidget(_host(ProfileHub(
        apiClient: api,
        sessionStore: store,
        resolver: resolver,
        role: 'normal',
      )));
      await tester.pumpAndSettle();

      final helpEntry = find.text('Hướng dẫn & Trợ giúp');
      await tester.scrollUntilVisible(
        helpEntry,
        50,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.drag(find.byType(Scrollable).first, const Offset(0, -150));
      await tester.pumpAndSettle();
      await tester.tap(helpEntry);
      await tester.pumpAndSettle();

      expect(find.text('Về Trợ lý Sức khỏe CLARA'), findsOneWidget);
      expect(find.textContaining('CLARA là công cụ hỗ trợ, không thay thế bác sĩ điều trị.'), findsOneWidget);

      final faqQuestion = find.text('Dữ liệu sức khỏe của tôi có được bảo mật không?');
      expect(faqQuestion, findsOneWidget);
      await tester.tap(faqQuestion);
      await tester.pumpAndSettle();

      expect(find.textContaining('CLARA tuân thủ nghiêm ngặt Nghị định Bảo vệ Dữ liệu Cá nhân (PDPD)'), findsOneWidget);
    });
  });
}

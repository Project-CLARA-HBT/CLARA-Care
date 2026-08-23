// Tests for the CLARA_Mobile unified experience (clara-mobile-unified).
//
// Covers:
//   * The `kMobileUnifiedEnabled` build flag defaults to false (fail-closed:
//     the unified root is never selected in a normal build) — Req 1.1, 9.1.
//   * `UnifiedOnboardingGate` routes on the server-backed PHR onboarding
//     status: `needs_onboarding: true` shows the onboarding flow; a completed
//     status shows the child app — Req 6.1, 6.4.
//   * A load error fails open (renders the child) so a flaky onboarding read
//     never strands the user — Req 6.1.

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/experience/language_controller.dart';
import 'package:clara_mobile/experience/language_store.dart';
import 'package:clara_mobile/experience/presentation_mode.dart';
import 'package:clara_mobile/experience/redesign/council_surface_v3.dart';
import 'package:clara_mobile/experience/redesign/scribe_surface_v3.dart';
import 'package:clara_mobile/experience/unified/onboarding_flow.dart';
import 'package:clara_mobile/experience/unified/profile_hub.dart';
import 'package:clara_mobile/experience/unified/unified_root.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fake_api_client.dart';
import 'fakes/fake_session_store.dart';

class _MemoryLanguageStorage implements LanguageSecureStorage {
  final Map<String, String> _values = <String, String>{};

  @override
  Future<String?> read(String key) async => _values[key];

  @override
  Future<void> write(String key, String value) async => _values[key] = value;
}

void main() {
  group('kMobileUnifiedEnabled', () {
    test('defaults to true — the unified experience is the shipped default',
        () {
      expect(kMobileUnifiedEnabled, isTrue);
    });
  });

  group('UnifiedOnboardingGate', () {
    late FakeApiClient api;
    late PersistentSessionStore session;

    setUp(() async {
      api = FakeApiClient();
      session = await FakeSessionStore.authenticated(role: 'normal');
    });

    Widget harness() => MaterialApp(
          home: UnifiedOnboardingGate(
            apiClient: api,
            sessionStore: session,
            child: const Scaffold(body: Text('CHILD_APP')),
          ),
        );

    testWidgets('shows the onboarding flow when needs_onboarding is true',
        (tester) async {
      api.stub('getPhrOnboarding', response: <String, dynamic>{
        'status': 'pending',
        'needs_onboarding': true,
        'record': <String, dynamic>{},
      });
      await tester.pumpWidget(harness());
      await tester.pumpAndSettle();

      expect(find.text('CHILD_APP'), findsNothing);
      expect(find.text('Chào mừng bạn đến với CLARA'), findsOneWidget);
    });

    testWidgets('shows the child app when onboarding is completed',
        (tester) async {
      api.stub('getPhrOnboarding', response: <String, dynamic>{
        'status': 'completed',
        'needs_onboarding': false,
        'record': <String, dynamic>{},
      });
      await tester.pumpWidget(harness());
      await tester.pumpAndSettle();

      expect(find.text('CHILD_APP'), findsOneWidget);
    });

    testWidgets('fails open to the child app when the onboarding read errors',
        (tester) async {
      api.stub(
        'getPhrOnboarding',
        error: ApiException(statusCode: 500, message: 'boom'),
      );
      await tester.pumpWidget(harness());
      await tester.pumpAndSettle();

      expect(find.text('CHILD_APP'), findsOneWidget);
    });

    testWidgets('does not block professional role (doctor) even when needs_onboarding is true',
        (tester) async {
      final doctorSession = await FakeSessionStore.authenticated(role: 'doctor');
      api.stub('getPhrOnboarding', response: <String, dynamic>{
        'status': 'pending',
        'needs_onboarding': true,
        'record': <String, dynamic>{},
      });

      await tester.pumpWidget(
        MaterialApp(
          home: UnifiedOnboardingGate(
            apiClient: api,
            sessionStore: doctorSession,
            child: const Scaffold(body: Text('CHILD_APP')),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Doctor is not blocked by personal PHR onboarding
      expect(find.text('CHILD_APP'), findsOneWidget);
      expect(find.text('Chào mừng bạn đến với CLARA'), findsNothing);
    });
  });

  group('UnifiedRoot language navigation', () {
    late FakeApiClient api;
    late PersistentSessionStore session;
    late LanguageController language;

    setUp(() async {
      api = FakeApiClient();
      session = await FakeSessionStore.authenticated(role: 'normal');
      language = LanguageController(
        store: LanguageStore(storage: _MemoryLanguageStorage()),
      );
      api.stub('getMobileSummary', response: <String, dynamic>{});
      api.stub('getPhrOnboarding', response: <String, dynamic>{
        'status': 'completed',
        'needs_onboarding': false,
        'record': <String, dynamic>{},
      });
    });

    testWidgets('rebuilds the unified task navigation after a locale change',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: UnifiedRoot(
            apiClient: api,
            sessionStore: session,
            languageController: language,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Hôm nay'), findsOneWidget);
      expect(find.text('Hành trình sức khỏe'), findsOneWidget);
      expect(find.text('Thuốc'), findsOneWidget);
      expect(find.text('Hồ sơ'), findsOneWidget);
      expect(find.text('Hỏi CLARA'), findsOneWidget);

      await language.setLanguage('en');
      await tester.pump();

      expect(find.text('Today'), findsOneWidget);
      expect(find.text('Health journey'), findsOneWidget);
      expect(find.text('Medicines'), findsOneWidget);
      expect(find.text('Profile'), findsOneWidget);
      expect(find.text('Ask CLARA'), findsOneWidget);
      expect(find.text('Hôm nay'), findsNothing);
    });

    testWidgets('rebuilds the Profile hub chrome and entry labels by locale',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: ProfileHub(
            apiClient: api,
            sessionStore: session,
            resolver: MobileFeatureFlagResolver(summary: const {}),
            role: 'normal',
            languageController: language,
            phrBody: const SizedBox(child: Text('PHR_BODY')),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Hồ sơ'), findsOneWidget);
      expect(find.text('Công cụ & quyền riêng tư'), findsOneWidget);
      expect(find.text('Chuẩn bị đi khám'), findsOneWidget);
      expect(find.text('Cài đặt'), findsOneWidget);

      await language.setLanguage('en');
      await tester.pump();

      expect(find.text('Profile'), findsOneWidget);
      expect(find.text('Tools & privacy'), findsOneWidget);
      expect(find.text('Prepare for a visit'), findsOneWidget);
      expect(find.text('Settings'), findsOneWidget);
      expect(find.text('Chuẩn bị đi khám'), findsNothing);
    });
  });

  group('UnifiedRoot dynamic role & presentation mode navigation', () {
    late FakeApiClient api;
    late PersistentSessionStore doctorSession;
    late PersistentSessionStore researcherSession;
    late PersistentSessionStore normalSession;
    late LanguageController language;

    setUp(() async {
      api = FakeApiClient();
      doctorSession = await FakeSessionStore.authenticated(role: 'doctor');
      researcherSession =
          await FakeSessionStore.authenticated(role: 'researcher');
      normalSession = await FakeSessionStore.authenticated(role: 'normal');
      language = LanguageController(
        store: LanguageStore(storage: _MemoryLanguageStorage()),
      );
      api.stub('getMobileSummary', response: <String, dynamic>{
        'feature_flags': {
          MobileFeatureFlags.scribeMobileEnabled: true,
        },
      });
      api.stub('getPhrOnboarding', response: <String, dynamic>{
        'status': 'completed',
        'needs_onboarding': false,
        'record': <String, dynamic>{},
      });
    });

    testWidgets(
        'Doctor defaults to Clinical mode with top-level Council and Scribe',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: UnifiedRoot(
            apiClient: api,
            sessionStore: doctorSession,
            languageController: language,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Clinical mode destinations are rendered at top level
      expect(find.text('Tổng quan'), findsOneWidget);
      expect(find.text('Hội chẩn'), findsOneWidget);
      expect(find.text('Hỏi CLARA'), findsWidgets);
      expect(find.text('Ghi chép'), findsOneWidget);
      expect(find.text('Thêm'), findsOneWidget);

      // Personal mode specific tabs are NOT rendered
      expect(find.text('Hôm nay'), findsNothing);
      expect(find.text('Hành trình sức khỏe'), findsNothing);
      expect(find.text('Thuốc'), findsNothing);

      // Tap Council -> CouncilSurfaceV3 is active
      await tester.tap(find.text('Hội chẩn'));
      await tester.pumpAndSettle();
      expect(find.byType(CouncilSurfaceV3), findsOneWidget);

      // Tap Ghi chép -> ScribeSurfaceV3 is active
      await tester.tap(find.text('Ghi chép'));
      await tester.pumpAndSettle();
      expect(find.byType(ScribeSurfaceV3), findsOneWidget);
    });

    testWidgets('Researcher defaults to Research mode navigation',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: UnifiedRoot(
            apiClient: api,
            sessionStore: researcherSession,
            languageController: language,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Research mode navigation: Hỏi CLARA | Bằng chứng | Nguồn | Thêm
      expect(find.text('Hỏi CLARA'), findsOneWidget);
      expect(find.text('Bằng chứng'), findsOneWidget);
      expect(find.text('Nguồn'), findsOneWidget);
      expect(find.text('Thêm'), findsOneWidget);

      // Clinical/Personal tabs not in primary navigation
      expect(find.text('Hôm nay'), findsNothing);
      expect(find.text('Tổng quan'), findsNothing);
      expect(find.text('Hội chẩn'), findsNothing);
    });

    testWidgets('Doctor dynamically switches between Clinical and Personal modes',
        (tester) async {
      final modeController =
          PresentationModeController(initialRole: 'doctor');
      expect(modeController.mode, PresentationMode.clinical);

      await tester.pumpWidget(
        MaterialApp(
          home: UnifiedRoot(
            apiClient: api,
            sessionStore: doctorSession,
            languageController: language,
            presentationModeController: modeController,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Starts in Clinical mode
      expect(find.text('Tổng quan'), findsOneWidget);
      expect(find.text('Hội chẩn'), findsOneWidget);
      expect(find.text('Ghi chép'), findsOneWidget);

      // Doctor switches to Personal mode
      modeController.setMode(PresentationMode.personal);
      await tester.pumpAndSettle();

      // Now renders Personal mode navigation
      expect(find.text('Hôm nay'), findsOneWidget);
      expect(find.text('Hành trình sức khỏe'), findsOneWidget);
      expect(find.text('Thuốc'), findsOneWidget);
      expect(find.text('Hồ sơ'), findsOneWidget);
      expect(find.text('Hỏi CLARA'), findsOneWidget);

      // Clinical-specific tabs are gone
      expect(find.text('Tổng quan'), findsNothing);
      expect(find.text('Hội chẩn'), findsNothing);
      expect(find.text('Ghi chép'), findsNothing);

      // Doctor switches to Research mode
      modeController.setMode(PresentationMode.research);
      await tester.pumpAndSettle();

      expect(find.text('Bằng chứng'), findsOneWidget);
      expect(find.text('Nguồn'), findsOneWidget);
      expect(find.text('Thêm'), findsOneWidget);
      expect(find.text('Hỏi CLARA'), findsOneWidget);
      expect(find.text('Hôm nay'), findsNothing);
    });

    testWidgets('ProfileHub provides mode switcher for doctor and researcher',
        (tester) async {
      final doctorModeController =
          PresentationModeController(initialRole: 'doctor');
      doctorModeController.setMode(PresentationMode.personal);

      await tester.pumpWidget(
        MaterialApp(
          home: ProfileHub(
            apiClient: api,
            sessionStore: doctorSession,
            resolver: MobileFeatureFlagResolver(summary: const {}),
            role: 'doctor',
            presentationModeController: doctorModeController,
            phrBody: const SizedBox(child: Text('PHR_BODY')),
          ),
        ),
      );
      await tester.pumpAndSettle();

      final workspaceModeFinder = find.text('Không gian làm việc');
      await tester.scrollUntilVisible(workspaceModeFinder, 100);
      await tester.pumpAndSettle();

      // Doctor has mode switcher in ProfileHub
      expect(workspaceModeFinder, findsOneWidget);
      expect(find.text('Cá nhân'), findsOneWidget);

      // Tap on workspace mode entry to open selector sheet
      await tester.tap(workspaceModeFinder);
      await tester.pumpAndSettle();

      // Selector sheet options are available
      expect(find.text('Lâm sàng'), findsOneWidget);
      expect(find.text('Nghiên cứu'), findsOneWidget);

      // Select Clinical mode
      await tester.tap(find.text('Lâm sàng'));
      await tester.pumpAndSettle();

      expect(doctorModeController.mode, PresentationMode.clinical);
    });

    testWidgets('ProfileHub does NOT provide mode switcher for normal user',
        (tester) async {
      final normalModeController =
          PresentationModeController(initialRole: 'normal');

      await tester.pumpWidget(
        MaterialApp(
          home: ProfileHub(
            apiClient: api,
            sessionStore: normalSession,
            resolver: MobileFeatureFlagResolver(summary: const {}),
            role: 'normal',
            presentationModeController: normalModeController,
            phrBody: const SizedBox(child: Text('PHR_BODY')),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Normal user does not have mode switcher
      expect(find.text('Không gian làm việc'), findsNothing);
    });
  });
}

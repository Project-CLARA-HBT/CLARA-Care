// Wave 10 quality-gate: full Experience_V2 happy path with the flag on
// (CLARA mobile experience spec, task 10.3).
//
// With Experience_V2 enabled the authenticated root is the first-run
// `OnboardingGate` wrapping the adaptive `AppShell` (Home / Hồ sơ / Ghi chú /
// Cài đặt). This pins the end-to-end happy path: onboarding → shell → Home
// renders WITHOUT exceptions across BOTH phone and tablet widths
// (Requirement 10.2).
//
// `kMobileExperienceV2Enabled` is a compile-time constant (default OFF), so a
// normal `flutter test` cannot flip it at runtime. We therefore construct the
// SAME V2 authenticated subtree the app builds behind the flag (see
// `app.dart` `_authenticatedRoot` when the flag is on) directly, exercising the
// real `OnboardingGate`, `AppShell`, and `HomeScreen` widgets — the integration
// the flag selects — under the shared `pumpExperience` harness with the real
// `ClaraTheme`. No platform channels, no live network (Requirement 10.5).

import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/experience/app_shell.dart';
import 'package:clara_mobile/experience/home_screen.dart';
import 'package:clara_mobile/experience/onboarding/onboarding_gate.dart';
import 'package:clara_mobile/experience/onboarding/onboarding_store.dart';
import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/screens/phr_screen.dart';
import 'package:clara_mobile/screens/scribe_screen.dart';
import 'package:clara_mobile/theme/clara_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../fakes/fakes.dart';
import '../support/experience_pump.dart';

/// In-memory [OnboardingSecureStorage] so the gate's persistence is exercised
/// deterministically without platform channels.
class _InMemoryOnboardingStorage implements OnboardingSecureStorage {
  _InMemoryOnboardingStorage([Map<String, String>? seed])
      : _data = <String, String>{...?seed};
  final Map<String, String> _data;
  @override
  Future<String?> read(String key) async => _data[key];
  @override
  Future<void> write(String key, String value) async => _data[key] = value;
}

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  /// Builds the V2 authenticated root: the [OnboardingGate] over the adaptive
  /// [AppShell] of primary destinations, mirroring `app.dart` with the flag on.
  Widget buildV2Root({
    required FakeApiClient api,
    required PersistentSessionStore session,
    required OnboardingStore onboardingStore,
  }) {
    return OnboardingGate(
      store: onboardingStore,
      child: AppShell(
        destinations: [
          ShellDestination(
            icon: Icons.home_outlined,
            selectedIcon: Icons.home,
            label: 'Trang chủ',
            body: HomeScreen(apiClient: api, sessionStore: session),
          ),
          ShellDestination(
            icon: Icons.folder_shared_outlined,
            selectedIcon: Icons.folder_shared,
            label: 'Hồ sơ',
            body: PhrScreen(
              apiClient: api,
              sessionStore: session,
              featureFlags: MobileFeatureFlagResolver(),
            ),
          ),
          ShellDestination(
            icon: Icons.mic_none,
            selectedIcon: Icons.mic,
            label: 'Ghi chú',
            body: ScribeScreen(
              apiClient: api,
              sessionStore: session,
              featureFlags: MobileFeatureFlagResolver(),
            ),
          ),
          const ShellDestination(
            icon: Icons.settings_outlined,
            selectedIcon: Icons.settings,
            label: 'Cài đặt',
            body: Scaffold(body: Center(child: Text('Cài đặt'))),
          ),
        ],
      ),
    );
  }

  /// A summary that lights up a couple of role-scoped quick actions on Home so
  /// the success path (not just the empty one) is exercised end to end.
  FakeApiClient apiWithSummary() {
    final api = FakeApiClient();
    api.stub('getMobileSummary', response: const {
      'feature_flags': {
        'research': true,
        'careguard': true,
        'chat_mobile_enabled': true,
      },
    });
    return api;
  }

  group('Experience_V2 happy path (flag-on integration, Req 10.2)', () {
    testWidgets(
        'first run: onboarding → shell → Home renders without exceptions at '
        'phone width', (tester) async {
      final api = apiWithSummary();
      final session = await FakeSessionStore.authenticated(role: 'normal');
      final onboardingStore =
          OnboardingStore(storage: _InMemoryOnboardingStorage());

      await pumpAtPhoneWidth(
        tester,
        buildV2Root(
          api: api,
          session: session,
          onboardingStore: onboardingStore,
        ),
        theme: ClaraTheme.light(),
      );
      await tester.pumpAndSettle();

      // First run shows the skippable onboarding carousel.
      expect(find.byKey(const Key('onboarding-pageview')), findsOneWidget);

      // Skip onboarding → the adaptive shell + Home become the root.
      await tester.tap(find.byKey(const Key('onboarding-skip')));
      await tester.pumpAndSettle();

      // Compact width ⇒ bottom navigation shell.
      expect(find.byType(NavigationBar), findsOneWidget);
      expect(find.byType(HomeScreen), findsOneWidget);
      // Home rendered its role-gated quick actions + the always-present PHR.
      expect(find.text('Hồ sơ sức khỏe'), findsOneWidget);
      expect(find.text('Nghiên cứu y khoa'), findsOneWidget);

      // No exception escaped the full first-run flow.
      expect(tester.takeException(), isNull);
    });

    testWidgets(
        'returning user (onboarding seen): shell + Home render without '
        'exceptions at tablet width', (tester) async {
      final api = apiWithSummary();
      final session = await FakeSessionStore.authenticated(role: 'doctor');
      // Pre-seed "seen" so the gate goes straight to the shell.
      final onboardingStore = OnboardingStore(
        storage: _InMemoryOnboardingStorage(
          <String, String>{OnboardingStore.seenKey: 'true'},
        ),
      );

      await pumpAtTabletWidth(
        tester,
        buildV2Root(
          api: api,
          session: session,
          onboardingStore: onboardingStore,
        ),
        theme: ClaraTheme.light(),
      );
      await tester.pumpAndSettle();

      // Returning user skips onboarding entirely.
      expect(find.byKey(const Key('onboarding-pageview')), findsNothing);
      // Expanded width ⇒ navigation rail shell.
      expect(find.byType(NavigationRail), findsOneWidget);
      expect(find.byType(HomeScreen), findsOneWidget);
      expect(find.text('Hồ sơ sức khỏe'), findsOneWidget);

      expect(tester.takeException(), isNull);
    });

    testWidgets(
        'navigating shell destinations after onboarding raises no exceptions',
        (tester) async {
      final api = apiWithSummary();
      final session = await FakeSessionStore.authenticated(role: 'normal');
      final onboardingStore = OnboardingStore(
        storage: _InMemoryOnboardingStorage(
          <String, String>{OnboardingStore.seenKey: 'true'},
        ),
      );

      await pumpAtPhoneWidth(
        tester,
        buildV2Root(
          api: api,
          session: session,
          onboardingStore: onboardingStore,
        ),
        theme: ClaraTheme.light(),
      );
      await tester.pumpAndSettle();

      // Switch to the Hồ sơ (PHR) destination, then to Cài đặt (Settings).
      await tester.tap(find.text('Hồ sơ').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cài đặt').last);
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
    });
  });
}

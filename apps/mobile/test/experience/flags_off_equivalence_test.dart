// Wave 10 quality-gate: flags-off equivalence (CLARA mobile experience spec,
// task 10.1 — Property P1).
//
// Property P1 (design §"Correctness Properties"): with
// `MOBILE_EXPERIENCE_V2_ENABLED` false, the authenticated root is the legacy
// `DashboardScreen`, NO Experience_V2 widget (`AppShell`, `HomeScreen`,
// `OnboardingGate`) is constructed, and the reachable navigation equals the
// pre-feature baseline.
//   Validates: Requirements 1.1, 1.2, 1.3, 10.1.
//
// `kMobileExperienceV2Enabled` is a compile-time `bool.fromEnvironment`
// constant that defaults to `false`; a normal `flutter test` run (no
// `--dart-define`) therefore exercises the flag-OFF branch of `app.dart`
// directly. This test drives the real `ClaraApp` end-to-end (hydrate → consent
// gate → authenticated root) with the reusable fakes, so it runs with no
// platform channels or live network (Requirement 10.5).
//
// A valid (future-exp) JWT is persisted so launch hydration RESTORES the
// session rather than clearing it as expired (the legacy `DashboardScreen`
// only renders for an authenticated session).

import 'dart:convert';

import 'package:clara_mobile/app.dart';
import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/experience/app_shell.dart';
import 'package:clara_mobile/experience/home_screen.dart';
import 'package:clara_mobile/experience/onboarding/onboarding_gate.dart';
import 'package:clara_mobile/screens/dashboard_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../fakes/fakes.dart';

/// Base64url-encodes a JSON map without padding (matches real JWT segments).
String _encodeSegment(Map<String, dynamic> map) =>
    base64Url.encode(utf8.encode(jsonEncode(map))).replaceAll('=', '');

/// Builds a real-looking JWT with a future `exp` so the store treats it as a
/// valid, non-expired credential during launch hydration.
String _validJwt() {
  final exp = DateTime.now()
          .toUtc()
          .add(const Duration(days: 30))
          .millisecondsSinceEpoch ~/
      1000;
  final header = _encodeSegment(const {'alg': 'HS256', 'typ': 'JWT'});
  final payload = _encodeSegment({'sub': 'u-1', 'exp': exp});
  return '$header.$payload.c2lnbmF0dXJl';
}

/// An authenticated [PersistentSessionStore] whose persisted access token is a
/// valid future-exp JWT (so `hydrate()` restores rather than clears it).
Future<PersistentSessionStore> _authenticatedWithValidJwt({
  String role = 'normal',
}) async {
  final store = PersistentSessionStore(storage: InMemorySessionSecureStorage());
  await store.setSession(
    email: 'user@example.com',
    accessToken: _validJwt(),
    refreshToken: _validJwt(),
    role: role,
  );
  return store;
}

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  group('Property P1 — flags-off equivalence (Req 1.1, 1.2, 1.3, 10.1)', () {
    testWidgets(
        'compile-time gate ships OFF so the baseline experience is the default',
        (tester) async {
      // The single Experience_V2 build gate must default to false: a normal
      // build (no --dart-define) is byte-for-byte the legacy experience.
      expect(kMobileExperienceV2Enabled, isFalse);
    });

    testWidgets(
        'authenticated root is the legacy DashboardScreen and no Experience_V2 '
        'widget is constructed', (tester) async {
      final api = FakeApiClient();
      // Consent already accepted so the gate passes straight to the root.
      api.stub('getConsentStatus', response: const {
        'accepted': true,
        'required_version': 'v1',
      });
      // Legacy dashboard loads the same role-scoped summary on init.
      api.stub('getMobileSummary', response: const {'feature_flags': {}});

      final session = await _authenticatedWithValidJwt();

      await tester.pumpWidget(
        ClaraApp(apiClient: api, sessionStore: session),
      );
      // Settle hydration + consent evaluation + summary load.
      await tester.pumpAndSettle();

      // The legacy authenticated root is present.
      expect(find.byType(DashboardScreen), findsOneWidget);

      // NONE of the Experience_V2 surfaces are constructed when the flag is off.
      expect(find.byType(AppShell), findsNothing);
      expect(find.byType(HomeScreen), findsNothing);
      expect(find.byType(OnboardingGate), findsNothing);

      // The locale-aware MaterialApp branch is only taken when the flag is on
      // AND a controller is injected; with the flag off there is no locale
      // wiring (supportedLocales stays at Flutter's default single entry).
      final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(app.locale, isNull);
    });

    testWidgets(
        'an unauthenticated launch never constructs an Experience_V2 surface',
        (tester) async {
      final api = FakeApiClient();
      // Empty store → not authenticated → login screen, never the V2 tree.
      final session =
          PersistentSessionStore(storage: InMemorySessionSecureStorage());

      await tester.pumpWidget(
        ClaraApp(apiClient: api, sessionStore: session),
      );
      await tester.pumpAndSettle();

      expect(find.byType(AppShell), findsNothing);
      expect(find.byType(HomeScreen), findsNothing);
      expect(find.byType(OnboardingGate), findsNothing);
      // The authenticated legacy root is not shown either (we are logged out).
      expect(find.byType(DashboardScreen), findsNothing);
    });
  });
}

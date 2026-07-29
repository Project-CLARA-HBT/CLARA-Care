// Unified-default root selection (spec: clara-mobile-unified, Phase 7.3).
//
// The unified client is now the shipped default (`MOBILE_UNIFIED_ENABLED`
// defaults to true), superseding the legacy Dashboard and Experience_V2. This
// test drives the real `ClaraApp` end-to-end (hydrate → consent gate →
// authenticated root) with the reusable fakes, asserting that:
//   * the authenticated root is the `UnifiedRoot`, and
//   * the legacy Experience_V2 build gate still ships OFF and none of its
//     surfaces (`AppShell`, `HomeScreen`, `OnboardingGate`) are constructed.
// It runs with no platform channels or live network.
//
// A valid (future-exp) JWT is persisted so launch hydration RESTORES the
// session rather than clearing it as expired (the authenticated root only
// renders for an authenticated session).

import 'dart:convert';

import 'package:clara_mobile/app.dart';
import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/experience/app_shell.dart';
import 'package:clara_mobile/experience/home_screen.dart';
import 'package:clara_mobile/experience/onboarding/onboarding_gate.dart';
import 'package:clara_mobile/experience/unified/unified_root.dart';
import 'package:clara_mobile/theme/web_palette.dart';
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
        'the Experience_V2 build gate still ships OFF (superseded by unified)',
        (tester) async {
      // The legacy Experience_V2 build gate must default to false: it is
      // superseded by the unified root and must never auto-construct.
      expect(kMobileExperienceV2Enabled, isFalse);
    });

    testWidgets(
        'authenticated root is the unified root and no Experience_V2 widget is '
        'constructed', (tester) async {
      final api = FakeApiClient();
      // Consent already accepted so the gate passes straight to the root.
      api.stub('getConsentStatus', response: const {
        'accepted': true,
        'required_version': 'v1',
      });
      // The unified root loads the role-scoped summary + onboarding on init.
      api.stub('getMobileSummary', response: const {'feature_flags': {}});
      api.stub('getPhrOnboarding', response: const {
        'needs_onboarding': false,
        'status': 'completed',
      });

      final session = await _authenticatedWithValidJwt();

      await tester.pumpWidget(
        ClaraApp(apiClient: api, sessionStore: session),
      );
      // Settle hydration + consent evaluation + summary/onboarding load.
      await tester.pumpAndSettle();

      // The unified authenticated root is present (default-on, Phase 7.3).
      expect(find.byType(UnifiedRoot), findsOneWidget);
      final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(app.theme?.colorScheme.primary, WebPalette.brand600);
      expect(app.theme?.scaffoldBackgroundColor, WebPalette.lightCanvas);
      expect(app.themeMode, ThemeMode.system);

      // NONE of the legacy Experience_V2 surfaces are constructed.
      expect(find.byType(AppShell), findsNothing);
      expect(find.byType(HomeScreen), findsNothing);
      expect(find.byType(OnboardingGate), findsNothing);
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
      // The authenticated unified root is not shown either (we are logged out).
      expect(find.byType(UnifiedRoot), findsNothing);
    });
  });
}

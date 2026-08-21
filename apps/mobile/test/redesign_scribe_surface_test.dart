// Widget tests for the redesigned Medical Scribe surface (Experience_V3).
//
// clara-mobile-redesign, Task 8.3. These lock the three fail-closed gating
// layers and the no-PII discipline:
//
//   * Gate 1 (flag) — `scribe_mobile_enabled` off ⇒ inert placeholder, ZERO
//     network calls.
//   * Gate 2 (role) — only `doctor` OR `admin` may reach the surface; every
//     other/missing role ⇒ placeholder, ZERO network calls.
//   * When both gates open (authorized doctor/admin), the session list loads.
//   * Analytics never receive clinical free text — only the coarse
//     `mobile_scribe_*` event names.

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/experience/redesign/scribe_surface_v3.dart';

import 'fakes/fakes.dart';

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

/// A resolver with `scribe_mobile_enabled` granted by the server summary.
MobileFeatureFlagResolver _scribeOn() => MobileFeatureFlagResolver(
      summary: const {
        'feature_flags': {'scribe_mobile_enabled': true},
      },
    );

/// A resolver with every gate off (fail-closed default).
MobileFeatureFlagResolver _allOff() => MobileFeatureFlagResolver();

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  group('ScribeSurfaceV3 — fail-closed gating (Requirement 8, INV-2/INV-4)',
      () {
    testWidgets('flag off ⇒ inert placeholder, zero network calls',
        (tester) async {
      final api = FakeApiClient();
      final store = await FakeSessionStore.authenticated(role: 'doctor');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _allOff(),
      )));
      await tester.pumpAndSettle();

      expect(find.text('Không khả dụng'), findsOneWidget);
      expect(api.wasCalled('listScribeSessions'), isFalse);
      expect(api.invocations, isEmpty);
    });

    testWidgets('unauthorized role ⇒ placeholder, zero network calls',
        (tester) async {
      final api = FakeApiClient();
      // Flag on, but a normal (non-doctor/non-admin) role stays fail-closed.
      final store = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
      )));
      await tester.pumpAndSettle();

      expect(find.text('Không khả dụng'), findsOneWidget);
      expect(api.invocations, isEmpty);
    });

    testWidgets('authorized doctor with the flag on loads the session list',
        (tester) async {
      final api = FakeApiClient()
        ..stub('listScribeSessions', response: {'items': <dynamic>[]});
      final store = await FakeSessionStore.authenticated(role: 'doctor');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
      )));
      await tester.pumpAndSettle();

      expect(api.wasCalled('listScribeSessions'), isTrue);
      expect(find.text('Không khả dụng'), findsNothing);
    });

    testWidgets('admin is authorized too (redesign widens doctor-only RBAC)',
        (tester) async {
      final api = FakeApiClient()
        ..stub('listScribeSessions', response: {'items': <dynamic>[]});
      final store = await FakeSessionStore.authenticated(role: 'admin');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
      )));
      await tester.pumpAndSettle();

      expect(api.wasCalled('listScribeSessions'), isTrue);
    });

    testWidgets('the screen-view analytics event carries no clinical text',
        (tester) async {
      final transport = RecordingAnalyticsTransport();
      final analytics = Analytics(transport: transport)
        ..init(
          const AnalyticsConfig(provider: 'test', apiKey: 'k'),
          consentGranted: true,
        );
      final api = FakeApiClient()
        ..stub('listScribeSessions', response: {'items': <dynamic>[]});
      final store = await FakeSessionStore.authenticated(role: 'doctor');

      await tester.pumpWidget(_host(ScribeSurfaceV3(
        apiClient: api,
        sessionStore: store,
        resolver: _scribeOn(),
        analytics: analytics,
      )));
      await tester.pumpAndSettle();

      // The only event is the coarse view event; it carries no props at all.
      expect(transport.capturedNames, contains('mobile_scribe_viewed'));
      for (final event in transport.captured) {
        expect(event.props, isEmpty,
            reason: 'Scribe analytics must never carry clinical content.');
      }
    });
  });
}

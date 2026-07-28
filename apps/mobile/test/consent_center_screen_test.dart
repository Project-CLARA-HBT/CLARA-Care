// Feature: clara-mobile-feature-parity — Task 10.1 (Req 8.1, 8.2, 8.4).
//
// Widget test for the granular consent center. It asserts the load-bearing
// invariant of the task: toggling the *analytics* purpose drives the shared
// `Analytics` facade — granting calls `setConsent(granted: true)` and
// withdrawing calls `setConsent(granted: false)` immediately (Requirement 8.4 /
// Property P7). It also confirms the surface is gated behind
// `consent_center_mobile_enabled` (Requirement 8.6 / 15.1).
//
// A real `ConsentStore` backed by an in-memory secure-storage seam drives the
// genuine persistence + facade-wiring plumbing without platform channels, and a
// spy `Analytics` records every `setConsent` call.

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/consent_state.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/screens/consent_center_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fakes.dart';

/// Spy over the production [Analytics] facade that records every consent flip.
class SpyAnalytics extends Analytics {
  SpyAnalytics() : super(transport: RecordingAnalyticsTransport());

  final List<bool> consentCalls = <bool>[];

  @override
  void setConsent({required bool granted}) {
    consentCalls.add(granted);
    super.setConsent(granted: granted);
  }
}

MobileFeatureFlagResolver _resolver({required bool consentEnabled}) {
  return MobileFeatureFlagResolver(
    summary: <String, dynamic>{
      'feature_flags': <String, dynamic>{
        MobileFeatureFlags.consentCenterMobileEnabled: consentEnabled,
      },
    },
  );
}

void main() {
  testWidgets(
      'toggling analytics consent drives Analytics.setConsent (grant=true, withdraw=false)',
      (tester) async {
    final spy = SpyAnalytics();
    final store = ConsentStore(
      storage: InMemorySessionSecureStorage(),
      analytics: spy,
    );
    final session = FakeSessionStore.empty();

    await tester.pumpWidget(MaterialApp(
      home: ConsentCenterScreen(
        resolver: _resolver(consentEnabled: true),
        sessionStore: session,
        consentStore: store,
      ),
    ));
    await tester.pumpAndSettle();

    // Analytics defaults to OFF (privacy-first); the switch reflects that.
    expect(store.isGranted(ConsentPurpose.analytics), isFalse);
    await tester.dragUntilVisible(
      find.text(ConsentPurpose.analytics.titleVi),
      find.byType(Scrollable),
      const Offset(0, -240),
    );

    final analyticsSwitch = find.ancestor(
      of: find.text(ConsentPurpose.analytics.titleVi),
      matching: find.byType(SwitchListTile),
    );
    expect(analyticsSwitch, findsOneWidget);

    // Grant analytics → facade receives setConsent(true).
    await tester.tap(analyticsSwitch);
    await tester.pumpAndSettle();
    expect(store.isGranted(ConsentPurpose.analytics), isTrue);
    expect(spy.consentCalls.last, isTrue);

    // Withdraw analytics → facade receives setConsent(false) immediately.
    await tester.tap(analyticsSwitch);
    await tester.pumpAndSettle();
    expect(store.isGranted(ConsentPurpose.analytics), isFalse);
    expect(spy.consentCalls.last, isFalse);
  });

  testWidgets('withdrawing analytics consent suppresses analytics transmission',
      (tester) async {
    // A real, *configured* facade so transmission would occur if consented.
    final transport = RecordingAnalyticsTransport();
    final analytics = Analytics(transport: transport)
      ..init(
        const AnalyticsConfig(provider: 'test', apiKey: 'k'),
        consentGranted: true,
      );
    final store = ConsentStore(
      storage: InMemorySessionSecureStorage(),
      analytics: analytics,
    );

    await tester.pumpWidget(MaterialApp(
      home: ConsentCenterScreen(
        resolver: _resolver(consentEnabled: true),
        sessionStore: FakeSessionStore.empty(),
        consentStore: store,
      ),
    ));
    await tester.pumpAndSettle();

    // load() synced the facade to the persisted analytics grant (false) →
    // transmission is suppressed even though credentials are present.
    await tester.dragUntilVisible(
      find.text(ConsentPurpose.analytics.titleVi),
      find.byType(Scrollable),
      const Offset(0, -240),
    );
    final analyticsSwitch = find.ancestor(
      of: find.text(ConsentPurpose.analytics.titleVi),
      matching: find.byType(SwitchListTile),
    );

    // Grant then withdraw; after withdrawal a capture must not transmit.
    await tester.tap(analyticsSwitch);
    await tester.pumpAndSettle();
    await tester.tap(analyticsSwitch);
    await tester.pumpAndSettle();

    transport.reset();
    analytics.capture(const AnalyticsEvent('post_withdraw_event'));
    expect(transport.transmissions, 0);
  });

  testWidgets('surface is gated off when consent_center flag is absent',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: ConsentCenterScreen(
        resolver: _resolver(consentEnabled: false),
        sessionStore: FakeSessionStore.empty(),
        consentStore: ConsentStore(
          storage: InMemorySessionSecureStorage(),
          analytics: SpyAnalytics(),
        ),
      ),
    ));
    await tester.pumpAndSettle();

    // No purpose toggles are exposed when the gate is off.
    expect(find.byType(SwitchListTile), findsNothing);
    expect(find.text('Tính năng này hiện chưa được bật.'), findsOneWidget);
  });
}

// Feature: clara-mobile-feature-parity — canonical consent ledger contract.
//
// The mobile screen must use the same server-owned, append-only consent ledger
// as web. These widget contracts keep it from regressing to a device-local
// switch that looks successful without changing policy enforcement.

import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/screens/consent_center_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fakes.dart';

MobileFeatureFlagResolver _resolver({required bool consentEnabled}) {
  return MobileFeatureFlagResolver(
    summary: <String, dynamic>{
      'feature_flags': <String, dynamic>{
        MobileFeatureFlags.consentCenterMobileEnabled: consentEnabled,
      },
    },
  );
}

Map<String, dynamic> _ledger({bool personalization = false}) =>
    <String, dynamic>{
      'enabled': true,
      'policy_version': '2026-04-v1',
      'consents': <String, bool>{
        'core_service': true,
        'ai_transparency': true,
        'personalization': personalization,
        'research': false,
        'cross_border_processing': false,
        'sharing': false,
      },
    };

void main() {
  testWidgets(
      'renders all six server ledger purposes including AI transparency',
      (tester) async {
    final api = FakeApiClient()
      ..stub('getComplianceConsents', response: _ledger());
    final session = await FakeSessionStore.authenticated();

    await tester.pumpWidget(MaterialApp(
      home: ConsentCenterScreen(
        apiClient: api,
        resolver: _resolver(consentEnabled: true),
        sessionStore: session,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Minh bạch AI'), findsOneWidget);
    expect(find.text('Xử lý bởi mô hình bên thứ ba / xuyên biên giới'),
        findsOneWidget);
    expect(api.wasCalled('getComplianceConsents'), isTrue);
  });

  testWidgets('a grant appends through the API then re-reads server truth',
      (tester) async {
    var personalization = false;
    final api = FakeApiClient()
      ..stub(
        'getComplianceConsents',
        responder: (_) => _ledger(personalization: personalization),
      )
      ..stub(
        'grantComplianceConsent',
        responder: (invocation) {
          expect(invocation.args['purpose'], 'personalization');
          personalization = true;
          return <String, dynamic>{};
        },
      );
    final session = await FakeSessionStore.authenticated();

    await tester.pumpWidget(MaterialApp(
      home: ConsentCenterScreen(
        apiClient: api,
        resolver: _resolver(consentEnabled: true),
        sessionStore: session,
      ),
    ));
    await tester.pumpAndSettle();

    final toggle = find.ancestor(
      of: find.text('Cá nhân hóa'),
      matching: find.byType(SwitchListTile),
    );
    await tester.tap(toggle);
    await tester.pumpAndSettle();

    expect(api.wasCalled('grantComplianceConsent'), isTrue);
    expect(
        api.callsTo('getComplianceConsents').length, greaterThanOrEqualTo(2));
  });

  testWidgets('a ledger failure fails closed without exposing switches',
      (tester) async {
    final api = FakeApiClient()
      ..stub('getComplianceConsents', error: StateError('unavailable'));
    final session = await FakeSessionStore.authenticated();

    await tester.pumpWidget(MaterialApp(
      home: ConsentCenterScreen(
        apiClient: api,
        resolver: _resolver(consentEnabled: true),
        sessionStore: session,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.byType(SwitchListTile), findsNothing);
    expect(
        find.text('Không thể tải trạng thái đồng ý lúc này. Vui lòng thử lại.'),
        findsOneWidget);
  });

  testWidgets('feature flag off exposes no control and makes no ledger request',
      (tester) async {
    final api = FakeApiClient();
    final session = await FakeSessionStore.authenticated();

    await tester.pumpWidget(MaterialApp(
      home: ConsentCenterScreen(
        apiClient: api,
        resolver: _resolver(consentEnabled: false),
        sessionStore: session,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.byType(SwitchListTile), findsNothing);
    expect(api.wasCalled('getComplianceConsents'), isFalse);
  });
}

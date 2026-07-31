// Widget tests for the redesigned Personal Medicine Cabinet (Experience_V3).
//
// clara-mobile-redesign, Task 5.4. These lock the regression-critical safety
// invariants of `CabinetScreenV3`:
//
//   * All-roles availability: the Personal Medicine Cabinet is offered to every
//     authenticated role, so it loads the consent status regardless of the
//     feature-flag summary — but the consent gate still governs medical content.
//   * Consent gate (INV-1): with consent not accepted, the cabinet contents/CRUD
//     are not shown; only the consent step renders (this is the real safety gate
//     ahead of any medicine data).
//   * Two-medicine guard (INV-5): the in-cabinet DDI check never calls the
//     owner-scoped `autoCheckCareguardCabinet` contract for fewer than two
//     distinct medicines.
//
// All fakes avoid platform channels and live network I/O.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/connectivity_service.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/experience/redesign/cabinet_screen_v3.dart';

import 'fakes/fakes.dart';

/// A resolver with the cabinet + careguard gates ON (built-time defaults are
/// off, so we feed a summary granting both for the role).
MobileFeatureFlagResolver _enabledResolver() => MobileFeatureFlagResolver(
      summary: const <String, dynamic>{
        'feature_flags': <String, dynamic>{
          'selfmed_cabinet_mobile_enabled': true,
          'careguard': true,
        },
      },
    );

/// A resolver with every gate off (fail-closed).
MobileFeatureFlagResolver _disabledResolver() =>
    MobileFeatureFlagResolver(summary: const <String, dynamic>{});

Widget _host(Widget child) => MaterialApp(home: child);

void main() {
  setUp(resetAnalyticsClientForTest);

  group('CabinetScreenV3 — safety invariants (Task 5.4)', () {
    testWidgets(
        'no feature flags ⇒ cabinet still available to the role (consent gate '
        'is the safety boundary, not a feature flag)', (tester) async {
      final api = FakeApiClient();
      // Consent not yet accepted so the consent gate stands; the point of this
      // test is that the surface is reachable for the role even with an empty
      // summary, then the consent gate — not a feature flag — protects content.
      api.stub('getConsentStatus', response: const {
        'accepted': false,
        'required_version': 'v1',
      });
      final store = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(_host(CabinetScreenV3(
        apiClient: api,
        sessionStore: store,
        resolver: _disabledResolver(),
        connectivity: DefaultConnectivityService(initialValue: true),
      )));
      await tester.pumpAndSettle();

      // The cabinet is offered to every role now, so it DOES check consent even
      // with an empty summary — but the consent gate still blocks the cabinet
      // contents until consent is accepted (INV-1).
      expect(api.wasCalled('getConsentStatus'), isTrue);
      expect(api.wasCalled('getCareguardCabinet'), isFalse);
      expect(find.text('Thêm thuốc'), findsNothing);
    });

    testWidgets('flag on but consent absent ⇒ cabinet CRUD is not shown',
        (tester) async {
      final api = FakeApiClient();
      // Consent not accepted: the gate must block cabinet contents.
      api.stub('getConsentStatus', response: const {
        'accepted': false,
        'required_version': 'v1',
      });
      final store = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(_host(CabinetScreenV3(
        apiClient: api,
        sessionStore: store,
        resolver: _enabledResolver(),
        connectivity: DefaultConnectivityService(initialValue: true),
      )));
      await tester.pumpAndSettle();

      // Consent was checked, but the cabinet was NEVER loaded because consent
      // is not accepted (INV-1).
      expect(api.wasCalled('getConsentStatus'), isTrue);
      expect(api.wasCalled('getCareguardCabinet'), isFalse);
      // The "add medicine" FAB (which only appears once consent is accepted) is
      // absent while the consent gate is up.
      expect(find.text('Thêm thuốc'), findsNothing);
    });

    testWidgets(
        'consent accepted with <2 distinct medicines ⇒ DDI never runs '
        '(two-medicine guard, INV-5)', (tester) async {
      final api = FakeApiClient();
      api.stub('getConsentStatus', response: const {
        'accepted': true,
        'required_version': 'v1',
      });
      // A single-item cabinet: below the two-medicine guard threshold.
      api.stub('getCareguardCabinet', response: const {
        'items': [
          {
            'id': 1,
            'drug_name': 'Paracetamol',
            'normalized_name': 'paracetamol'
          },
        ],
      });
      final store = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(_host(CabinetScreenV3(
        apiClient: api,
        sessionStore: store,
        resolver: _enabledResolver(),
        connectivity: DefaultConnectivityService(initialValue: true),
      )));
      await tester.pumpAndSettle();

      // Cabinet loaded (consent accepted), the item is shown.
      expect(api.wasCalled('getCareguardCabinet'), isTrue);
      expect(find.text('Paracetamol'), findsOneWidget);

      // Attempt the in-cabinet DDI check; the guard must block the analyze call.
      final ddiButton = find.text('Kiểm tra tương tác');
      expect(ddiButton, findsOneWidget);
      await tester.ensureVisible(ddiButton);
      await tester.tap(ddiButton);
      await tester.pumpAndSettle();

      // Fewer than two distinct medicines ⇒ auto-DDI was NOT called
      // (never fabricate an all-clear — INV-5).
      expect(api.wasCalled('autoCheckCareguardCabinet'), isFalse);
    });
  });
}

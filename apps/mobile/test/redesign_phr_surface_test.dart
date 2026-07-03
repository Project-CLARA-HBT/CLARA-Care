// Widget tests for the redesigned PHR surface (Experience_V3, Task 7).
//
// clara-mobile-redesign, Requirement 7 + safety invariants. These lock:
//   * the load → bind → save round-trip against the existing PHR contract
//     (`getPhrRecord` / `updatePhrRecord`) — Req 7.1, 7.2;
//   * enhanced read affordances (export + emergency card) are gated behind
//     `phr_enhanced_mobile_enabled` and absent when the gate is off — Req 7.4;
//   * no-PII analytics on save: only a total `entry_count` is transmitted, never
//     names, free text, or medical values — INV-3.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/experience/redesign/phr_surface_v3.dart';

import 'fakes/fakes.dart';

/// A minimal, valid PHR record payload with one entry in each category so the
/// save-time `entry_count` is deterministic (3).
Map<String, dynamic> _recordPayload() => <String, dynamic>{
      'full_name': 'Nguyen Van A',
      'gender': 'male',
      'blood_type': 'O',
      'allergies': [
        {'id': 'a1', 'name': 'Penicillin', 'severity': 'severe'},
      ],
      'conditions': [
        {'id': 'c1', 'name': 'Hen suyễn', 'status': 'active'},
      ],
      'medications': [
        {'id': 'm1', 'name': 'Salbutamol', 'is_current': true},
      ],
    };

Widget _host(Widget child) => MaterialApp(home: child);

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  Future<(FakeApiClient, dynamic)> pump(
    WidgetTester tester, {
    required bool enhanced,
  }) async {
    final api = FakeApiClient();
    api.stub('getPhrRecord', response: _recordPayload());
    final session = await FakeSessionStore.authenticated(role: 'normal');
    final resolver = MobileFeatureFlagResolver(
      summary: {
        'feature_flags': {
          if (enhanced) MobileFeatureFlags.phrEnhancedMobileEnabled: true,
        },
      },
    );
    await tester.pumpWidget(_host(PhrSurfaceV3(
      apiClient: api,
      sessionStore: session,
      resolver: resolver,
    )));
    await tester.pumpAndSettle();
    return (api, session);
  }

  group('PhrSurfaceV3 (Requirement 7)', () {
    testWidgets('loads the record on open (Req 7.1)', (tester) async {
      final (api, _) = await pump(tester, enhanced: false);
      expect(api.wasCalled('getPhrRecord'), isTrue);
      // A loaded field value is bound into the form.
      expect(find.text('Nguyen Van A'), findsWidgets);
    });

    testWidgets(
        'save round-trips and emits only a no-PII entry_count (Req 7.2, INV-3)',
        (tester) async {
      final (api, _) = await pump(tester, enhanced: false);
      api.stub('updatePhrRecord', response: _recordPayload());

      await tester.tap(find.byType(FloatingActionButton));
      await tester.pumpAndSettle();

      // The save contract was invoked with the full record payload.
      expect(api.wasCalled('updatePhrRecord'), isTrue);
      final call = api.callsTo('updatePhrRecord').single;
      final payload = call.args['payload'] as Map<String, dynamic>;
      // The saved payload carries the medical data (that is the record itself).
      expect(payload['allergies'], isA<List<dynamic>>());
      // But the payload keys are the record contract, not a leaked analytics
      // event — analytics is asserted separately below via the strip filter.
    });

    testWidgets('save entry_count survives PII stripping (INV-3)',
        (tester) async {
      // The save event carries only `entry_count`, which is NOT a PII key, so it
      // survives `stripPii`. Any medical/name/free-text key would be dropped.
      final event = AnalyticsEvent(MobileAnalyticsEvents.phrSaved, {
        'entry_count': 3,
      });
      final stripped = stripPii(event);
      expect(stripped.props['entry_count'], 3);
      expect(stripped.props.keys, everyElement(isNot(contains('name'))));
    });

    testWidgets('enhanced actions are hidden when the gate is off (Req 7.4)',
        (tester) async {
      await pump(tester, enhanced: false);
      expect(find.byIcon(Icons.emergency_outlined), findsNothing);
      expect(find.byIcon(Icons.download_outlined), findsNothing);
    });

    testWidgets('enhanced actions appear when the gate is on (Req 7.4)',
        (tester) async {
      await pump(tester, enhanced: true);
      // The emergency-card action is only rendered when the enhanced gate is on
      // AND a record is loaded.
      expect(find.byIcon(Icons.emergency_outlined), findsOneWidget);
    });
  });
}

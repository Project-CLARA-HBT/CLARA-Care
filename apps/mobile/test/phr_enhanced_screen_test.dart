// Feature: clara-mobile-feature-parity — Task 7.2 (Req 5.6).
//
// Widget tests for the flag-gated enhanced PHR reads (export + emergency card).
// The invariant under test: the enhanced read-only affordances appear ONLY when
// `phr_enhanced_mobile_enabled` resolves true; with the flag off (or absent) the
// PHR screen behaves exactly as the legacy surface — no export/emergency-card
// affordances are rendered (Req 5.6).
//
// Both surfaces are read-only client-side projections of the already-loaded
// record (no extra API call), so the test drives the screen with the same
// task-1.1 fakes and asserts no additional network methods are invoked.

import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/screens/phr_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fakes.dart';

void main() {
  // A legacy `/record` GET payload with a current + non-current medication, an
  // allergy, a condition, blood type, and an emergency contact so every
  // emergency-card field is exercised.
  Map<String, dynamic> recordPayload() => {
        'full_name': 'Nguyen Van A',
        'blood_type': 'O+',
        'emergency_contact_name': 'Tran Thi B',
        'emergency_contact_phone': '0900000000',
        'allergies': [
          {
            'id': 'a1',
            'name': 'Penicillin',
            'reaction': 'Phát ban',
            'severity': 'severe',
            'note': '',
          },
        ],
        'conditions': [
          {
            'id': 'c1',
            'name': 'Tăng huyết áp',
            'status': 'active',
            'note': '',
          },
        ],
        'medications': [
          {
            'id': 'm1',
            'name': 'Amlodipine',
            'dose': '5mg',
            'frequency': 'daily',
            'is_current': true,
            'note': '',
          },
          {
            'id': 'm2',
            'name': 'Ibuprofen',
            'dose': '200mg',
            'frequency': 'as needed',
            'is_current': false,
            'note': '',
          },
        ],
      };

  /// Builds a resolver whose server summary sets `phr_enhanced_mobile_enabled`.
  MobileFeatureFlagResolver resolver({required bool enhanced}) {
    return MobileFeatureFlagResolver(summary: {
      'feature_flags': {
        MobileFeatureFlags.phrEnhancedMobileEnabled: enhanced,
      },
    });
  }

  Future<void> pumpScreen(
    WidgetTester tester, {
    required FakeApiClient api,
    MobileFeatureFlagResolver? flags,
  }) async {
    final session = await FakeSessionStore.authenticated();
    await tester.pumpWidget(MaterialApp(
      home: PhrScreen(
        apiClient: api,
        sessionStore: session,
        featureFlags: flags,
      ),
    ));
    await tester.pumpAndSettle();
  }

  testWidgets(
    'flag OFF: no export / emergency-card affordances are rendered '
    '(legacy behavior preserved) (Req 5.6)',
    (tester) async {
      final api = FakeApiClient()
        ..stub('getPhrRecord', response: recordPayload());

      await pumpScreen(tester, api: api, flags: resolver(enhanced: false));

      expect(find.byKey(const Key('phr-enhanced-actions')), findsNothing);
      expect(find.byKey(const Key('phr-export-action')), findsNothing);
      expect(find.byKey(const Key('phr-emergency-card-action')), findsNothing);

      // The legacy surface still loaded normally.
      await tester.dragUntilVisible(
        find.text('Penicillin'),
        find.byType(ListView).first,
        const Offset(0, -240),
      );
      expect(find.text('Penicillin'), findsOneWidget);
    },
  );

  testWidgets(
    'no featureFlags injected resolves the gate closed (default-off) (Req 5.6)',
    (tester) async {
      final api = FakeApiClient()
        ..stub('getPhrRecord', response: recordPayload());

      await pumpScreen(tester, api: api); // no flags

      expect(find.byKey(const Key('phr-export-action')), findsNothing);
      expect(find.byKey(const Key('phr-emergency-card-action')), findsNothing);
    },
  );

  testWidgets(
    'flag ON: export + emergency-card affordances appear (Req 5.6)',
    (tester) async {
      final api = FakeApiClient()
        ..stub('getPhrRecord', response: recordPayload());

      await pumpScreen(tester, api: api, flags: resolver(enhanced: true));

      expect(find.byKey(const Key('phr-enhanced-actions')), findsOneWidget);
      expect(find.byKey(const Key('phr-export-action')), findsOneWidget);
      expect(
          find.byKey(const Key('phr-emergency-card-action')), findsOneWidget);
    },
  );

  testWidgets(
    'flag ON: export view renders a read-only JSON projection of the record '
    '(no extra API call) (Req 5.6)',
    (tester) async {
      final api = FakeApiClient()
        ..stub('getPhrRecord', response: recordPayload());

      await pumpScreen(tester, api: api, flags: resolver(enhanced: true));

      await tester.tap(find.byKey(const Key('phr-export-action')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('phr-export-view')), findsOneWidget);
      // The serialized record is shown read-only and selectable.
      final json = tester
          .widget<SelectableText>(find.byKey(const Key('phr-export-json')));
      expect(json.data, contains('Nguyen Van A'));
      expect(json.data, contains('Amlodipine'));

      // Only the original GET was made — the export is a client-side projection.
      expect(api.callsTo('getPhrRecord').length, 1);
      expect(api.wasCalled('updatePhrRecord'), isFalse);
    },
  );

  testWidgets(
    'flag ON: emergency-card view shows allergies, current meds only, '
    'conditions, blood type, and contact (Req 5.6)',
    (tester) async {
      final api = FakeApiClient()
        ..stub('getPhrRecord', response: recordPayload());

      await pumpScreen(tester, api: api, flags: resolver(enhanced: true));

      await tester.tap(find.byKey(const Key('phr-emergency-card-action')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('phr-emergency-card-view')), findsOneWidget);

      // Blood type + contact.
      expect(find.text('O+'), findsOneWidget);
      expect(find.text('Tran Thi B'), findsOneWidget);
      expect(find.text('0900000000'), findsOneWidget);

      // Current medication is included; the non-current one is excluded.
      expect(find.textContaining('Amlodipine'), findsOneWidget);
      expect(find.textContaining('Ibuprofen'), findsNothing);

      // Allergy + condition lines.
      expect(find.textContaining('Penicillin'), findsOneWidget);
      expect(find.textContaining('Tăng huyết áp'), findsOneWidget);

      // The persistent self-declared disclaimer remains present.
      expect(find.byKey(const Key('phr-disclaimer')), findsOneWidget);
    },
  );

  test('PhrEmergencyCardProjection includes only current medications (Req 5.6)',
      () {
    final record = PhrRecordModel.fromJson(recordPayload());
    final card = PhrEmergencyCardProjection.fromRecord(record);

    expect(card.bloodType, 'O+');
    expect(card.emergencyContactName, 'Tran Thi B');
    expect(card.allergies.map((a) => a.name), ['Penicillin']);
    expect(card.conditions.map((c) => c.name), ['Tăng huyết áp']);
    // Only the current medication survives the projection.
    expect(card.currentMedications.map((m) => m.name), ['Amlodipine']);
    expect(card.isEmpty, isFalse);
  });
}

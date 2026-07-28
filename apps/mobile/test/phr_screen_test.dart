// Feature: clara-mobile-feature-parity — Task 7.1 (Req 5.1, 5.2, 5.3).
//
// Widget tests for the legacy PHR surface, asserting the load-bearing parity
// invariants that task 7.1 reaffirms (verify-and-harden):
//   * Legacy GET/PUT contract preserved (Req 5.1): the screen reads via
//     `getPhrRecord` and writes via `updatePhrRecord` with the legacy
//     `/record` payload shape — no contract change.
//   * Provenance + verification badges (Req 5.2): each entry renders its
//     `information_source` / `verification_status` badge, defaulting to
//     self-declared / unconfirmed when the legacy endpoint omits them.
//   * Persistent self-declared disclaimer (Req 5.3): the disclaimer banner is
//     present on every PHR surface (loading, success, and error), and status
//     is conveyed by text — not color alone.
//
// The screen is driven through the reusable task-1.1 fakes (`FakeApiClient`,
// `FakeSessionStore`) so the test runs under `flutter test` with no live
// network or platform channels (Req 14.6).

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/screens/phr_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fakes.dart';

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  // A legacy `/record` GET payload. The allergy carries explicit provenance,
  // while the condition omits provenance entirely so the screen's
  // self-declared / unconfirmed defaults are exercised (Req 5.2).
  Map<String, dynamic> recordPayload() => {
        'full_name': 'Nguyen Van A',
        'allergies': [
          {
            'id': 'a1',
            'name': 'Penicillin',
            'reaction': 'Phát ban',
            'severity': 'severe',
            'note': '',
            'information_source': 'imported',
            'verification_status': 'confirmed',
          },
        ],
        'conditions': [
          {
            'id': 'c1',
            'name': 'Tăng huyết áp',
            'status': 'active',
            'note': '',
            // No information_source / verification_status -> defaults apply.
          },
        ],
        'medications': <dynamic>[],
      };

  Future<void> pumpScreen(
    WidgetTester tester, {
    required FakeApiClient api,
  }) async {
    final session = await FakeSessionStore.authenticated();
    await tester.pumpWidget(MaterialApp(
      home: PhrScreen(apiClient: api, sessionStore: session),
    ));
  }

  testWidgets(
    'renders provenance/verification badges and the persistent self-declared '
    'disclaimer, reading via the legacy GET contract (Req 5.1, 5.2, 5.3)',
    (tester) async {
      final api = FakeApiClient()
        ..stub('getPhrRecord', response: recordPayload());

      await pumpScreen(tester, api: api);

      // Loading surface still carries the persistent disclaimer (Req 5.3).
      await tester.pump();
      expect(find.byKey(const Key('phr-disclaimer')), findsOneWidget);

      await tester.pumpAndSettle();

      // Legacy GET preserved (Req 5.1).
      expect(api.wasCalled('getPhrRecord'), isTrue);

      // Disclaimer persists on the loaded surface (Req 5.3).
      expect(find.byKey(const Key('phr-disclaimer')), findsOneWidget);

      // Entries render.
      await tester.dragUntilVisible(
        find.text('Penicillin'),
        find.byType(ListView).first,
        const Offset(0, -240),
      );
      expect(find.text('Penicillin'), findsOneWidget);
      expect(find.text('Nhập khẩu'), findsOneWidget); // imported source
      expect(find.text('Đã xác minh'), findsOneWidget); // confirmed

      await tester.dragUntilVisible(
        find.text('Tăng huyết áp'),
        find.byType(ListView).first,
        const Offset(0, -240),
      );
      expect(find.text('Tăng huyết áp'), findsOneWidget);

      // Provenance + verification badges convey status by TEXT (Req 5.2, not
      // color alone). The imported/confirmed allergy and the default
      // self-declared/unconfirmed condition are both labelled.
      expect(find.text('Tự khai'), findsOneWidget); // default self-declared
      expect(find.text('Chưa xác minh'), findsOneWidget); // default unconfirmed
    },
  );

  testWidgets(
    'save round-trips through the legacy PUT contract without contract change '
    '(Req 5.1)',
    (tester) async {
      final api = FakeApiClient()
        ..stub('getPhrRecord', response: recordPayload())
        ..stub('updatePhrRecord', response: recordPayload());

      await pumpScreen(tester, api: api);
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(FloatingActionButton, 'Lưu'));
      await tester.pumpAndSettle();

      // Legacy PUT preserved with the legacy `/record` payload shape (Req 5.1).
      expect(api.wasCalled('updatePhrRecord'), isTrue);
      final payload =
          api.callsTo('updatePhrRecord').single.args['payload'] as Map;
      expect(payload.containsKey('allergies'), isTrue);
      expect(payload.containsKey('conditions'), isTrue);
      expect(payload.containsKey('medications'), isTrue);
      expect(payload.containsKey('full_name'), isTrue);
    },
  );

  testWidgets(
    'error surface keeps the persistent self-declared disclaimer and offers '
    'retry (Req 5.3)',
    (tester) async {
      final api = FakeApiClient()
        ..stub('getPhrRecord',
            error:
                ApiException(message: 'Không thể tải hồ sơ.', statusCode: 500));

      await pumpScreen(tester, api: api);
      await tester.pumpAndSettle();

      // Disclaimer present even on the error surface (Req 5.3).
      expect(find.byKey(const Key('phr-disclaimer')), findsOneWidget);
      // Retry affordance is shown (status conveyed by text).
      expect(find.text('Thử lại'), findsOneWidget);
    },
  );
}

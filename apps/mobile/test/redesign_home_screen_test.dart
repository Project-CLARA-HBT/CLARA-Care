// Widget tests for the redesigned Home surface (Experience_V3).
//
// clara-mobile-redesign, Task 3.3 + Requirement 3 / INV-4 (fail-closed RBAC):
//   * A null role-scoped summary derives NO privileged tool cards, but the
//     always-available PHR card is still present, and a retry is offered.
//   * A loaded summary derives the tool cards its `feature_flags` grant.
//   * The "recent activity" region shows a friendly empty state (no fabricated
//     data).
//
// The surface is given the already-loaded summary + resolver by the redesign
// root, so these tests construct it directly (no network). A `FakeApiClient`
// is supplied only so a pull-to-refresh has something to call.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/experience/redesign/home_screen_v3.dart';

import 'fakes/fakes.dart';

Widget _host(Widget child) => MaterialApp(home: child);

Future<HomeScreenV3> _home({
  required Map<String, dynamic>? summary,
  String role = 'normal',
}) async {
  final session = await FakeSessionStore.authenticated(role: role);
  return HomeScreenV3(
    apiClient: FakeApiClient(),
    sessionStore: session,
    resolver: MobileFeatureFlagResolver(summary: summary),
    summary: summary,
  );
}

void main() {
  group('HomeScreenV3 — fail-closed tool derivation (Req 3.2, INV-4)', () {
    testWidgets('null summary shows no privileged cards but keeps PHR + retry',
        (tester) async {
      await tester.pumpWidget(_host(await _home(summary: null)));
      await tester.pumpAndSettle();

      // PHR is always available regardless of the summary.
      expect(find.text('Hồ sơ sức khỏe'), findsOneWidget);

      // No privileged tools are derived when the summary is unavailable.
      expect(find.text('Trò chuyện'), findsNothing);
      expect(find.text('Hội chẩn AI'), findsNothing);
      expect(find.text('Ghi chú lâm sàng'), findsNothing);

      // A fail-closed retry affordance is offered in place of the tools.
      expect(find.text('Thử lại'), findsOneWidget);
    });

    testWidgets('a loaded summary derives the granted tool cards',
        (tester) async {
      final summary = <String, dynamic>{
        'feature_flags': <String, dynamic>{
          'chat_mobile_enabled': true,
          'careguard': true,
        },
      };
      await tester.pumpWidget(_host(await _home(summary: summary)));
      await tester.pumpAndSettle();

      expect(find.text('Trò chuyện'), findsOneWidget);
      expect(find.text('Kiểm tra tương tác thuốc'), findsOneWidget);
      expect(find.text('Hồ sơ sức khỏe'), findsOneWidget);
      // A gate that was not granted stays hidden.
      expect(find.text('Hội chẩn AI'), findsNothing);
      // No retry when a summary loaded successfully.
      expect(find.text('Thử lại'), findsNothing);
    });

    testWidgets('Scribe card requires an authorized role even when flag is on',
        (tester) async {
      final summary = <String, dynamic>{
        'feature_flags': <String, dynamic>{'scribe_mobile_enabled': true},
      };

      // normal role: Scribe stays hidden despite the flag (fail-closed RBAC).
      await tester
          .pumpWidget(_host(await _home(summary: summary, role: 'normal')));
      await tester.pumpAndSettle();
      expect(find.text('Ghi chú lâm sàng'), findsNothing);

      // admin role: the redesign opens Scribe to admin.
      await tester
          .pumpWidget(_host(await _home(summary: summary, role: 'admin')));
      await tester.pumpAndSettle();
      expect(find.text('Ghi chú lâm sàng'), findsOneWidget);
    });

    testWidgets('recent-activity region shows a friendly empty state',
        (tester) async {
      await tester.pumpWidget(_host(await _home(summary: <String, dynamic>{
        'feature_flags': <String, dynamic>{},
      })));
      await tester.pumpAndSettle();

      // The richer Home (primary CTA + daily tip) makes the list taller than the
      // test viewport, and the list lazily builds its children, so scroll the
      // recent-activity region into view before asserting it rendered.
      await tester.scrollUntilVisible(
        find.text('Chưa có hoạt động gần đây'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Chưa có hoạt động gần đây'), findsOneWidget);
    });
  });
}

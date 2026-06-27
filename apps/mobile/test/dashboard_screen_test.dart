// Feature: clara-mobile-feature-parity — Task 13.1 (Req 13.2, 13.4, 13.5).
//
// Focused widget tests for the role-aware dashboard's fail-closed behavior.
// They pin the load-bearing invariants of task 13.1:
//   * Summary-load failure ⇒ NO privileged/feature tiles are shown and a retry
//     affordance is presented; retry re-fetches the summary (Req 13.4).
//   * Always-available tiles (PHR) keep working regardless of the summary
//     (Req 13.3) — additive hardening preserves existing reachability.
//   * Admin-only surfaces (system monitor) are NEVER shown to non-admin roles,
//     and their existence is not even disclosed (Req 13.5).
//
// The reusable fakes (task 1.1) back a real screen so the test runs without a
// live server or platform channels (Requirement 14.6).

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/screens/dashboard_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fakes.dart';

Future<void> _pumpDashboard(
  WidgetTester tester, {
  required FakeApiClient api,
  required String role,
}) async {
  final session = await FakeSessionStore.authenticated(role: role);
  await tester.pumpWidget(
    MaterialApp(
      home: DashboardScreen(apiClient: api, sessionStore: session),
    ),
  );
  // Let initState's _loadSummary future settle.
  await tester.pumpAndSettle();
}

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  testWidgets(
      'summary-load failure shows no privileged tiles and offers a retry',
      (tester) async {
    final api = FakeApiClient();
    api.stub(
      'getMobileSummary',
      error: ApiException(message: 'Máy chủ không phản hồi', statusCode: 503),
    );

    await _pumpDashboard(tester, api: api, role: 'normal');

    // Fail closed: none of the privileged/feature tiles are rendered.
    expect(find.text('Nghiên cứu y khoa'), findsNothing);
    expect(find.text('Kiểm tra tương tác thuốc'), findsNothing);
    expect(find.text('Hội chẩn AI'), findsNothing);

    // Always-available tile keeps working (Req 13.3).
    expect(find.text('Hồ sơ sức khỏe'), findsOneWidget);

    // A retry affordance is presented (Req 13.4).
    final retry = find.widgetWithText(FilledButton, 'Thử lại');
    expect(retry, findsOneWidget);

    // The admin-only surface is never disclosed to a non-admin role (Req 13.5).
    expect(find.text('Chỉ số hệ thống'), findsNothing);
    expect(find.text('Làm mới'), findsNothing);

    // Retry re-fetches the summary; on success tiles appear (Req 13.4).
    api.stub('getMobileSummary', response: const {
      'feature_flags': {'research': true, 'careguard': true, 'council': false},
    });
    await tester.tap(retry);
    await tester.pumpAndSettle();

    expect(find.text('Nghiên cứu y khoa'), findsOneWidget);
    expect(find.text('Kiểm tra tương tác thuốc'), findsOneWidget);
    expect(find.text('Hội chẩn AI'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Thử lại'), findsNothing);
  });

  testWidgets(
      'system monitor is hidden from non-admin even if the flag is set',
      (tester) async {
    // Defense-in-depth: a mis-scoped server flag must still not leak the
    // admin-only surface to a non-admin role (Req 13.5).
    final api = FakeApiClient();
    api.stub('getMobileSummary', response: const {
      'feature_flags': {'system_monitor': true, 'research': true},
    });

    await _pumpDashboard(tester, api: api, role: 'normal');

    expect(find.text('Chỉ số hệ thống'), findsNothing);
    expect(api.wasCalled('getSystemMetrics'), isFalse);
    // The role-scoped tile still renders.
    expect(find.text('Nghiên cứu y khoa'), findsOneWidget);
  });

  testWidgets('admin with system_monitor flag sees the metrics surface',
      (tester) async {
    final api = FakeApiClient();
    api.stub('getMobileSummary', response: const {
      'feature_flags': {'system_monitor': true},
    });
    api.stub('getSystemMetrics', response: const {
      'requests_total': 42,
      'avg_latency_ms': 12,
    });

    await _pumpDashboard(tester, api: api, role: 'admin');

    expect(find.text('Chỉ số hệ thống'), findsOneWidget);
    expect(api.wasCalled('getSystemMetrics'), isTrue);
    expect(find.text('Tổng số request: 42'), findsOneWidget);
  });
}

// Feature: clara-mobile-feature-parity — Task 4.2 / 4.3 (Req 2.3, 2.4).
//
// Widget-level assertion of Property P2 (role-gated telemetry soundness) for the
// deep-research surface. The screen reuses the pure, fail-closed
// `evaluateTelemetryGate` helper, so this test pins the *rendered* consequences
// of that gate rather than re-testing the helper (covered by
// `research_telemetry_gate_test.dart`):
//
//   * admin            -> the detailed telemetry rail is shown verbatim
//                         (internal labels + per-stage detail visible);
//   * recognized non-admin -> only the sanitized summary is shown (internal
//                         labels stripped, per-stage detail hidden);
//   * unevaluable role -> fail closed: no telemetry rail, the research job is
//                         blocked, and the API is never called.
//
// Uses the shared `test/fakes/` harness (task 1.1) so the test runs under
// `flutter test` with no platform channels or live network (Requirement 14.6).

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/screens/research_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fakes.dart';

void main() {
  // A research-job payload whose progress carries internal telemetry labels in
  // the status note and a stage label, plus an admin-only per-stage detail. The
  // gate decides which of these survive into the rendered view.
  const adminOnlyDetail = 'ADMIN_ONLY_STAGE_DETAIL_42';
  final completedJobSnapshot = <String, dynamic>{
    'status': 'completed',
    'progress': {
      'status_note': 'Đang tổng hợp retrieval kết quả',
      'active_stage': 'synthesis',
      'flow_stages': [
        {
          'id': 'analysis',
          'label': 'Phân tích RAG mode',
          'status': 'completed',
          'detail': adminOnlyDetail,
        },
      ],
    },
    'result': {'answer': 'Câu trả lời mẫu cho người dùng.'},
  };

  FakeApiClient buildApi() {
    final api = FakeApiClient();
    api.stub('createResearchJob', response: {'job_id': 'job-1'});
    api.stubStream(events: [
      SseEvent(event: 'progress', data: jsonEncode(completedJobSnapshot)),
    ]);
    return api;
  }

  Future<void> pumpResearch(
    WidgetTester tester, {
    required FakeApiClient api,
    required String role,
  }) async {
    final session = await FakeSessionStore.authenticated(role: role);
    await tester.pumpWidget(MaterialApp(
      home: ResearchScreen(
        apiClient: api,
        sessionStore: session,
        deepResearchEnabled: true,
      ),
    ));
    await tester.pumpAndSettle();
  }

  Future<void> runDeepResearch(WidgetTester tester) async {
    await tester.enterText(find.byType(TextField), 'Tương tác thuốc?');
    // Switch to a deep mode so the job-stream/progress rail is exercised.
    await tester.tap(find.text('Tư duy'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Tìm hiểu'));
    await tester.pumpAndSettle();
  }

  testWidgets(
      'non-admin role sees the sanitized summary only (labels stripped, no detail)',
      (tester) async {
    final api = buildApi();
    await pumpResearch(tester, api: api, role: 'doctor');
    await runDeepResearch(tester);

    // The progress rail renders (sanitized summary is shown to recognized roles).
    expect(find.byKey(const Key('research-progress')), findsOneWidget);

    // Internal telemetry labels are stripped from the summary (R2.3).
    expect(find.textContaining('retrieval'), findsNothing);
    expect(find.textContaining('RAG mode'), findsNothing);
    // The admin-only per-stage detail is not exposed to non-admin roles.
    expect(find.textContaining(adminOnlyDetail), findsNothing);

    // The user-facing copy survives sanitization.
    expect(find.textContaining('Đang tổng hợp'), findsOneWidget);
    expect(find.textContaining('Phân tích'), findsOneWidget);
  });

  testWidgets('admin role sees the detailed telemetry rail verbatim',
      (tester) async {
    final api = buildApi();
    await pumpResearch(tester, api: api, role: 'admin');
    await runDeepResearch(tester);

    expect(find.byKey(const Key('research-progress')), findsOneWidget);

    // Detailed rail: internal labels and per-stage detail are shown verbatim
    // (R2.3 — detailed rail iff admin).
    expect(find.textContaining('retrieval'), findsOneWidget);
    expect(find.textContaining('RAG mode'), findsOneWidget);
    expect(find.textContaining(adminOnlyDetail), findsOneWidget);
  });

  testWidgets('unevaluable role fails closed: job blocked, API never called',
      (tester) async {
    final api = buildApi();
    await pumpResearch(tester, api: api, role: 'ghost-role-not-recognized');
    await runDeepResearch(tester);

    // No telemetry rail is rendered (fail closed — R2.4).
    expect(find.byKey(const Key('research-progress')), findsNothing);

    // The research job is blocked with a clear, PII-free message.
    expect(
      find.textContaining('Phiên nghiên cứu đã bị chặn'),
      findsOneWidget,
    );

    // Fail-closed means the privileged job is never dispatched to the API.
    expect(api.wasCalled('createResearchJob'), isFalse);
    expect(api.wasCalled('researchTier2'), isFalse);
    expect(api.wasCalled('streamResearchJob'), isFalse);
  });
}

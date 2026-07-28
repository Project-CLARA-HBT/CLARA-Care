// Feature: clara-council-upgrade — Task 8.3 (Req 8.2, 8.3, 8.4, 8.5, 8.6).
//
// Widget/integration test for the mobile Council parity flow added in task 8.2
// (`CouncilCaseScreen`, 3-phase intake -> specialists -> result). It drives the
// full wizard against a real [ApiClient] backed by a `MockClient`
// (package:http/testing) and an in-memory [PersistentSessionStore], so the
// screen exercises genuine request/response plumbing without a live server or
// platform channels.
//
// Load-bearing invariants asserted:
//   * The flow reuses the shared Council_API case endpoints (create -> intake ->
//     run) — no mobile-only result shape (Req 8.2).
//   * The result screen renders consensus / divergence / final recommendation
//     from a sample `run_council` envelope (Req 8.3).
//   * The "review with a licensed clinician" directive
//     (`kCouncilClinicianDirective`) is ALWAYS present on the result screen,
//     both when specialists diverge and when they reach consensus (Req 8.3).

import 'dart:convert';

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/screens/council_case_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

class InMemorySessionSecureStorage implements SessionSecureStorage {
  final Map<String, String> _data = {};

  @override
  Future<String?> read(String key) async => _data[key];

  @override
  Future<void> write(String key, String value) async => _data[key] = value;

  @override
  Future<void> delete(String key) async => _data.remove(key);
}

void main() {
  const base = 'https://api.test';

  // A sample `run_council` result envelope, returned under the case `result`
  // key by POST /council/cases/{id}/run — the same shape the web consumes.
  Map<String, dynamic> divergentRunResult() => {
        'consensus_summary':
            'Cả ba chuyên khoa đồng ý cần loại trừ hội chứng vành cấp.',
        'final_recommendation':
            'Khuyến nghị nhập viện theo dõi và đo troponin chuỗi.',
        'divergence_notes': [
          'Tim mạch ưu tiên chụp mạch vành sớm; Thần kinh đề nghị loại trừ '
              'đột quỵ trước.',
        ],
        'conflict_list': [
          {'note': 'Khác biệt về thứ tự ưu tiên chẩn đoán hình ảnh.'},
        ],
        'requested_specialists': ['cardiology', 'neurology', 'endocrinology'],
      };

  Map<String, dynamic> consensusRunResult() => {
        'consensus_summary':
            'Các chuyên khoa thống nhất chẩn đoán viêm dạ dày và điều trị nội khoa.',
        'final_recommendation':
            'Khuyến nghị dùng thuốc ức chế bơm proton và tái khám sau 2 tuần.',
        'divergence_notes': <String>[],
        'conflict_list': <dynamic>[],
        'requested_specialists': ['gastroenterology', 'internal_medicine'],
      };

  Future<PersistentSessionStore> buildSession() async {
    final store =
        PersistentSessionStore(storage: InMemorySessionSecureStorage());
    await store.setSession(
      email: 'doctor@example.com',
      accessToken: 'test-token',
      refreshToken: 'refresh',
      role: 'doctor',
    );
    return store;
  }

  /// Builds a MockClient that walks the case lifecycle: create -> intake -> run.
  /// The run endpoint returns the supplied `run_council` [runResult] under the
  /// case `result` key.
  MockClient buildMock(Map<String, dynamic> runResult, {int caseId = 42}) {
    return MockClient((request) async {
      final path = request.url.path;
      final method = request.method;

      if (path == '/api/v1/council/cases' && method == 'POST') {
        return http.Response(
          jsonEncode(
              {'id': caseId, 'title': 'Ca hội chẩn mới', 'status': 'draft'}),
          200,
          headers: {'content-type': 'application/json'},
        );
      }
      if (path == '/api/v1/council/cases/$caseId/intake' && method == 'POST') {
        return http.Response(
          jsonEncode({
            'id': caseId,
            'intake': {
              'symptoms': ['đau ngực'],
              'ai_disclosure': {'is_fallback': false},
            },
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      }
      if (path == '/api/v1/council/cases/$caseId/run' && method == 'POST') {
        return http.Response(
          jsonEncode({'id': caseId, 'result': runResult}),
          200,
          headers: {'content-type': 'application/json'},
        );
      }
      return http.Response(
          '{"detail":"unexpected ${request.method} $path"}', 404,
          headers: {'content-type': 'application/json'});
    });
  }

  Future<void> driveFlowToResult(
    WidgetTester tester, {
    required ApiClient apiClient,
    required PersistentSessionStore session,
  }) async {
    await tester.pumpWidget(MaterialApp(
      home: CouncilCaseScreen(apiClient: apiClient, sessionStore: session),
    ));
    await tester.pumpAndSettle();

    // Phase 1 (intake): supply a transcript so the case is created AND intake
    // runs, then advance to the specialists step.
    await tester.enterText(
      find.widgetWithText(TextField, 'Lời thoại / mô tả ca (không bắt buộc)'),
      'Bệnh nhân nam 58 tuổi, đau ngực trái lan tay trái 30 phút.',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Tạo ca & trích xuất'));
    await tester.pumpAndSettle();

    // Phase 2 (specialists): the case was created; run the Council.
    expect(find.text('Chạy hội chẩn'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, 'Chạy hội chẩn'));
    await tester.pumpAndSettle();
  }

  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  testWidgets(
    'parity flow intake->specialists->result renders consensus/divergence/'
    'final + clinician directive from a run_council envelope',
    (tester) async {
      final apiClient =
          ApiClient(baseUrl: base, httpClient: buildMock(divergentRunResult()));
      final session = await buildSession();

      await driveFlowToResult(tester, apiClient: apiClient, session: session);

      // Result phase: the "tạo ca mới" reset control marks we reached phase 3.
      await tester.dragUntilVisible(
        find.text('Tạo ca hội chẩn mới'),
        find.byType(Scrollable),
        const Offset(0, -300),
      );
      expect(find.text('Tạo ca hội chẩn mới'), findsOneWidget);

      // Consensus summary (Req 8.3).
      expect(find.text('Tóm tắt đồng thuận'), findsOneWidget);
      expect(
        find.text('Cả ba chuyên khoa đồng ý cần loại trừ hội chứng vành cấp.'),
        findsOneWidget,
      );

      // Final recommendation (Req 8.3).
      expect(find.text('Khuyến nghị cuối cùng'), findsOneWidget);
      expect(
        find.text('Khuyến nghị nhập viện theo dõi và đo troponin chuỗi.'),
        findsOneWidget,
      );

      // Divergence: header + the divergence note and the conflict note are both
      // surfaced, and the divergence banner title is shown (Req 8.3).
      expect(
          find.text('Có điểm khác biệt giữa các chuyên khoa'), findsOneWidget);
      expect(find.text('Điểm cần lưu ý / bất đồng'), findsOneWidget);
      expect(
        find.textContaining('Tim mạch ưu tiên chụp mạch vành sớm'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Khác biệt về thứ tự ưu tiên chẩn đoán hình ảnh.'),
        findsOneWidget,
      );

      // Participating specialists rendered from the shared envelope.
      expect(
        find.text('cardiology, neurology, endocrinology'),
        findsOneWidget,
      );

      // The clinician directive is ALWAYS present on the result screen (Req 8.3).
      expect(find.text(kCouncilClinicianDirective), findsOneWidget);
    },
  );

  testWidgets(
    'clinician directive is present on the result screen even when the '
    'specialists reach consensus (no divergence)',
    (tester) async {
      final apiClient =
          ApiClient(baseUrl: base, httpClient: buildMock(consensusRunResult()));
      final session = await buildSession();

      await driveFlowToResult(tester, apiClient: apiClient, session: session);

      // Reached the result phase.
      expect(find.text('Tạo ca hội chẩn mới'), findsOneWidget);

      // Consensus banner (no divergence) + final recommendation render.
      expect(find.text('Các chuyên khoa đồng thuận'), findsOneWidget);
      expect(find.text('Điểm cần lưu ý / bất đồng'), findsNothing);
      expect(
        find.text(
            'Khuyến nghị dùng thuốc ức chế bơm proton và tái khám sau 2 tuần.'),
        findsOneWidget,
      );

      // Directive still present regardless of consensus/divergence state.
      expect(find.text(kCouncilClinicianDirective), findsOneWidget);
    },
  );
}

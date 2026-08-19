// Widget tests for the redesigned Home surface (Experience_V3) consuming /api/v2/home.
//
// Tests:
//   * Priority 1: Top next-action card (severity-based).
//   * Priority 2: Full-width Ask CLARA entry card with text/camera/voice affordances.
//   * Priority 3: Today's schedule (medications, visits, care tasks).
//   * Priority 4: Recent changes (real source records only; no fake activity).
//   * Priority 5: Calm caught-up state when all tasks are complete.
//   * Ordinary personal Home does not show privileged feature launcher grid.
//   * Professional drawer / menu affordance is role-scoped (doctor/admin).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/experience/redesign/home_screen_v3.dart';

import 'fakes/fakes.dart';

Widget _host(Widget child) => MaterialApp(home: child);

Future<HomeScreenV3> _home({
  required Map<String, dynamic>? summary,
  FakeApiClient? client,
  String role = 'normal',
}) async {
  final session = await FakeSessionStore.authenticated(role: role);
  final apiClient = client ?? FakeApiClient();
  if (summary != null) {
    apiClient.stub('getHomeV2', response: summary);
  }
  return HomeScreenV3(
    apiClient: apiClient,
    sessionStore: session,
    resolver: MobileFeatureFlagResolver(summary: summary),
    summary: summary,
  );
}

void main() {
  group('HomeScreenV3 — /api/v2/home consumer read model', () {
    testWidgets('null summary / network failure shows error with retry affordance',
        (tester) async {
      final api = FakeApiClient()
        ..stub('getHomeV2', error: Exception('Network failure'));
      await tester.pumpWidget(_host(await _home(summary: null, client: api)));
      await tester.pumpAndSettle();

      expect(find.text('Thử lại'), findsOneWidget);
    });

    testWidgets('Priority 1: Top next-action card renders with severity and action',
        (tester) async {
      final payload = <String, dynamic>{
        'top_action': <String, dynamic>{
          'id': 'med-1',
          'kind': 'medication',
          'title': 'Uống thuốc huyết áp Amlodipine 5mg',
          'description': 'Đã đến giờ uống thuốc buổi sáng theo đơn của bác sĩ.',
          'severity': 'urgent',
          'action_label': 'Xác nhận uống thuốc',
        },
        'schedule': <Map<String, dynamic>>[],
        'recent_changes': <Map<String, dynamic>>[],
      };

      await tester.pumpWidget(_host(await _home(summary: payload)));
      await tester.pumpAndSettle();

      expect(find.text('Việc nên làm tiếp theo'), findsOneWidget);
      expect(find.text('Uống thuốc huyết áp Amlodipine 5mg'), findsOneWidget);
      expect(find.text('Khẩn cấp'), findsOneWidget);
      expect(find.text('Xác nhận uống thuốc'), findsOneWidget);
    });

    testWidgets(
        'Priority 2: Full-width Ask CLARA entry card with text/camera/voice affordances',
        (tester) async {
      final payload = <String, dynamic>{
        'schedule': <Map<String, dynamic>>[],
        'recent_changes': <Map<String, dynamic>>[],
      };

      await tester.pumpWidget(_host(await _home(summary: payload)));
      await tester.pumpAndSettle();

      expect(find.text('Hỏi CLARA'), findsOneWidget);
      expect(
        find.text('Hỏi CLARA về sức khỏe, triệu chứng, đơn thuốc...'),
        findsOneWidget,
      );
      expect(find.text('Gửi câu hỏi'), findsOneWidget);
      expect(find.text('Chụp ảnh nhãn thuốc hoặc kết quả'), findsOneWidget);
      expect(find.text('Nói câu hỏi'), findsOneWidget);
    });

    testWidgets(
        'Priority 3: Today schedule renders medications, visits, and care tasks',
        (tester) async {
      final payload = <String, dynamic>{
        'schedule': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 'task-1',
            'kind': 'medication',
            'title': 'Metformin 500mg',
            'subtitle': '1 viên sau ăn sáng',
            'time': '08:00',
            'status': 'pending',
          },
          <String, dynamic>{
            'id': 'task-2',
            'kind': 'visit',
            'title': 'Tái khám Tim mạch',
            'subtitle': 'Bệnh viện Đại học Y Dược',
            'time': '14:30',
            'status': 'pending',
          },
          <String, dynamic>{
            'id': 'task-3',
            'kind': 'task',
            'title': 'Đo đường huyết trước ăn',
            'status': 'pending',
          },
        ],
        'recent_changes': <Map<String, dynamic>>[],
      };

      await tester.pumpWidget(_host(await _home(summary: payload)));
      await tester.pumpAndSettle();

      expect(find.text('Lịch hôm nay'), findsOneWidget);
      expect(find.text('Metformin 500mg'), findsOneWidget);
      expect(find.text('Tái khám Tim mạch'), findsOneWidget);
      expect(find.text('Đo đường huyết trước ăn'), findsOneWidget);
    });

    testWidgets('Priority 4: Recent changes renders real source records only',
        (tester) async {
      final payload = <String, dynamic>{
        'schedule': <Map<String, dynamic>>[],
        'recent_changes': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 'rec-1',
            'title': 'Cập nhật liều Amlodipine 5mg',
            'summary': 'Đã điều chỉnh từ 2.5mg lên 5mg theo đơn mới',
            'source': 'Bản ghi đơn thuốc BV Chợ Rẫy',
          },
        ],
      };

      await tester.pumpWidget(_host(await _home(summary: payload)));
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Thay đổi gần đây'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Thay đổi gần đây'), findsOneWidget);
      expect(find.text('Từ nguồn dữ liệu thực tế'), findsOneWidget);
      expect(find.text('Cập nhật liều Amlodipine 5mg'), findsOneWidget);
      expect(find.text('Bản ghi đơn thuốc BV Chợ Rẫy'), findsOneWidget);
    });

    testWidgets('Priority 5: Calm caught-up state when all tasks are complete',
        (tester) async {
      final payload = <String, dynamic>{
        'schedule': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 'task-1',
            'kind': 'task',
            'title': 'Đo huyết áp sáng',
            'status': 'completed',
            'completed': true,
          },
          <String, dynamic>{
            'id': 'task-2',
            'kind': 'task',
            'title': 'Uống thuốc sáng',
            'status': 'completed',
            'completed': true,
          },
        ],
        'recent_changes': <Map<String, dynamic>>[],
      };

      await tester.pumpWidget(_host(await _home(summary: payload)));
      await tester.pumpAndSettle();

      expect(find.text('Bạn đã hoàn thành các việc hôm nay'), findsOneWidget);
      expect(
        find.text(
          'Các việc hoàn tất đã được ghi nhận. Bạn có thể nghỉ ngơi hoặc cập nhật nếu có thay đổi.',
        ),
        findsOneWidget,
      );
    });

    testWidgets(
        'Privileged feature launcher grid is removed from personal Home for ordinary user',
        (tester) async {
      final payload = <String, dynamic>{
        'feature_flags': <String, dynamic>{
          'council': true,
          'scribe_mobile_enabled': true,
        },
        'schedule': <Map<String, dynamic>>[],
        'recent_changes': <Map<String, dynamic>>[],
      };

      await tester.pumpWidget(_host(await _home(summary: payload, role: 'normal')));
      await tester.pumpAndSettle();

      // Council and Scribe feature launcher cards are NOT in ordinary personal Home grid
      expect(find.text('Hội chẩn AI'), findsNothing);
      expect(find.text('Ghi chú lâm sàng'), findsNothing);
      // And the professional tool header button is hidden for normal role
      expect(find.text('Công cụ chuyên môn →'), findsNothing);
    });

    testWidgets(
        'Professional drawer/menu affordance is available for doctor role',
        (tester) async {
      final payload = <String, dynamic>{
        'feature_flags': <String, dynamic>{
          'council': true,
          'scribe_mobile_enabled': true,
        },
        'schedule': <Map<String, dynamic>>[],
        'recent_changes': <Map<String, dynamic>>[],
      };

      await tester.pumpWidget(_host(await _home(summary: payload, role: 'doctor')));
      await tester.pumpAndSettle();

      expect(find.text('Công cụ chuyên môn →'), findsOneWidget);
    });
  });
}

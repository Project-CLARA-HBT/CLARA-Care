// Widget tests for the CLARA_Mobile Experience_V2 modern Home (task 4.3).
//
// These pin Property P4 (Home fail-closed gating) and the surrounding state
// matrix for `HomeScreen`:
//   * Loading   — while the very first `mobile/summary` is in-flight a polished
//     `ClaraSkeletonList` stands in for the tools grid (Requirement 6.1).
//   * Success   — a loaded, role-scoped summary derives the privileged
//     quick-action cards via the same gating as the legacy dashboard
//     (Requirements 4.2), and PHR is always present (4.5).
//   * Empty     — the recent-items region shows a friendly Vietnamese-first
//     `ClaraEmptyState` (Requirement 6.2 — verified alongside success).
//   * Fail-closed error — a settled summary-load failure shows `ErrorRetryView`
//     and NO privileged quick actions, while PHR stays reachable
//     (Requirements 4.3).
//   * Non-admin never sees admin surfaces — even a mis-scoped `system_monitor`
//     flag does not leak the admin-only surface to a non-admin role
//     (Requirement 4.4), and with all flags off only PHR is shown.
//
// Property P4 (Home fail-closed gating) validates Requirements 4.2, 4.3, 4.4,
// 4.5.
//
// Pure widget tests: the reusable fakes (task 1.1) back a real `HomeScreen` so
// the suite runs under `flutter test` with no platform channels or live network
// (Requirement 10.5). The shared `pumpExperience` harness renders the screen
// under `ClaraTheme.light()`.

import 'dart:async';

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/experience/home_screen.dart';
import 'package:clara_mobile/experience/states/empty_state.dart';
import 'package:clara_mobile/experience/states/skeleton.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/theme/clara_theme.dart';
import 'package:clara_mobile/widgets/error_retry_view.dart';
import 'package:flutter_test/flutter_test.dart';

import '../fakes/fakes.dart';
import '../support/experience_pump.dart';

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  /// Builds and pumps a real `HomeScreen` backed by [api] for the given [role].
  ///
  /// The fake session is authenticated with a non-empty access token (the
  /// default of `FakeSessionStore.authenticated`) so `_loadSummary` proceeds —
  /// it returns early when the token is null/empty.
  Future<PersistentSessionStore> pumpHome(
    WidgetTester tester, {
    required FakeApiClient api,
    String role = 'normal',
  }) async {
    final session = await FakeSessionStore.authenticated(role: role);
    await pumpExperience(
      tester,
      HomeScreen(apiClient: api, sessionStore: session),
      theme: ClaraTheme.light(),
    );
    return session;
  }

  group('HomeScreen loading state (Requirement 6.1)', () {
    testWidgets('shows a skeleton while the first summary is in-flight',
        (tester) async {
      // A never-completing summary keeps the screen in its initial-load state.
      final pending = Completer<Map<String, dynamic>>();
      final api = FakeApiClient();
      api.stub('getMobileSummary', responder: (_) => pending.future);

      await pumpHome(tester, api: api);
      // A single frame after initState — do NOT settle (the future never
      // completes by design).
      await tester.pump();

      expect(find.byType(ClaraSkeletonList), findsOneWidget);
      // No privileged quick actions while loading (none derived yet).
      expect(find.text('Nghiên cứu y khoa'), findsNothing);
      expect(find.byType(ErrorRetryView), findsNothing);

      // Let the pending request resolve so no work is left dangling.
      pending.complete(const <String, dynamic>{'feature_flags': {}});
      await tester.pumpAndSettle();
    });
  });

  group('HomeScreen success state (Requirements 4.2, 4.5, 6.2)', () {
    testWidgets(
        'renders role-gated quick actions, PHR, and the recent-items empty '
        'state', (tester) async {
      final api = FakeApiClient();
      api.stub('getMobileSummary', response: const {
        'feature_flags': {
          'research': true,
          'careguard': true,
          'council': false,
          'chat_mobile_enabled': true,
        },
      });

      await pumpHome(tester, api: api);
      await tester.pumpAndSettle();

      // Enabled flags surface their quick-action cards (semanticLabel = title).
      expect(find.text('Nghiên cứu y khoa'), findsOneWidget);
      expect(find.text('Kiểm tra tương tác thuốc'), findsOneWidget);
      expect(find.text('Trò chuyện'), findsOneWidget);
      // A disabled flag stays dark.
      expect(find.text('Hội chẩn AI'), findsNothing);

      // PHR is always present (Requirement 4.5).
      expect(find.text('Hồ sơ sức khỏe'), findsOneWidget);

      // The loading skeleton is gone and no error is shown.
      expect(find.byType(ClaraSkeletonList), findsNothing);
      expect(find.byType(ErrorRetryView), findsNothing);

      // The recent-items region shows the friendly empty state (Req 6.2).
      expect(find.byType(ClaraEmptyState), findsOneWidget);
      expect(find.text('Chưa có hoạt động gần đây'), findsOneWidget);
    });

    testWidgets('with all flags off only PHR is reachable (fail closed)',
        (tester) async {
      final api = FakeApiClient();
      api.stub('getMobileSummary', response: const {'feature_flags': {}});

      await pumpHome(tester, api: api, role: 'normal');
      await tester.pumpAndSettle();

      // No privileged quick actions are derived from an empty flag set.
      expect(find.text('Nghiên cứu y khoa'), findsNothing);
      expect(find.text('Kiểm tra tương tác thuốc'), findsNothing);
      expect(find.text('Hội chẩn AI'), findsNothing);
      expect(find.text('Trò chuyện'), findsNothing);
      expect(find.text('Tủ thuốc tự kê'), findsNothing);
      expect(find.text('Ghi chú lâm sàng'), findsNothing);

      // PHR remains reachable for every authenticated role (Req 4.5).
      expect(find.text('Hồ sơ sức khỏe'), findsOneWidget);
      // A successful (if empty) load is not an error.
      expect(find.byType(ErrorRetryView), findsNothing);
    });
  });

  group('HomeScreen fail-closed error state (Requirement 4.3)', () {
    testWidgets(
        'summary-load failure shows ErrorRetryView, no privileged actions, '
        'PHR still present', (tester) async {
      final api = FakeApiClient();
      api.stub(
        'getMobileSummary',
        error: ApiException(message: 'Máy chủ không phản hồi', statusCode: 503),
      );

      await pumpHome(tester, api: api, role: 'normal');
      await tester.pumpAndSettle();

      // Fail closed: no privileged quick actions are shown.
      expect(find.text('Nghiên cứu y khoa'), findsNothing);
      expect(find.text('Trò chuyện'), findsNothing);
      expect(find.text('Hội chẩn AI'), findsNothing);
      expect(find.text('Nội dung chia sẻ'), findsNothing);

      // A retry affordance is presented via the shared ErrorRetryView.
      expect(find.byType(ErrorRetryView), findsOneWidget);

      // PHR is still reachable even on a failed load (Requirement 4.5).
      expect(find.text('Hồ sơ sức khỏe'), findsOneWidget);
    });
  });

  group('HomeScreen admin-surface isolation (Requirement 4.4)', () {
    testWidgets(
        'non-admin never sees the system-monitor surface even if its flag is '
        'set', (tester) async {
      // Defense-in-depth: a mis-scoped server flag must not leak the admin-only
      // surface to a non-admin role.
      final api = FakeApiClient();
      api.stub('getMobileSummary', response: const {
        'feature_flags': {
          'system_monitor': true,
          'research': true,
        },
      });

      await pumpHome(tester, api: api, role: 'normal');
      await tester.pumpAndSettle();

      // The admin metrics surface is never derived for a non-admin role and is
      // never even disclosed; getSystemMetrics is never called.
      expect(find.text('Chỉ số hệ thống'), findsNothing);
      expect(find.textContaining('hệ thống'), findsNothing);
      expect(api.wasCalled('getSystemMetrics'), isFalse);

      // The role-scoped tile still renders, and PHR is present.
      expect(find.text('Nghiên cứu y khoa'), findsOneWidget);
      expect(find.text('Hồ sơ sức khỏe'), findsOneWidget);
    });
  });
}

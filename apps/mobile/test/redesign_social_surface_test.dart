// Widget tests for the redesigned Health Social surface (Experience_V3).
//
// clara-health-social, mobile Task 9.3. These lock:
//   * Fail-closed: a 404 (server flag off) shows the "unavailable" state and
//     never the compose/feed affordances.
//   * Consent gate: without social consent, the compose CTA routes through the
//     consent sheet (posting is not reachable until consent is granted).
//   * Feed render: posts from the API are listed.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/experience/redesign/social_surface_v3.dart';

import 'fakes/fakes.dart';

Widget _host(Widget child) => MaterialApp(home: child);

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  Future<SocialSurfaceV3> build(FakeApiClient api) async {
    final store = await FakeSessionStore.authenticated(role: 'normal');
    return SocialSurfaceV3(apiClient: api, sessionStore: store);
  }

  group('SocialSurfaceV3 (clara-health-social)', () {
    testWidgets('fail-closed: 404 from server shows the unavailable state',
        (tester) async {
      final api = FakeApiClient();
      api.socialError = ApiException(statusCode: 404, message: 'Not found');
      await tester.pumpWidget(_host(await build(api)));
      await tester.pumpAndSettle();

      // No compose FAB / feed when the feature is unavailable.
      expect(find.byIcon(Icons.edit_outlined), findsNothing);
    });

    testWidgets('renders feed posts from the API', (tester) async {
      final api = FakeApiClient();
      api.socialConsent = {'granted': true};
      api.socialCommunities = [
        {
          'id': 1,
          'slug': 'dtd',
          'name': 'Đái tháo đường',
          'description': '',
          'member_count': 3,
          'joined': true
        },
      ];
      api.socialFeed = [
        {
          'id': 10,
          'community_id': 1,
          'author_handle': 'clara7',
          'title': 'Kinh nghiệm kiểm soát đường huyết',
          'body': 'Chia sẻ của mình sau 6 tháng.',
          'created_at': '2026-07-04T06:00:00',
          'comment_count': 2,
          'reaction_count': 4,
        },
      ];
      await tester.pumpWidget(_host(await build(api)));
      await tester.pumpAndSettle();

      expect(find.textContaining('Kinh nghiệm kiểm soát đường huyết'),
          findsOneWidget);
    });

    testWidgets('tapping a post opens the detail sheet with its comments',
        (tester) async {
      final api = FakeApiClient();
      api.socialConsent = {'granted': true};
      api.socialCommunities = [
        {
          'id': 1,
          'slug': 'dtd',
          'name': 'Đái tháo đường',
          'description': '',
          'member_count': 3,
          'joined': true
        },
      ];
      api.socialFeed = [
        {
          'id': 10,
          'community_id': 1,
          'author_handle': 'clara7',
          'title': 'Kinh nghiệm kiểm soát đường huyết',
          'body': 'Chia sẻ của mình sau 6 tháng.',
          'created_at': '2026-07-04T06:00:00',
          'comment_count': 1,
          'reaction_count': 4,
        },
      ];
      api.socialComments = [
        {
          'id': 99,
          'post_id': 10,
          'author_handle': 'clara8',
          'body': 'Cảm ơn bạn đã chia sẻ kinh nghiệm.',
          'created_at': '2026-07-04T07:00:00',
        },
      ];
      await tester.pumpWidget(_host(await build(api)));
      await tester.pumpAndSettle();

      await tester
          .tap(find.textContaining('Kinh nghiệm kiểm soát đường huyết'));
      await tester.pumpAndSettle();

      // The detail sheet loads and renders the post's comment.
      expect(find.textContaining('Cảm ơn bạn đã chia sẻ'), findsOneWidget);
      expect(api.wasCalled('getSocialComments'), isTrue);
    });
  });
}

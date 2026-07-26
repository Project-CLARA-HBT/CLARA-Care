// Tests for the CLARA_Mobile unified experience (clara-mobile-unified).
//
// Covers:
//   * The `kMobileUnifiedEnabled` build flag defaults to false (fail-closed:
//     the unified root is never selected in a normal build) — Req 1.1, 9.1.
//   * `UnifiedOnboardingGate` routes on the server-backed PHR onboarding
//     status: `needs_onboarding: true` shows the onboarding flow; a completed
//     status shows the child app — Req 6.1, 6.4.
//   * A load error fails open (renders the child) so a flaky onboarding read
//     never strands the user — Req 6.1.

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/experience/unified/onboarding_flow.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fake_api_client.dart';
import 'fakes/fake_session_store.dart';

void main() {
  group('kMobileUnifiedEnabled', () {
    test('defaults to false (fail-closed) in a normal build', () {
      expect(kMobileUnifiedEnabled, isFalse);
    });
  });

  group('UnifiedOnboardingGate', () {
    late FakeApiClient api;
    late PersistentSessionStore session;

    setUp(() async {
      api = FakeApiClient();
      session = await FakeSessionStore.authenticated(role: 'normal');
    });

    Widget harness() => MaterialApp(
          home: UnifiedOnboardingGate(
            apiClient: api,
            sessionStore: session,
            child: const Scaffold(body: Text('CHILD_APP')),
          ),
        );

    testWidgets('shows the onboarding flow when needs_onboarding is true',
        (tester) async {
      api.stub('getPhrOnboarding', response: <String, dynamic>{
        'status': 'pending',
        'needs_onboarding': true,
        'record': <String, dynamic>{},
      });
      await tester.pumpWidget(harness());
      await tester.pumpAndSettle();

      expect(find.text('CHILD_APP'), findsNothing);
      expect(find.text('Chào mừng bạn đến với CLARA'), findsOneWidget);
    });

    testWidgets('shows the child app when onboarding is completed',
        (tester) async {
      api.stub('getPhrOnboarding', response: <String, dynamic>{
        'status': 'completed',
        'needs_onboarding': false,
        'record': <String, dynamic>{},
      });
      await tester.pumpWidget(harness());
      await tester.pumpAndSettle();

      expect(find.text('CHILD_APP'), findsOneWidget);
    });

    testWidgets('fails open to the child app when the onboarding read errors',
        (tester) async {
      api.stub(
        'getPhrOnboarding',
        error: ApiException(statusCode: 500, message: 'boom'),
      );
      await tester.pumpWidget(harness());
      await tester.pumpAndSettle();

      expect(find.text('CHILD_APP'), findsOneWidget);
    });
  });
}

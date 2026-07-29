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
import 'package:clara_mobile/experience/language_controller.dart';
import 'package:clara_mobile/experience/language_store.dart';
import 'package:clara_mobile/experience/unified/onboarding_flow.dart';
import 'package:clara_mobile/experience/unified/unified_root.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fake_api_client.dart';
import 'fakes/fake_session_store.dart';

class _MemoryLanguageStorage implements LanguageSecureStorage {
  final Map<String, String> _values = <String, String>{};

  @override
  Future<String?> read(String key) async => _values[key];

  @override
  Future<void> write(String key, String value) async => _values[key] = value;
}

void main() {
  group('kMobileUnifiedEnabled', () {
    test('defaults to true — the unified experience is the shipped default',
        () {
      expect(kMobileUnifiedEnabled, isTrue);
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

  group('UnifiedRoot language navigation', () {
    late FakeApiClient api;
    late PersistentSessionStore session;
    late LanguageController language;

    setUp(() async {
      api = FakeApiClient();
      session = await FakeSessionStore.authenticated(role: 'normal');
      language = LanguageController(
        store: LanguageStore(storage: _MemoryLanguageStorage()),
      );
      api.stub('getMobileSummary', response: <String, dynamic>{});
      api.stub('getPhrOnboarding', response: <String, dynamic>{
        'status': 'completed',
        'needs_onboarding': false,
        'record': <String, dynamic>{},
      });
    });

    testWidgets('rebuilds the unified task navigation after a locale change',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: UnifiedRoot(
            apiClient: api,
            sessionStore: session,
            languageController: language,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Hôm nay'), findsOneWidget);
      expect(find.text('Hành trình sức khỏe'), findsOneWidget);
      expect(find.text('Thuốc'), findsOneWidget);
      expect(find.text('Hồ sơ'), findsOneWidget);
      expect(find.text('Hỏi CLARA'), findsOneWidget);

      await language.setLanguage('en');
      await tester.pump();

      expect(find.text('Today'), findsOneWidget);
      expect(find.text('Health journey'), findsOneWidget);
      expect(find.text('Medicines'), findsOneWidget);
      expect(find.text('Profile'), findsOneWidget);
      expect(find.text('Ask CLARA'), findsOneWidget);
      expect(find.text('Hôm nay'), findsNothing);
    });
  });
}

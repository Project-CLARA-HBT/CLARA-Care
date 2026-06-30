// Smoke tests for the reusable test fakes (CLARA mobile feature-parity, task
// 1.1). These verify the fakes themselves behave so screen tests built on top
// can trust them. They use no platform channels and no live network.

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  group('FakeApiClient', () {
    test('records invocations and returns the stubbed response', () async {
      final api = FakeApiClient();
      api.stub('getMobileSummary', response: {
        'feature_flags': {'research': true},
      });

      final result = await api.getMobileSummary(accessToken: 'tok');

      expect(result['feature_flags'], {'research': true});
      expect(api.wasCalled('getMobileSummary'), isTrue);
      expect(api.lastInvocation!.accessToken, 'tok');
    });

    test('login adapts a stubbed map into LoginResponseData', () async {
      final api = FakeApiClient();
      api.stub('login', response: {
        'access_token': 'a',
        'refresh_token': 'r',
        'role': 'admin',
        'token_type': 'bearer',
      });

      final data = await api.login(email: 'e@x.com', password: 'pw');

      expect(data.accessToken, 'a');
      expect(data.role, 'admin');
      expect(api.callsTo('login').single.args['email'], 'e@x.com');
    });

    test('stubbed error is thrown', () async {
      final api = FakeApiClient();
      api.stub('getPhrRecord',
          error: ApiException(message: 'boom', statusCode: 500));

      expect(
        () => api.getPhrRecord(accessToken: 'tok'),
        throwsA(isA<ApiException>()
            .having((e) => e.statusCode, 'statusCode', 500)),
      );
    });

    test('un-stubbed method throws a descriptive StateError', () async {
      final api = FakeApiClient();
      expect(
        () => api.getCareguardCabinet(accessToken: 'tok'),
        throwsA(isA<StateError>()),
      );
    });

    test('stubStream emits SSE events in order', () async {
      final api = FakeApiClient();
      api.stubStream(events: const [
        SseEvent(event: 'progress', data: '{"stage":"start"}'),
        SseEvent(event: 'done', data: '{}'),
      ]);

      final events =
          await api.streamResearchJob(accessToken: 'tok', jobId: 'j1').toList();

      expect(events.map((e) => e.event), ['progress', 'done']);
      expect(api.wasCalled('streamResearchJob'), isTrue);
    });
  });

  group('FakeSessionStore', () {
    test('authenticated() yields a ready, role-scoped session', () async {
      final store = await FakeSessionStore.authenticated(role: 'doctor');

      expect(store.isAuthenticated, isTrue);
      expect(store.role, 'doctor');
      expect(store.accessToken, isNotEmpty);
    });

    test('empty() store is unauthenticated and clears cleanly', () async {
      final storage = InMemorySessionSecureStorage();
      final store = FakeSessionStore.empty(storage: storage);

      expect(store.isAuthenticated, isFalse);

      await store.setSession(
        email: 'e@x.com',
        accessToken: 'tok',
        refreshToken: 'r',
        role: 'normal',
      );
      expect(storage.isEmpty, isFalse);

      await store.clear();
      expect(store.isAuthenticated, isFalse);
      expect(storage.isEmpty, isTrue);
    });
  });

  group('FakeConnectivityService', () {
    test('starts online and emits only on actual change', () async {
      final conn = FakeConnectivityService(online: true);
      addTearDown(conn.dispose);

      final seen = <bool>[];
      conn.isOnline.listen(seen.add);

      conn.goOnline(); // no change -> no emit
      conn.goOffline(); // change -> emit false
      conn.goOnline(); // change -> emit true

      await Future<void>.delayed(Duration.zero);

      expect(conn.isOnlineNow, isTrue);
      expect(seen, [false, true]);
      expect(conn.emittedCount, 2);
    });
  });

  group('RecordingAnalyticsTransport', () {
    test('captures transmissions through the real Analytics facade', () {
      final transport = RecordingAnalyticsTransport();
      final analytics = Analytics(transport: transport);
      analytics.init(
        const AnalyticsConfig(provider: 'posthog', apiKey: 'phc_test'),
        consentGranted: true,
      );

      analytics.capture(const AnalyticsEvent('mobile_dashboard_viewed'));

      expect(transport.initCalls, 1);
      expect(transport.transmissions, 1);
      expect(transport.capturedNames, ['mobile_dashboard_viewed']);
    });

    test('records zero transmissions without consent', () {
      final transport = RecordingAnalyticsTransport();
      final analytics = Analytics(transport: transport);
      analytics.init(
        const AnalyticsConfig(provider: 'posthog', apiKey: 'phc_test'),
        consentGranted: false,
      );

      analytics.capture(const AnalyticsEvent('mobile_research_viewed'));

      expect(transport.transmissions, 0);
      expect(transport.initCalls, 0);
    });
  });
}

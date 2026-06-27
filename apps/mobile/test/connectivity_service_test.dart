// Unit tests for the additive networking resilience added in task 1.2:
//  * [DefaultConnectivityService] (Requirement 9.1) — current-value-on-subscribe,
//    change de-duplication, probe-driven and pushed updates.
//  * [ApiClient] bounded request/stream timeouts (Requirement 9.2) mapping onto
//    the existing [ApiException] type. A `MockClient` backs a real [ApiClient]
//    so no live network is required.

import 'dart:async';

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/connectivity_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

void main() {
  group('DefaultConnectivityService', () {
    test('emits the current value to a new subscriber, then changes', () async {
      final service = DefaultConnectivityService(initialValue: true);
      addTearDown(service.dispose);

      final seen = <bool>[];
      final sub = service.isOnline.listen(seen.add);
      await Future<void>.delayed(Duration.zero);

      service.setOnline(false);
      service.setOnline(true);
      await Future<void>.delayed(Duration.zero);
      await sub.cancel();

      expect(seen, [true, false, true]);
      expect(service.currentValue, isTrue);
    });

    test('de-duplicates repeated values (only real transitions emit)', () async {
      final service = DefaultConnectivityService(initialValue: true);
      addTearDown(service.dispose);

      final changes = <bool>[];
      final sub = service.isOnline.skip(1).listen(changes.add);
      await Future<void>.delayed(Duration.zero);

      service.setOnline(true); // unchanged -> no emit
      service.setOnline(false); // change -> emit
      service.setOnline(false); // unchanged -> no emit
      await Future<void>.delayed(Duration.zero);
      await sub.cancel();

      expect(changes, [false]);
    });

    test('refresh() resolves online from an injected probe', () async {
      var reachable = false;
      final service = DefaultConnectivityService(
        probe: () async => reachable,
        initialValue: true,
      );
      addTearDown(service.dispose);

      reachable = false;
      expect(await service.refresh(), isFalse);
      expect(service.currentValue, isFalse);

      reachable = true;
      expect(await service.refresh(), isTrue);
      expect(service.currentValue, isTrue);
    });

    test('a throwing probe is treated as offline', () async {
      final service = DefaultConnectivityService(
        probe: () async => throw Exception('socket'),
        initialValue: true,
      );
      addTearDown(service.dispose);

      expect(await service.refresh(), isFalse);
      expect(service.currentValue, isFalse);
    });
  });

  group('ApiClient bounded timeouts', () {
    const base = 'https://api.test';

    test('a stalled request maps onto ApiException (not a hang)', () async {
      final mock = MockClient((request) async {
        // Never responds within the bounded window.
        await Future<void>.delayed(const Duration(seconds: 5));
        return http.Response('{}', 200);
      });
      final api = ApiClient(
        baseUrl: base,
        httpClient: mock,
        requestTimeout: const Duration(milliseconds: 50),
      );

      await expectLater(
        api.getMobileSummary(accessToken: 'token'),
        throwsA(isA<ApiException>()),
      );
    });

    test('a fast response is unaffected by the timeout', () async {
      final mock = MockClient((request) async {
        return http.Response(
          '{"ok": true}',
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(
        baseUrl: base,
        httpClient: mock,
        requestTimeout: const Duration(seconds: 5),
      );

      final result = await api.getMobileSummary(accessToken: 'token');
      expect(result['ok'], isTrue);
    });
  });
}

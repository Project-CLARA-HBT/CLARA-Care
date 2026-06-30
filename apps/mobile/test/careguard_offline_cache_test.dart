// Feature: clara-selfmed-careguard-upgrade — Task 8.2 (Req 6.3).
//
// Dart tests for the mobile CareGuard offline / last-known DDI cache
// (`CareguardOfflineCache` in `lib/core/careguard_offline_cache.dart`).
//
// These pin the load-bearing safety properties of the offline fallback:
//   * Default OFF — caching/labeling is inert unless the flag is on
//     (Requirement 12.1, 12.2).
//   * Projection only — only the four End_User fields are persisted; internal
//     diagnostic fields are never written to device storage (Req 3.4, 6.2).
//   * No fabricated all-clear — a cache miss returns null (Req 6.4).
//
// An in-memory [SessionSecureStorage] double keeps the tests free of platform
// channels. Property-style coverage runs many generated inputs.

import 'dart:convert';
import 'dart:math';

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/careguard_offline_cache.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:flutter_test/flutter_test.dart';

class InMemorySessionSecureStorage implements SessionSecureStorage {
  final Map<String, String> _data = {};

  @override
  Future<String?> read(String key) async => _data[key];

  @override
  Future<void> write(String key, String value) async {
    _data[key] = value;
  }

  @override
  Future<void> delete(String key) async {
    _data.remove(key);
  }

  Map<String, String> get snapshot => Map.unmodifiable(_data);
  bool get isEmpty => _data.isEmpty;
}

Map<String, dynamic> _sampleView() => <String, dynamic>{
      'riskLevel': 'high',
      'alerts': [
        {
          'message': 'Phối hợp này có thể làm tăng nguy cơ chảy máu.',
          'severity': 'high',
          'details': 'Theo dõi dấu hiệu chảy máu.',
        }
      ],
      'recommendations': ['Hỏi bác sĩ hoặc dược sĩ.'],
      'sources': [
        {'label': 'Nguồn cục bộ'}
      ],
    };

void main() {
  group('default OFF: cache is inert (Req 12.1, 12.2)', () {
    test('save is a no-op and read returns null when disabled', () async {
      final storage = InMemorySessionSecureStorage();
      final cache = CareguardOfflineCache(storage: storage, enabled: false);

      expect(await cache.save(_sampleView()), isFalse);
      expect(storage.isEmpty, isTrue);
      expect(await cache.read(), isNull);
    });

    test('does not read a pre-existing entry while disabled', () async {
      final storage = InMemorySessionSecureStorage();
      final enabled = CareguardOfflineCache(storage: storage, enabled: true);
      await enabled.save(_sampleView());

      final disabled = CareguardOfflineCache(storage: storage, enabled: false);
      expect(await disabled.read(), isNull);
    });
  });

  group('round-trip when enabled (Req 6.3)', () {
    test('save then read returns the projection and timestamp', () async {
      final storage = InMemorySessionSecureStorage();
      final cache = CareguardOfflineCache(storage: storage, enabled: true);
      final now = DateTime.utc(2024, 1, 2, 3, 4, 5);

      expect(await cache.save(_sampleView(), now: now), isTrue);

      final cached = await cache.read();
      expect(cached, isNotNull);
      expect(cached!.cachedAt.toUtc(), equals(now));
      expect(cached.view['riskLevel'], 'high');
      expect((cached.view['alerts'] as List).length, 1);
      expect(
        (cached.view['alerts'] as List).first['message'],
        'Phối hợp này có thể làm tăng nguy cơ chảy máu.',
      );
    });

    test('cache miss returns null (never fabricates all-clear, Req 6.4)',
        () async {
      final storage = InMemorySessionSecureStorage();
      final cache = CareguardOfflineCache(storage: storage, enabled: true);
      expect(await cache.read(), isNull);
    });

    test('invalid/tampered payloads are ignored', () async {
      final storage = InMemorySessionSecureStorage();
      final cache = CareguardOfflineCache(storage: storage, enabled: true);

      await storage.write(CareguardOfflineCache.storageKey, '{not json');
      expect(await cache.read(), isNull);

      await storage.write(
        CareguardOfflineCache.storageKey,
        jsonEncode({'version': 999, 'cachedAt': '2024-01-01T00:00:00Z', 'view': _sampleView()}),
      );
      expect(await cache.read(), isNull);
    });

    test('clear removes the cached entry', () async {
      final storage = InMemorySessionSecureStorage();
      final cache = CareguardOfflineCache(storage: storage, enabled: true);
      await cache.save(_sampleView());
      await cache.clear();
      expect(await cache.read(), isNull);
    });
  });

  group('projection drops internal/diagnostic fields (Req 3.4, 6.2)', () {
    test('only the four user-facing fields survive a write', () async {
      final storage = InMemorySessionSecureStorage();
      final cache = CareguardOfflineCache(storage: storage, enabled: true);

      final polluted = <String, dynamic>{
        ..._sampleView(),
        'mode': 'external_plus_local',
        'fallback_used': true,
        'source_errors': {
          'openfda': ['openfda http_400']
        },
        'alerts': [
          {
            'message': 'Phối hợp này có thể làm tăng nguy cơ chảy máu.',
            'severity': 'high',
            'sources': ['openfda', 'rxnav'],
            'rawSeverity': 'critical',
          }
        ],
      };

      await cache.save(polluted);
      final stored = storage.snapshot[CareguardOfflineCache.storageKey]!;
      final decoded = jsonDecode(stored) as Map<String, dynamic>;
      final view = decoded['view'] as Map<String, dynamic>;

      expect(view.keys.toSet(),
          equals({'riskLevel', 'alerts', 'recommendations', 'sources'}));
      final alert = (view['alerts'] as List).first as Map<String, dynamic>;
      expect(alert.keys.toSet(), equals({'message', 'severity'}));

      final lower = stored.toLowerCase();
      for (final leak in ['mode', 'fallback', 'source_errors', 'openfda', 'rxnav', 'rawseverity']) {
        expect(lower.contains(leak), isFalse, reason: 'leaked: $leak');
      }
    });

    test('property: persisted payload never carries internal alert keys', () {
      final rng = Random(424242);
      const iterations = 200;
      const messages = [
        'Phối hợp này có thể làm tăng nguy cơ chảy máu.',
        'Phối hợp này có thể làm tăng kali máu.',
      ];
      const severities = ['low', 'medium', 'high', 'critical', 'unknown'];

      for (var i = 0; i < iterations; i++) {
        final alertCount = rng.nextInt(4);
        final alerts = List.generate(alertCount, (_) {
          return <String, dynamic>{
            'message': messages[rng.nextInt(messages.length)],
            'severity': severities[rng.nextInt(severities.length)],
            // Adversarial internal fields a caller might smuggle in.
            'source_errors': {
              'openfda': ['openfda http_400']
            },
            'mode': 'local_only',
          };
        });
        final view = <String, dynamic>{
          'riskLevel': severities[rng.nextInt(severities.length)],
          'alerts': alerts,
          'recommendations': const ['Hỏi bác sĩ.'],
          'sources': const [
            {'label': 'OpenFDA'}
          ],
        };

        final projected = CareguardOfflineCache.projectForCache(view);
        for (final alert in projected['alerts'] as List) {
          final keys = (alert as Map<String, dynamic>).keys.toSet();
          expect(keys.contains('source_errors'), isFalse);
          expect(keys.contains('mode'), isFalse);
        }
        expect((projected).keys.contains('source_errors'), isFalse);
      }
    });
  });

  group('isLikelyOfflineFailure', () {
    test('treats no-status / gateway ApiException as offline', () {
      expect(isLikelyOfflineFailure(ApiException(message: 'Không thể kết nối tới server.')),
          isTrue);
      expect(
          isLikelyOfflineFailure(ApiException(message: 'gateway', statusCode: 503)), isTrue);
      expect(
          isLikelyOfflineFailure(ApiException(message: 'gateway', statusCode: 504)), isTrue);
    });

    test('treats a real 4xx server rejection as NOT offline', () {
      expect(
          isLikelyOfflineFailure(ApiException(message: 'Cần ít nhất 2 thuốc.', statusCode: 400)),
          isFalse);
      expect(
          isLikelyOfflineFailure(ApiException(message: 'Forbidden', statusCode: 403)), isFalse);
    });

    test('treats arbitrary socket/timeout errors as offline', () {
      expect(isLikelyOfflineFailure(Exception('SocketException: failed host lookup')),
          isTrue);
    });
  });
}

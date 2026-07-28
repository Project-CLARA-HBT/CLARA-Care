// Unit tests for the additive JWT token-refresh added to [ApiClient] in
// task 1.3 of the clara-mobile-feature-parity spec.
//
// Covers the refresh state machine (design "Request flow — token refresh"):
//   * Pre-flight expiry check before an authenticated request (Req 6.2).
//   * A single 401-retry that calls `POST /auth/refresh` once (Req 6.2).
//   * Persisting the refreshed session on success, or clearing it on failure
//     and surfacing a PII-free auth error that routes to login (Req 6.3).
//   * Back-compatibility: with no hooks attached the client behaves exactly as
//     before (no pre-flight, no refresh-retry).
//
// A `MockClient` backs a real [ApiClient]; a real [PersistentSessionStore]
// (over an in-memory secure-storage double) backs [SessionStoreAuthHooks], so
// the genuine persist/clear contract is exercised without platform channels or
// live network.

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

/// Minimal in-memory [SessionSecureStorage] double (no platform channels).
class _InMemoryStorage implements SessionSecureStorage {
  _InMemoryStorage([Map<String, String>? seed]) : _data = {...?seed};
  final Map<String, String> _data;

  bool get isEmpty => _data.isEmpty;

  @override
  Future<String?> read(String key) async => _data[key];
  @override
  Future<void> write(String key, String value) async => _data[key] = value;
  @override
  Future<void> delete(String key) async => _data.remove(key);
}

String _seg(Map<String, dynamic> map) =>
    base64Url.encode(utf8.encode(jsonEncode(map))).replaceAll('=', '');

/// Builds a real-looking JWT whose `exp` is [offset] from now.
String _jwt(Duration offset) {
  final exp = DateTime.now().toUtc().add(offset).millisecondsSinceEpoch ~/ 1000;
  return '${_seg(const {'alg': 'HS256', 'typ': 'JWT'})}'
      '.${_seg({'exp': exp, 'sub': 'user'})}'
      '.c2lnbmF0dXJl';
}

final String _validAccess = _jwt(const Duration(hours: 1));
final String _expiredAccess = _jwt(const Duration(seconds: -10));
final String _refreshedAccess = _jwt(const Duration(hours: 2));

Future<PersistentSessionStore> _authedStore({
  required String accessToken,
  String refreshToken = 'refresh-token',
  String role = 'normal',
}) async {
  final store = PersistentSessionStore(storage: _InMemoryStorage());
  await store.setSession(
    email: 'user@example.com',
    accessToken: accessToken,
    refreshToken: refreshToken,
    role: role,
  );
  return store;
}

void main() {
  const base = 'https://api.test';

  http.Response ok(Map<String, dynamic> body) => http.Response(
        jsonEncode(body),
        200,
        headers: {'content-type': 'application/json'},
      );

  group('pre-flight expiry refresh (Req 6.2)', () {
    test('expired access token + valid refresh -> refresh then proceed',
        () async {
      final store = await _authedStore(accessToken: _expiredAccess);
      var refreshCalls = 0;
      var summaryCalls = 0;
      String? bearerOnSummary;

      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/refresh')) {
          refreshCalls++;
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          expect(body['refresh_token'], 'refresh-token');
          return ok({
            'access_token': _refreshedAccess,
            'refresh_token': 'refresh-token-2',
            'role': 'doctor',
            'token_type': 'bearer',
          });
        }
        summaryCalls++;
        bearerOnSummary = request.headers['Authorization'];
        return ok({'ok': true});
      });

      final api = ApiClient(baseUrl: base, httpClient: mock)
        ..authHooks = SessionStoreAuthHooks(store);

      final result = await api.getMobileSummary(accessToken: _expiredAccess);

      expect(result['ok'], isTrue);
      expect(refreshCalls, 1, reason: 'one pre-flight refresh');
      expect(summaryCalls, 1, reason: 'summary sent once, with the new token');
      expect(bearerOnSummary, 'Bearer $_refreshedAccess');
      // New session persisted (Req 6.2).
      expect(store.accessToken, _refreshedAccess);
      expect(store.refreshToken, 'refresh-token-2');
      expect(store.role, 'doctor');
    });

    test('expired access token + no refresh token -> clear + auth error',
        () async {
      final store =
          await _authedStore(accessToken: _expiredAccess, refreshToken: '');
      var refreshCalls = 0;
      var summaryCalls = 0;

      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/refresh')) {
          refreshCalls++;
        } else {
          summaryCalls++;
        }
        return ok({'ok': true});
      });

      final api = ApiClient(baseUrl: base, httpClient: mock)
        ..authHooks = SessionStoreAuthHooks(store);

      await expectLater(
        api.getMobileSummary(accessToken: _expiredAccess),
        throwsA(
            isA<ApiException>().having((e) => e.statusCode, 'statusCode', 401)),
      );
      expect(refreshCalls, 0, reason: 'no refresh token to exchange');
      expect(summaryCalls, 0, reason: 'request never sent');
      expect(store.isAuthenticated, isFalse, reason: 'session cleared (6.3)');
    });
  });

  group('401 retry (Req 6.2)', () {
    test('valid token, server 401 -> single refresh + one resend succeeds',
        () async {
      final store = await _authedStore(accessToken: _validAccess);
      var refreshCalls = 0;
      var summaryCalls = 0;

      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/refresh')) {
          refreshCalls++;
          return ok({
            'access_token': _refreshedAccess,
            'refresh_token': 'refresh-token-2',
            'role': 'normal',
          });
        }
        summaryCalls++;
        // First attempt rejected; the post-refresh resend succeeds.
        if (summaryCalls == 1) {
          return http.Response('{"detail":"expired"}', 401,
              headers: {'content-type': 'application/json'});
        }
        return ok({'ok': true});
      });

      final api = ApiClient(baseUrl: base, httpClient: mock)
        ..authHooks = SessionStoreAuthHooks(store);

      final result = await api.getMobileSummary(accessToken: _validAccess);
      expect(result['ok'], isTrue);
      expect(refreshCalls, 1);
      expect(summaryCalls, 2, reason: 'original + exactly one resend');
      expect(store.accessToken, _refreshedAccess);
    });

    test('failed refresh -> clear session + auth error (no loop)', () async {
      final store = await _authedStore(accessToken: _validAccess);
      var refreshCalls = 0;
      var summaryCalls = 0;

      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/refresh')) {
          refreshCalls++;
          return http.Response('{"detail":"invalid refresh"}', 401,
              headers: {'content-type': 'application/json'});
        }
        summaryCalls++;
        return http.Response('{"detail":"expired"}', 401,
            headers: {'content-type': 'application/json'});
      });

      final api = ApiClient(baseUrl: base, httpClient: mock)
        ..authHooks = SessionStoreAuthHooks(store);

      await expectLater(
        api.getMobileSummary(accessToken: _validAccess),
        throwsA(
            isA<ApiException>().having((e) => e.statusCode, 'statusCode', 401)),
      );
      expect(refreshCalls, 1, reason: 'exactly one refresh attempt');
      expect(summaryCalls, 1, reason: 'no resend after a failed refresh');
      expect(store.isAuthenticated, isFalse, reason: 'session cleared (6.3)');
    });

    test('persistent 401 even after a successful refresh does not loop',
        () async {
      final store = await _authedStore(accessToken: _validAccess);
      var refreshCalls = 0;
      var summaryCalls = 0;

      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/refresh')) {
          refreshCalls++;
          return ok({
            'access_token': _refreshedAccess,
            'refresh_token': 'r2',
            'role': 'normal',
          });
        }
        summaryCalls++;
        // Always 401, even with a fresh token.
        return http.Response('{"detail":"expired"}', 401,
            headers: {'content-type': 'application/json'});
      });

      final api = ApiClient(baseUrl: base, httpClient: mock)
        ..authHooks = SessionStoreAuthHooks(store);

      await expectLater(
        api.getMobileSummary(accessToken: _validAccess),
        throwsA(isA<ApiException>()),
      );
      // Bounded: one refresh, original send + one resend only.
      expect(refreshCalls, 1);
      expect(summaryCalls, 2);
    });

    test('onCleared side-effect runs after a failed refresh', () async {
      final store = await _authedStore(accessToken: _validAccess);
      var routedToLogin = false;

      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/refresh')) {
          return http.Response('{}', 401);
        }
        return http.Response('{}', 401);
      });

      final api = ApiClient(baseUrl: base, httpClient: mock)
        ..authHooks = SessionStoreAuthHooks(
          store,
          onCleared: () async => routedToLogin = true,
        );

      await expectLater(
        api.getMobileSummary(accessToken: _validAccess),
        throwsA(isA<ApiException>()),
      );
      expect(routedToLogin, isTrue);
      expect(store.isAuthenticated, isFalse);
    });
  });

  group('back-compatibility (no hooks attached)', () {
    test('401 surfaces directly without any refresh attempt', () async {
      var refreshCalls = 0;
      var summaryCalls = 0;

      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/refresh')) {
          refreshCalls++;
          return ok({'access_token': _refreshedAccess});
        }
        summaryCalls++;
        return http.Response('{"detail":"expired"}', 401,
            headers: {'content-type': 'application/json'});
      });

      // No authHooks attached.
      final api = ApiClient(baseUrl: base, httpClient: mock);

      await expectLater(
        api.getMobileSummary(accessToken: _expiredAccess),
        throwsA(
            isA<ApiException>().having((e) => e.statusCode, 'statusCode', 401)),
      );
      expect(refreshCalls, 0, reason: 'no refresh wiring -> legacy behavior');
      expect(summaryCalls, 1, reason: 'request sent once, no retry');
    });
  });

  group('concurrency', () {
    test('parallel expired requests share a single refresh', () async {
      final store = await _authedStore(accessToken: _expiredAccess);
      var refreshCalls = 0;

      final mock = MockClient((request) async {
        if (request.url.path.endsWith('/auth/refresh')) {
          refreshCalls++;
          // Small delay so the second caller joins the in-flight refresh.
          await Future<void>.delayed(const Duration(milliseconds: 10));
          return ok({
            'access_token': _refreshedAccess,
            'refresh_token': 'r2',
            'role': 'normal',
          });
        }
        return ok({'ok': true});
      });

      final api = ApiClient(baseUrl: base, httpClient: mock)
        ..authHooks = SessionStoreAuthHooks(store);

      final results = await Future.wait([
        api.getMobileSummary(accessToken: _expiredAccess),
        api.getMobileSummary(accessToken: _expiredAccess),
      ]);

      expect(results.every((r) => r['ok'] == true), isTrue);
      expect(refreshCalls, 1, reason: 'concurrent refreshes coalesced');
    });
  });
}

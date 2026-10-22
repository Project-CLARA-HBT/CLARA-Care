import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _InMemoryStorage implements SessionSecureStorage {
  _InMemoryStorage([Map<String, String>? initial])
      : _store = initial != null ? Map<String, String>.from(initial) : {};

  final Map<String, String> _store;

  @override
  Future<void> delete(String key) async {
    _store.remove(key);
  }

  @override
  Future<String?> read(String key) async {
    return _store[key];
  }

  @override
  Future<void> write(String key, String value) async {
    _store[key] = value;
  }
}

String _seg(Map<String, dynamic> map) =>
    base64Url.encode(utf8.encode(jsonEncode(map))).replaceAll('=', '');

String _jwt(Duration offset) {
  final exp = DateTime.now().toUtc().add(offset).millisecondsSinceEpoch ~/ 1000;
  return '${_seg(const {'alg': 'HS256', 'typ': 'JWT'})}'
      '.${_seg({'exp': exp, 'sub': 'user-123'})}'
      '.c2lnbmF0dXJl';
}

void main() {
  group('ApiClient Tenant Organization Header Propagation', () {
    test('propagates X-CLARA-Organization-Id header when configured explicitly', () async {
      String? capturedOrgHeader;
      final mockClient = MockClient((request) async {
        capturedOrgHeader = request.headers['X-CLARA-Organization-Id'];
        return http.Response(jsonEncode({'status': 'ok'}), 200, headers: {
          'content-type': 'application/json',
        });
      });

      final client = ApiClient(
        baseUrl: 'https://api.theclaracare.com',
        httpClient: mockClient,
        organizationId: 'org-hospital-central',
      );

      final res = await client.getLifeMapToday(accessToken: _jwt(const Duration(hours: 1)));
      expect(res, isNotNull);
      expect(capturedOrgHeader, equals('org-hospital-central'));
    });

    test('omits X-CLARA-Organization-Id header when organizationId is null or empty', () async {
      String? capturedOrgHeader;
      final mockClient = MockClient((request) async {
        capturedOrgHeader = request.headers['X-CLARA-Organization-Id'];
        return http.Response(jsonEncode({'status': 'ok'}), 200, headers: {
          'content-type': 'application/json',
        });
      });

      final client = ApiClient(
        baseUrl: 'https://api.theclaracare.com',
        httpClient: mockClient,
      );

      await client.getLifeMapToday(accessToken: _jwt(const Duration(hours: 1)));
      expect(capturedOrgHeader, isNull);
    });

    test('propagates organizationId resolved via attached SessionStoreAuthHooks', () async {
      String? capturedOrgHeader;
      final mockClient = MockClient((request) async {
        capturedOrgHeader = request.headers['X-CLARA-Organization-Id'];
        return http.Response(jsonEncode({'status': 'ok'}), 200, headers: {
          'content-type': 'application/json',
        });
      });

      final validToken = _jwt(const Duration(hours: 2));
      final storage = _InMemoryStorage();
      final store = PersistentSessionStore(storage: storage);
      await store.setSession(
        email: 'doctor@hospital.vn',
        accessToken: validToken,
        refreshToken: 'refresh-token',
        role: 'doctor',
        organizationId: 'org-clinic-danang',
      );

      final client = ApiClient(
        baseUrl: 'https://api.theclaracare.com',
        httpClient: mockClient,
        authHooks: SessionStoreAuthHooks(store),
      );

      await client.getLifeMapToday(accessToken: validToken);
      expect(capturedOrgHeader, equals('org-clinic-danang'));

      // Switch organization dynamically
      await store.setOrganizationId('org-clinic-saigon');
      await client.getLifeMapToday(accessToken: validToken);
      expect(capturedOrgHeader, equals('org-clinic-saigon'));
    });

    test('explicit organizationId on client takes precedence over authHooks', () async {
      String? capturedOrgHeader;
      final mockClient = MockClient((request) async {
        capturedOrgHeader = request.headers['X-CLARA-Organization-Id'];
        return http.Response(jsonEncode({'status': 'ok'}), 200, headers: {
          'content-type': 'application/json',
        });
      });

      final validToken = _jwt(const Duration(hours: 2));
      final storage = _InMemoryStorage();
      final store = PersistentSessionStore(storage: storage);
      await store.setSession(
        email: 'doctor@hospital.vn',
        accessToken: validToken,
        refreshToken: 'refresh-token',
        role: 'doctor',
        organizationId: 'org-store-default',
      );

      final client = ApiClient(
        baseUrl: 'https://api.theclaracare.com',
        httpClient: mockClient,
        authHooks: SessionStoreAuthHooks(store),
        organizationId: 'org-explicit-override',
      );

      await client.getLifeMapToday(accessToken: validToken);
      expect(capturedOrgHeader, equals('org-explicit-override'));

      // Clear explicit override -> falls back to store
      client.setOrganization(null);
      await client.getLifeMapToday(accessToken: validToken);
      expect(capturedOrgHeader, equals('org-store-default'));
    });
  });

  group('PersistentSessionStore Organization Scoping', () {
    test('persists organizationId across hydrate and clear cycles', () async {
      final validToken = _jwt(const Duration(hours: 3));
      final storage = _InMemoryStorage();
      final store1 = PersistentSessionStore(storage: storage);

      await store1.setSession(
        email: 'user@clara.vn',
        accessToken: validToken,
        refreshToken: 'refresh-jwt',
        role: 'normal',
        organizationId: 'org-patient-affiliate',
      );

      expect(store1.organizationId, equals('org-patient-affiliate'));

      // Simulate app relaunch
      final store2 = PersistentSessionStore(storage: storage);
      await store2.hydrate();
      expect(store2.organizationId, equals('org-patient-affiliate'));

      // Clear session purges organization context
      await store2.clear();
      expect(store2.organizationId, isNull);

      final store3 = PersistentSessionStore(storage: storage);
      await store3.hydrate();
      expect(store3.organizationId, isNull);
    });
  });
}

// Unit tests for the additive auth-lifecycle client methods added to
// [ApiClient] in task 8.1 of the clara-mobile-feature-parity spec.
//
// These pin the actual server contract (method/path/headers/body) each method
// drives against the CLARA_API Auth routes mounted under `/api/v1/auth` (see
// `services/api/.../endpoints/auth.py`): register, verify-email,
// forgot-password, reset-password, and logout. The request/response bodies
// match the server pydantic schemas exactly (`RegisterRequest`/
// `RegisterResponse`, `VerifyEmailRequest`, `ForgotPasswordRequest`/
// `ForgotPasswordResponse`, `ResetPasswordRequest`). Tests use a
// `MockClient`-backed real [ApiClient] so no live server or platform channels
// are required (Req 6.1).

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

void main() {
  const base = 'https://api.test';

  group('register', () {
    test('POSTs RegisterRequest to /api/v1/auth/register (unauthenticated)',
        () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'user_id': 1,
            'email': 'a@b.com',
            'role': 'normal',
            'is_email_verified': false,
            'email_delivery_status': 'sent',
            'verification_token_preview': null,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.register(payload: {
        'email': 'a@b.com',
        'password': 'secret123',
        'full_name': 'Người Dùng',
        'role': 'normal',
        'accepted_terms': true,
        'accepted_privacy': true,
        'accepted_medical_consent': true,
      });

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/auth/register');
      // Unauthenticated endpoint: no Authorization header.
      expect(captured.headers.containsKey('Authorization'), isFalse);
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['email'], 'a@b.com');
      expect(body['password'], 'secret123');
      expect(body['accepted_terms'], true);
      expect(body['accepted_privacy'], true);
      expect(body['accepted_medical_consent'], true);
      expect(result['user_id'], 1);
      expect(result['role'], 'normal');
      expect(result['is_email_verified'], false);
    });

    test('surfaces a duplicate-email 409 as ApiException', () async {
      final mock = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Email đã tồn tại'}),
          409,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      expect(
        () => api.register(payload: {
          'email': 'a@b.com',
          'password': 'secret123',
        }),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 409)
              .having((e) => e.message, 'message', 'Email đã tồn tại'),
        ),
      );
    });
  });

  group('verifyEmail', () {
    test('POSTs {token} to /api/v1/auth/verify-email', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({'verified': true, 'email': 'a@b.com'}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.verifyEmail(token: 'verify-tok');

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/auth/verify-email');
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body, {'token': 'verify-tok'});
      expect(result['verified'], isTrue);
      expect(result['email'], 'a@b.com');
    });

    test('surfaces an invalid-token 400 as ApiException', () async {
      final mock = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Token xác thực không hợp lệ hoặc đã hết hạn'}),
          400,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      expect(
        () => api.verifyEmail(token: 'bad'),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 400)
              .having((e) => e.message, 'message',
                  'Token xác thực không hợp lệ hoặc đã hết hạn'),
        ),
      );
    });
  });

  group('forgotPassword', () {
    test('POSTs {email} to /api/v1/auth/forgot-password', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'accepted': true,
            'email_delivery_status': 'sent',
            'reset_token_preview': null,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.forgotPassword(email: 'a@b.com');

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/auth/forgot-password');
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body, {'email': 'a@b.com'});
      expect(result['accepted'], isTrue);
      expect(result['email_delivery_status'], 'sent');
    });
  });

  group('resetPassword', () {
    test('POSTs {token,new_password} to /api/v1/auth/reset-password', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({'reset': true}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.resetPassword(
        token: 'reset-tok',
        newPassword: 'newsecret1',
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/auth/reset-password');
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body, {'token': 'reset-tok', 'new_password': 'newsecret1'});
      expect(result['reset'], isTrue);
    });

    test('surfaces an invalid-reset-token 400 as ApiException', () async {
      final mock = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Token đặt lại mật khẩu không hợp lệ'}),
          400,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      expect(
        () => api.resetPassword(token: 'bad', newPassword: 'newsecret1'),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 400)
              .having((e) => e.message, 'message',
                  'Token đặt lại mật khẩu không hợp lệ'),
        ),
      );
    });
  });

  group('logout', () {
    test('POSTs empty body to /api/v1/auth/logout with bearer token', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({'logged_out': true, 'revoked_refresh_sessions': 2}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.logout(accessToken: 'sess-token');

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/auth/logout');
      expect(captured.headers['Authorization'], 'Bearer sess-token');
      expect(jsonDecode(captured.body), <String, dynamic>{});
      expect(result['logged_out'], isTrue);
      expect(result['revoked_refresh_sessions'], 2);
    });

    test('works without a token (optional server gate)', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({'logged_out': true, 'revoked_refresh_sessions': 0}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.logout();

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/auth/logout');
      expect(captured.headers.containsKey('Authorization'), isFalse);
      expect(result['logged_out'], isTrue);
    });
  });
}

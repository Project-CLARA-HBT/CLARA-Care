// Unit tests for the additive ambient-scribe client methods added to
// [ApiClient] in task 6.1 of the clara-mobile-feature-parity spec.
//
// These pin the actual server contract (method/path/headers/body) each scribe
// method drives against the Scribe_API routes mounted under `/api/v1/scribe`
// (see `services/api/.../endpoints/scribe.py`) and mirror the web scribe client
// (`apps/web/lib/scribe.ts`). A `MockClient` (package:http/testing) backs a
// real [ApiClient] so no live server or platform channels are required
// (Req 4.1, 4.2, 4.4, 14.6, 15.5).

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

void main() {
  const token = 'test-token';
  const base = 'https://api.test';

  group('listScribeSessions', () {
    test('GETs /api/v1/scribe/sessions with pagination query', () async {
      late Uri capturedUri;
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        capturedUri = request.url;
        return http.Response(
          jsonEncode({
            'items': [
              {'id': 1, 'title': 'Visit A', 'status': 'ready', 'transcript': ''},
            ],
            'total': 1,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result =
          await api.listScribeSessions(accessToken: token, limit: 5, offset: 10);

      expect(captured.method, 'GET');
      expect(capturedUri.path, '/api/v1/scribe/sessions');
      expect(capturedUri.queryParameters['limit'], '5');
      expect(capturedUri.queryParameters['offset'], '10');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect((result['items'] as List), hasLength(1));
      expect(result['total'], 1);
    });
  });

  group('createScribeSession', () {
    test('POSTs the create payload to /api/v1/scribe/sessions', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'id': 7,
            'title': 'New visit',
            'status': 'ready',
            'transcript': 'patient reports cough',
            'soap': {'subjective': 'cough'},
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.createScribeSession(
        accessToken: token,
        payload: {
          'title': 'New visit',
          'transcript': 'patient reports cough',
          'auto_generate_soap': true,
        },
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/scribe/sessions');
      expect(captured.headers['Authorization'], 'Bearer $token');
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['title'], 'New visit');
      expect(body['auto_generate_soap'], true);
      expect(result['id'], 7);
      expect(result['soap']['subjective'], 'cough');
    });
  });

  group('getScribeSession', () {
    test('GETs the owned session by id', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'id': 42,
            'title': 'Visit',
            'status': 'ready',
            'transcript': 'x',
            'soap': {'plan': 'rest'},
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.getScribeSession(accessToken: token, sessionId: 42);

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/v1/scribe/sessions/42');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(result['id'], 42);
      expect(result['soap']['plan'], 'rest');
    });

    test('surfaces a 404 as ApiException with the server detail', () async {
      final mock = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Session không tồn tại'}),
          404,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      expect(
        () => api.getScribeSession(accessToken: token, sessionId: 999),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 404)
              .having((e) => e.message, 'message', 'Session không tồn tại'),
        ),
      );
    });
  });

  group('transcribeScribeAudio', () {
    test('sends multipart audio_file + form fields to /api/v1/scribe/transcribe',
        () async {
      // MockClient finalizes the MultipartRequest into a plain Request before
      // invoking the handler, so assert on the serialized content-type boundary
      // and body bytes rather than the request type.
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({'text': 'hello world', 'language': 'vi'}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.transcribeScribeAudio(
        accessToken: token,
        audioBytes: utf8.encode('fake-audio-bytes'),
        filename: 'clip.webm',
        language: 'vi',
        sessionId: 11,
        appendToSession: true,
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/scribe/transcribe');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(
        captured.headers['content-type'],
        contains('multipart/form-data'),
      );
      expect(captured.body, contains('name="audio_file"'));
      expect(captured.body, contains('filename="clip.webm"'));
      expect(captured.body, contains('name="language"'));
      expect(captured.body, contains('name="session_id"'));
      expect(captured.body, contains('11'));
      expect(captured.body, contains('name="append_to_session"'));
      expect(captured.body, contains('true'));
      expect(result['text'], 'hello world');
    });

    test('omits optional form fields when not provided', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({'text': 'ok'}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      await api.transcribeScribeAudio(
        accessToken: token,
        audioBytes: utf8.encode('x'),
      );

      expect(captured.body, contains('name="audio_file"'));
      expect(captured.body, isNot(contains('name="language"')));
      expect(captured.body, isNot(contains('name="session_id"')));
      expect(captured.body, isNot(contains('name="append_to_session"')));
    });
  });

  group('regenerateScribeSession', () {
    test('POSTs to /api/v1/scribe/sessions/{id}/regenerate', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'id': 3,
            'title': 'Visit',
            'status': 'ready',
            'transcript': 'updated',
            'soap': {'assessment': 'better'},
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.regenerateScribeSession(
        accessToken: token,
        sessionId: 3,
        payload: {'transcript': 'updated'},
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/scribe/sessions/3/regenerate');
      expect(jsonDecode(captured.body)['transcript'], 'updated');
      expect(result['soap']['assessment'], 'better');
    });

    test('sends an empty body when no payload is provided', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({'id': 4, 'status': 'ready', 'title': '', 'transcript': 'x'}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      await api.regenerateScribeSession(accessToken: token, sessionId: 4);

      expect(captured.url.path, '/api/v1/scribe/sessions/4/regenerate');
      expect(jsonDecode(captured.body), <String, dynamic>{});
    });
  });

  group('captureScribeConsent', () {
    test('POSTs method/scope to /sessions/{id}/consent', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({'session_id': 5, 'consent_id': 9, 'captured': true}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.captureScribeConsent(
        accessToken: token,
        sessionId: 5,
        method: 'written',
        scope: 'encounter',
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/scribe/sessions/5/consent');
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['method'], 'written');
      expect(body['scope'], 'encounter');
      expect(result['captured'], isTrue);
      expect(result['consent_id'], 9);
    });

    test('defaults to verbal/encounter when not specified', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({'session_id': 5, 'consent_id': 1, 'captured': true}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      await api.captureScribeConsent(accessToken: token, sessionId: 5);

      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['method'], 'verbal');
      expect(body['scope'], 'encounter');
    });
  });

  group('revokeScribeConsent', () {
    test('POSTs to /sessions/{id}/consent/revoke', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({'session_id': 5, 'consent_id': 9, 'revoked': true}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result =
          await api.revokeScribeConsent(accessToken: token, sessionId: 5);

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/scribe/sessions/5/consent/revoke');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(result['revoked'], isTrue);
    });

    test('surfaces a 404 (no active consent) as ApiException', () async {
      final mock = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Không có consent đang hiệu lực để thu hồi.'}),
          404,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      expect(
        () => api.revokeScribeConsent(accessToken: token, sessionId: 5),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 404)
              .having((e) => e.message, 'message',
                  'Không có consent đang hiệu lực để thu hồi.'),
        ),
      );
    });
  });
}

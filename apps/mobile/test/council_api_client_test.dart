// Verifies the Council case-lifecycle client methods (clara-council-upgrade
// Requirement 8.1, 8.2) target the existing Council_API endpoints with the
// shared request/response shapes. A `MockClient` (package:http/testing) backs a
// real [ApiClient] so the request method, path, auth header, and body are
// exercised without a live server.

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

void main() {
  const token = 'test-token';
  const base = 'https://api.test';

  group('Council case lifecycle client', () {
    test('createCouncilCase POSTs to /council/cases with the create payload',
        () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request as http.Request;
        return http.Response(
          jsonEncode({'id': 7, 'title': 'Case A', 'status': 'draft'}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.createCouncilCase(
        accessToken: token,
        payload: {'title': 'Case A', 'intake_mode': 'transcript'},
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/council/cases');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(jsonDecode(captured.body)['title'], 'Case A');
      expect(result['id'], 7);
    });

    test('listCouncilCases GETs /council/cases with pagination query', () async {
      late Uri capturedUri;
      final mock = MockClient((request) async {
        capturedUri = request.url;
        return http.Response(
          jsonEncode({'items': [], 'total': 0}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      await api.listCouncilCases(accessToken: token, limit: 5, offset: 10);

      expect(capturedUri.path, '/api/v1/council/cases');
      expect(capturedUri.queryParameters['limit'], '5');
      expect(capturedUri.queryParameters['offset'], '10');
    });

    test('getCouncilCase GETs the owned case by id', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request as http.Request;
        return http.Response(
          jsonEncode({'id': 42, 'result': {'consensus': {}}}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.getCouncilCase(accessToken: token, caseId: 42);

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/v1/council/cases/42');
      expect(result['id'], 42);
    });

    test('updateCouncilCase PATCHes the specialist selection onto the case',
        () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request as http.Request;
        return http.Response(
          jsonEncode({'id': 9}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      await api.updateCouncilCase(
        accessToken: token,
        caseId: 9,
        payload: {
          'request': {
            'specialists': ['cardiology', 'neurology'],
            'specialist_count': 2,
          },
        },
      );

      expect(captured.method, 'PATCH');
      expect(captured.url.path, '/api/v1/council/cases/9');
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['request']['specialists'], ['cardiology', 'neurology']);
    });

    test('runCouncilCase POSTs run overrides to /cases/{id}/run', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request as http.Request;
        return http.Response(
          jsonEncode({'id': 3, 'result': {'final_recommendation': 'x'}}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.runCouncilCase(
        accessToken: token,
        caseId: 3,
        specialistCount: 4,
        specialists: ['cardiology'],
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/council/cases/3/run');
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['specialist_count'], 4);
      expect(body['specialists'], ['cardiology']);
      expect(result['result']['final_recommendation'], 'x');
    });

    test('submitCouncilCaseIntake sends multipart form to /cases/{id}/intake',
        () async {
      // MockClient finalizes the MultipartRequest into a plain Request before
      // invoking the handler, so assert on the serialized content-type boundary
      // and body bytes rather than the request type.
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({'id': 11, 'intake': {'symptoms': []}}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.submitCouncilCaseIntake(
        accessToken: token,
        caseId: 11,
        transcript: 'patient reports chest pain',
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/council/cases/11/intake');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(
        captured.headers['content-type'],
        contains('multipart/form-data'),
      );
      expect(captured.body, contains('name="transcript"'));
      expect(captured.body, contains('patient reports chest pain'));
      expect(result['id'], 11);
    });

    test('error responses surface as ApiException with the server detail',
        () async {
      final mock = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Case không tồn tại'}),
          404,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      expect(
        () => api.getCouncilCase(accessToken: token, caseId: 999),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 404)
              .having((e) => e.message, 'message', 'Case không tồn tại'),
        ),
      );
    });
  });
}

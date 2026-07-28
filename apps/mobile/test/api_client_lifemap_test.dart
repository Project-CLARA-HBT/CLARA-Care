// Unit tests for the additive LifeMap / PHR-onboarding / medication-courses
// client methods added to [ApiClient] for the clara-mobile-unified spec.
//
// Covers request method/path/headers/body for:
//   * getLifeMapToday        -> GET  /api/v1/lifemap/today
//   * createLifeMapEpisode   -> POST /api/v1/lifemap/episodes (+ Idempotency-Key)
//   * createLifeMapTask      -> POST /api/v1/lifemap/episodes/{id}/tasks
//   * acceptLifeMapTask      -> POST /api/v1/lifemap/tasks/{id}/accept
//   * completeLifeMapTask    -> POST /api/v1/lifemap/tasks/{id}/complete
//   * getPhrOnboarding       -> GET  /api/v1/phr/onboarding
//   * updatePhrOnboarding    -> PATCH /api/v1/phr/onboarding
//   * getMedicationCourses   -> GET  /api/v1/medication-courses
//   * createMedicationCourse -> POST /api/v1/medication-courses (+ Idempotency-Key)
//
// A `MockClient` backs a real [ApiClient] so headers/body/paths are exercised
// without a live server or platform channels.

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

void main() {
  const token = 'test-token';
  const base = 'https://api.test';

  http.Response ok(Map<String, dynamic> body) => http.Response(
        jsonEncode(body),
        200,
        headers: const {'content-type': 'application/json'},
      );

  group('LifeMap / Today wrappers', () {
    test('getLifeMapToday GETs /api/v1/lifemap/today with bearer', () async {
      late http.Request captured;
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          captured = request;
          return ok(
              {'tasks': [], 'episodes': [], 'pending_confirmation_count': 0});
        }),
      );

      final result = await client.getLifeMapToday(accessToken: token);

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/v1/lifemap/today');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(result['pending_confirmation_count'], 0);
    });

    test(
        'createLifeMapEpisode POSTs title/goal/priority with an Idempotency-Key',
        () async {
      late http.Request captured;
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          captured = request;
          return ok({'id': 'ep-1', 'status': 'open'});
        }),
      );

      await client.createLifeMapEpisode(
        accessToken: token,
        title: 'Theo dõi giấc ngủ',
        goal: 'Ngủ đều hơn',
        priority: 'soon',
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/lifemap/episodes');
      expect(captured.headers['Idempotency-Key'], isNotEmpty);
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['title'], 'Theo dõi giấc ngủ');
      expect(body['goal'], 'Ngủ đều hơn');
      expect(body['priority'], 'soon');
    });

    test('createLifeMapTask POSTs under the episode path', () async {
      late http.Request captured;
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          captured = request;
          return ok({'id': 't-1', 'status': 'proposed'});
        }),
      );

      await client.createLifeMapTask(
        accessToken: token,
        episodeId: 'ep-1',
        title: 'Ghi lại giờ ngủ',
      );

      expect(captured.url.path, '/api/v1/lifemap/episodes/ep-1/tasks');
      expect(captured.headers['Idempotency-Key'], isNotEmpty);
    });

    test('acceptLifeMapTask and completeLifeMapTask hit the right paths',
        () async {
      final paths = <String>[];
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          paths.add(request.url.path);
          return ok({'id': 't-1', 'status': 'accepted'});
        }),
      );

      await client.acceptLifeMapTask(accessToken: token, taskId: 't-1');
      await client.completeLifeMapTask(accessToken: token, taskId: 't-1');

      expect(paths, [
        '/api/v1/lifemap/tasks/t-1/accept',
        '/api/v1/lifemap/tasks/t-1/complete',
      ]);
    });

    test('each mutation generates a distinct Idempotency-Key', () async {
      final keys = <String>[];
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          final key = request.headers['Idempotency-Key'];
          if (key != null) keys.add(key);
          return ok({'id': 'x'});
        }),
      );

      await client.createLifeMapEpisode(accessToken: token, title: 'A');
      await client.createLifeMapEpisode(accessToken: token, title: 'B');

      expect(keys.length, 2);
      expect(keys.toSet().length, 2, reason: 'keys must be unique per call');
    });

    test('Universal Capture wrappers use draft and idempotent review routes',
        () async {
      final requests = <http.Request>[];
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          requests.add(request);
          return ok({'id': 'capture-1', 'status': 'draft'});
        }),
      );

      await client.startLifeMapTextCapture(
        accessToken: token,
        text: 'Tôi ngủ 7 giờ',
      );
      await client.reviewLifeMapCaptureCandidate(
        accessToken: token,
        candidateId: 'candidate-1',
        action: 'confirm',
        reason: 'reviewed',
      );

      expect(requests[0].url.path, '/api/v1/lifemap/capture/sessions');
      expect(
        jsonDecode(requests[0].body),
        {'text': 'Tôi ngủ 7 giờ', 'locale': 'vi'},
      );
      expect(
        requests[1].url.path,
        '/api/v1/lifemap/capture/candidates/candidate-1/review',
      );
      expect(requests[1].headers['Idempotency-Key'], isNotEmpty);
    });
  });

  group('PHR onboarding wrappers', () {
    test('getPhrOnboarding GETs /api/v1/phr/onboarding', () async {
      late http.Request captured;
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          captured = request;
          return ok({'status': 'pending', 'needs_onboarding': true});
        }),
      );

      final result = await client.getPhrOnboarding(accessToken: token);

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/v1/phr/onboarding');
      expect(result['needs_onboarding'], true);
    });

    test('updatePhrOnboarding PATCHes the action payload', () async {
      late http.Request captured;
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          captured = request;
          return ok({'status': 'completed', 'needs_onboarding': false});
        }),
      );

      await client.updatePhrOnboarding(
        accessToken: token,
        payload: {'action': 'complete', 'full_name': 'Nguyễn An'},
      );

      expect(captured.method, 'PATCH');
      expect(captured.url.path, '/api/v1/phr/onboarding');
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['action'], 'complete');
      expect(body['full_name'], 'Nguyễn An');
    });
  });

  group('Medication-courses wrappers', () {
    test('getMedicationCourses GETs the empty-path collection route', () async {
      late http.Request captured;
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          captured = request;
          return http.Response(jsonEncode([]), 200,
              headers: const {'content-type': 'application/json'});
        }),
      );

      await client.getMedicationCourses(accessToken: token);

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/v1/medication-courses');
    });

    test('createMedicationCourse POSTs with an Idempotency-Key', () async {
      late http.Request captured;
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          captured = request;
          return ok({'id': 'mc-1'});
        }),
      );

      await client.createMedicationCourse(
        accessToken: token,
        medicationName: 'Metformin',
        doseText: '500 mg',
        drugbankId: 'DB00331',
      );

      expect(captured.url.path, '/api/v1/medication-courses');
      expect(captured.headers['Idempotency-Key'], isNotEmpty);
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['medication_name'], 'Metformin');
      expect(body['drugbank_id'], 'DB00331');
    });
  });
}

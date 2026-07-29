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

    test('Replay correction and dispute commands preserve exact revision',
        () async {
      final requests = <http.Request>[];
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          requests.add(request);
          return ok({'events': <dynamic>[]});
        }),
      );

      await client.getLifeMapReplay(
        accessToken: token,
        episodeId: 'episode-1',
      );
      await client.correctLifeMapEvent(
        accessToken: token,
        eventId: 'event-1',
        revision: 2,
        payload: {'text': 'Thông tin đúng'},
        reason: 'Người dùng sửa',
      );
      await client.disputeLifeMapEvent(
        accessToken: token,
        eventId: 'event-1',
        revision: 3,
        reason: 'Nguồn chưa rõ',
      );
      await client.resolveLifeMapEvent(
        accessToken: token,
        eventId: 'event-1',
        revision: 4,
        reason: 'Đã kiểm tra',
      );
      await client.getLifeMapDisputes(accessToken: token);

      expect(requests[0].method, 'GET');
      expect(requests[0].url.path, '/api/v1/episodes/episode-1/replay');
      expect(
        requests[1].url.path,
        '/api/v1/lifemap/events/event-1/correct',
      );
      expect(requests[1].headers['If-Match'], '2');
      expect(requests[1].headers['Idempotency-Key'], isNotEmpty);
      expect(requests[2].url.path, '/api/v1/lifemap/events/event-1/dispute');
      expect(requests[2].headers['If-Match'], '3');
      expect(requests[3].url.path, '/api/v1/lifemap/events/event-1/resolve');
      expect(requests[3].headers['If-Match'], '4');
      expect(requests[4].url.path, '/api/v1/lifemap/v2/disputes');
    });

    test('baseline and governed-question routes stay server authoritative',
        () async {
      final requests = <http.Request>[];
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          requests.add(request);
          return ok({'ask': false});
        }),
      );
      await client.getLifeMapBaselines(accessToken: token);
      await client.getLifeMapNextQuestion(
        accessToken: token,
        episodeId: 'episode-1',
      );
      await client.startLifeMapGuidedAnswer(
        accessToken: token,
        episodeId: 'episode-1',
        questionId: 'question-1',
        answer: {'value': 'Ổn hơn'},
      );
      expect(requests[0].url.path, '/api/v1/lifemap/v2/baselines');
      expect(
        requests[1].url.path,
        '/api/v1/episodes/episode-1/next-question',
      );
      expect(requests[1].url.queryParameters['locale'], 'vi');
      expect(
        requests[2].url.path,
        '/api/v1/lifemap/capture/guided-answers',
      );
    });

    test('Ask LifeMap uses the governed read-only endpoint', () async {
      late http.Request captured;
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          captured = request;
          return ok({'status': 'grounded', 'claims': [], 'evidence': []});
        }),
      );

      await client.askLifeMap(
        accessToken: token,
        query: 'Các ghi nhận gần đây?',
        episodeId: 'episode-1',
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/lifemap/v2/ask');
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['query'], 'Các ghi nhận gần đây?');
      expect(body['episode_id'], 'episode-1');
      expect(body['locale'], 'vi');
    });

    test('review findings use explicit scan and idempotent human action',
        () async {
      final requests = <http.Request>[];
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          requests.add(request);
          return ok({'id': 'finding-1', 'status': 'resolved'});
        }),
      );
      await client.scanLifeMapReviewFindings(accessToken: token);
      await client.actOnLifeMapReviewFinding(
        accessToken: token,
        findingId: 'finding-1',
        action: 'resolved',
        reason: 'Đã kiểm tra nguồn',
      );
      expect(requests[0].url.path, '/api/v1/lifemap/v2/review-findings/scan');
      expect(
        requests[1].url.path,
        '/api/v1/lifemap/v2/review-findings/finding-1/actions',
      );
      expect(requests[1].headers['Idempotency-Key'], isNotEmpty);
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
        routeText: 'Uống',
        formText: 'Viên nén',
        drugbankId: 'DB00331',
      );

      expect(captured.url.path, '/api/v1/medication-courses');
      expect(captured.headers['Idempotency-Key'], isNotEmpty);
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['medication_name'], 'Metformin');
      expect(body['drugbank_id'], 'DB00331');
      expect(body['route_text'], 'Uống');
      expect(body['form_text'], 'Viên nén');
    });

    test('correctMedicationCourse uses optimistic concurrency', () async {
      late http.Request captured;
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          captured = request;
          return ok({'id': 'mc_opaque', 'version': 3});
        }),
      );

      await client.correctMedicationCourse(
        accessToken: token,
        courseId: 'mc_opaque',
        version: 2,
        medicationName: 'Metformin',
        reason: 'Sửa liều đã nhập nhầm',
        doseText: '850 mg',
      );

      expect(captured.method, 'POST');
      expect(
        captured.url.path,
        '/api/v1/medication-courses/mc_opaque/correct',
      );
      expect(captured.headers['If-Match'], '2');
      expect(captured.headers['Idempotency-Key'], isNotEmpty);
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['dose_text'], '850 mg');
      expect(body['reason'], 'Sửa liều đã nhập nhầm');
    });

    test('endMedicationCourse records history without deletion', () async {
      late http.Request captured;
      final client = ApiClient(
        baseUrl: base,
        httpClient: MockClient((request) async {
          captured = request;
          return ok({'id': 'mc_opaque', 'status': 'ended', 'version': 2});
        }),
      );

      await client.endMedicationCourse(
        accessToken: token,
        courseId: 'mc_opaque',
        version: 1,
        reason: 'Người dùng xác nhận kết thúc',
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/medication-courses/mc_opaque/end');
      expect(captured.headers['If-Match'], '1');
      expect(captured.headers['Idempotency-Key'], isNotEmpty);
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['reason'], 'Người dùng xác nhận kết thúc');
      expect(body.containsKey('ended_at'), isFalse);
    });
  });
}

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const base = 'https://api.test';
  const token = 'access-token';

  test('creates, confirms, and runs an opaque evidence question', () async {
    final requests = <http.Request>[];
    final api = ApiClient(
      baseUrl: base,
      httpClient: MockClient((request) async {
        requests.add(request);
        return http.Response(
            jsonEncode(<String, dynamic>{'id': 'opaque-id'}), 200);
      }),
    );

    await api.createEvidenceQuestion(
      accessToken: token,
      episodeId: 'episode-1',
      question: 'Có bằng chứng nào về huyết áp?',
      populationContext: 'Người lớn.',
    );
    await api.confirmEvidenceQuestion(
      accessToken: token,
      questionId: 'question-1',
    );
    await api.runEvidenceQuestion(
      accessToken: token,
      questionId: 'question-1',
    );

    expect(requests[0].method, 'POST');
    expect(
        requests[0].url.path, '/api/v1/episodes/episode-1/evidence-questions');
    expect(jsonDecode(requests[0].body)['confirmed'], isFalse);
    expect(requests[1].method, 'PATCH');
    expect(requests[1].url.path, '/api/v1/evidence-questions/question-1');
    expect(requests[2].headers['Idempotency-Key'], isNotEmpty);
  });

  test('manages monitor interval and revocation', () async {
    final requests = <http.Request>[];
    final api = ApiClient(
      baseUrl: base,
      httpClient: MockClient((request) async {
        requests.add(request);
        return http.Response('{}', 200);
      }),
    );

    await api.subscribeToEvidenceRun(
      accessToken: token,
      runId: 'run-1',
      intervalHours: 168,
    );
    await api.updateEvidenceSubscription(
      accessToken: token,
      subscriptionId: 'sub-1',
      intervalHours: 720,
    );
    await api.revokeEvidenceSubscription(
      accessToken: token,
      subscriptionId: 'sub-1',
    );

    expect(jsonDecode(requests[0].body)['interval_hours'], 168);
    expect(requests[1].method, 'PATCH');
    expect(jsonDecode(requests[1].body)['interval_hours'], 720);
    expect(requests[2].method, 'DELETE');
  });

  test('reads applicability, contradictions, and reviewed notifications',
      () async {
    final paths = <String>[];
    final api = ApiClient(
      baseUrl: base,
      httpClient: MockClient((request) async {
        paths.add(request.url.path);
        return http.Response('[]', 200);
      }),
    );

    await api.getEvidenceApplicability(accessToken: token, runId: 'run-1');
    await api.getEvidenceContradictions(accessToken: token, runId: 'run-1');
    await api.getEvidenceChangeNotifications(accessToken: token);
    await api.readEvidenceChangeNotification(
      accessToken: token,
      notificationId: 'notification-1',
    );

    expect(paths, <String>[
      '/api/v1/evidence-runs/run-1/applicability',
      '/api/v1/evidence-runs/run-1/contradictions',
      '/api/v1/evidence-change-notifications',
      '/api/v1/evidence-change-notifications/notification-1/read',
    ]);
  });
}

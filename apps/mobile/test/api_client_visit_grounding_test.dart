import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const token = 'visit-token';
  const base = 'https://api.test';

  test('preserves opaque visit and document ids for grounded extraction',
      () async {
    late http.Request captured;
    final api = ApiClient(
      baseUrl: base,
      httpClient: MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(<String, dynamic>{
            'id': 'draft_K3',
            'status': 'extraction_unavailable',
            'candidates': <dynamic>[],
            'safe_unavailable': true,
          }),
          202,
        );
      }),
    );

    await api.extractVisitPlan(
      accessToken: token,
      visitId: 'visit_A7',
      documentId: 'document_B9',
    );

    expect(captured.method, 'POST');
    expect(captured.url.path, '/api/v1/visits/visit_A7/plan/extract');
    expect(
      jsonDecode(captured.body),
      <String, dynamic>{'document_id': 'document_B9'},
    );
  });

  test('confirms exact candidate ids with an idempotency key', () async {
    late http.Request captured;
    final api = ApiClient(
      baseUrl: base,
      httpClient: MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(<String, dynamic>{
            'id': 'draft_K3',
            'status': 'confirmed',
            'task_ids': <String>['task_T4'],
          }),
          200,
        );
      }),
    );

    await api.confirmVisitPlan(
      accessToken: token,
      visitId: 'visit_A7',
      draftId: 'draft_K3',
      candidateIds: <String>['candidate_C5'],
    );

    expect(captured.url.path, '/api/v1/visits/visit_A7/plan/confirm');
    expect(captured.headers['Idempotency-Key'], isNotEmpty);
    expect(
      jsonDecode(captured.body),
      <String, dynamic>{
        'draft_id': 'draft_K3',
        'candidate_ids': <String>['candidate_C5'],
      },
    );
  });

  test('creates a Visit Pack from explicit opaque selections', () async {
    late http.Request captured;
    final api = ApiClient(
      baseUrl: base,
      httpClient: MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(<String, dynamic>{
            'id': 'pack_P1',
            'version_no': 1,
            'status': 'draft',
          }),
          201,
        );
      }),
    );
    final selection = <String, dynamic>{
      'concern_ids': <String>['concern_A'],
      'episode_ids': <String>['episode_C'],
      'event_ids': <String>[],
      'medication_course_ids': <String>['medication_B'],
      'instruction_candidate_ids': <String>['instruction_I'],
      'questions': <String>[],
    };

    await api.createVisitPack(
      accessToken: token,
      visitId: 'visit_A7',
      selection: selection,
    );

    expect(captured.url.path, '/api/v1/visits/visit_A7/pack');
    expect(
        jsonDecode(captured.body), <String, dynamic>{'selection': selection});
  });

  test('sends document deletion reason in a DELETE body', () async {
    late http.Request captured;
    final api = ApiClient(
      baseUrl: base,
      httpClient: MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(<String, dynamic>{
            'id': 'document_B9',
            'deleted_at': '2026-07-29T00:00:00Z',
          }),
          200,
        );
      }),
    );

    await api.deleteVisitDocument(
      accessToken: token,
      visitId: 'visit_A7',
      documentId: 'document_B9',
    );

    expect(
      captured.url.path,
      '/api/v1/visits/visit_A7/documents/document_B9',
    );
    expect(
      jsonDecode(captured.body),
      <String, dynamic>{'reason': 'owner_requested_deletion'},
    );
  });
}

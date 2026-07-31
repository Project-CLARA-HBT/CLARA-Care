import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const token = 'family-token';
  const base = 'https://api.test';

  test('creates an invitation with an opaque minimum-scope object id',
      () async {
    late http.Request captured;
    final api = ApiClient(
      baseUrl: base,
      httpClient: MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(<String, dynamic>{
            'id': 'invite_I1',
            'token': 'one-time-secret',
          }),
          201,
        );
      }),
    );
    final payload = <String, dynamic>{
      'recipient_email': 'supporter@example.com',
      'scope': <String, dynamic>{
        'object_type': 'episode',
        'object_id': 'episode_E1',
        'allowed_actions': <String>['view'],
      },
      'purpose': 'care_coordination',
      'expires_at': '2026-08-01T00:00:00Z',
    };

    await api.createFamilyInvitation(
      accessToken: token,
      payload: payload,
    );

    expect(captured.url.path, '/api/v1/family/invitations');
    expect(jsonDecode(captured.body), payload);
  });

  test('acknowledgement re-sends the exact purpose for live authorization',
      () async {
    late http.Request captured;
    final api = ApiClient(
      baseUrl: base,
      httpClient: MockClient((request) async {
        captured = request;
        return http.Response(
            jsonEncode(<String, String>{'status': 'acknowledged'}), 200);
      }),
    );

    await api.acknowledgeFamilyNotification(
      accessToken: token,
      grantId: 'grant_G1',
      taskId: 'task_T1',
      purpose: 'care_coordination',
    );

    expect(
      captured.url.path,
      '/api/v1/family/notifications/grant_G1/task_T1/acknowledge',
    );
    expect(
      jsonDecode(captured.body),
      <String, dynamic>{'purpose': 'care_coordination'},
    );
  });

  test(
      'renewal creates a fresh invitation instead of silently extending a grant',
      () async {
    late http.Request captured;
    final api = ApiClient(
      baseUrl: base,
      httpClient: MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(<String, dynamic>{
            'id': 'invite_I2',
            'token': 'fresh-secret',
            'requires_recipient_acceptance': true,
          }),
          201,
        );
      }),
    );

    await api.renewFamilyAccessGrant(
      accessToken: token,
      grantId: 'grant_G1',
      expiresAt: DateTime.utc(2026, 8, 20),
    );

    expect(
      captured.url.path,
      '/api/v1/family/access-grants/grant_G1/renewals',
    );
    expect(
      jsonDecode(captured.body),
      <String, dynamic>{'expires_at': '2026-08-20T00:00:00.000Z'},
    );
  });

  test('previews an invitation through a header without accepting it',
      () async {
    late http.Request captured;
    final api = ApiClient(
      baseUrl: base,
      httpClient: MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(<String, dynamic>{
            'object_type': 'visit',
            'allowed_actions': <String>['view'],
            'purpose': 'visit_support',
            'expires_at': '2026-08-01T00:00:00Z',
          }),
          200,
        );
      }),
    );

    await api.previewFamilyInvitation(
      accessToken: token,
      invitationToken: 'preview-only-secret',
    );

    expect(captured.url.path, '/api/v1/family/invitations/preview');
    expect(captured.url.query, isEmpty);
    expect(
        captured.headers['x-family-invitation-token'], 'preview-only-secret');
    expect(jsonDecode(captured.body), <String, dynamic>{});
  });
}

// Feature: clara-mobile-feature-parity — Tasks 6.2, 6.3, 6.4 (Req 4.4, 4.5,
// 4.6, 4.7).
//
// Widget tests for the ambient-scribe screen that pin its load-bearing safety
// invariants:
//   * Flag gate (Req 4.7): with `scribe_mobile_enabled` off the screen is inert
//     (placeholder, no network calls).
//   * RBAC gate (Req 4.6): a non-doctor role sees an unauthorized placeholder
//     and triggers no calls.
//   * Consent gate (Req 4.4, task 6.3): audio processing / transcription is
//     BLOCKED until consent is captured — `transcribeScribeAudio` is never
//     called without consent, and capturing it unlocks processing.
//   * Sanitization (Req 4.5): backend-derived clinical text (transcript + SOAP)
//     is passed through the telemetry-label stripper before display, and no
//     clinical free text reaches analytics.
//
// A `MockClient` (package:http/testing) backs a real [ApiClient] so the screen
// drives genuine request/response plumbing without a live server or platform
// channels (Req 14.6). A recording analytics transport asserts no clinical text
// is transmitted.

import 'dart:convert';

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/screens/scribe_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

import 'fakes/fakes.dart';

MobileFeatureFlagResolver _resolver({required bool enabled}) {
  return MobileFeatureFlagResolver(
    summary: <String, dynamic>{
      'feature_flags': <String, dynamic>{
        MobileFeatureFlags.scribeMobileEnabled: enabled,
      },
    },
  );
}

http.Response _json(Object body, [int status = 200]) => http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json'},
    );

void main() {
  Future<PersistentSessionStore> buildSession({String role = 'doctor'}) {
    return FakeSessionStore.authenticated(
      role: role,
      storage: InMemorySessionSecureStorage(),
    );
  }

  Analytics consentedAnalytics(RecordingAnalyticsTransport transport) {
    final analytics = Analytics(transport: transport);
    analytics.init(
      const AnalyticsConfig(provider: 'test', apiKey: 'k'),
      consentGranted: true,
    );
    return analytics;
  }

  testWidgets('flag off renders an inert placeholder and makes no calls',
      (tester) async {
    var calls = 0;
    final mock = MockClient((request) async {
      calls++;
      return _json({'detail': 'unexpected'}, 404);
    });
    final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mock);
    final session = await buildSession();

    await tester.pumpWidget(MaterialApp(
      home: ScribeScreen(
        apiClient: apiClient,
        sessionStore: session,
        featureFlags: _resolver(enabled: false),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Tính năng ghi chú lâm sàng chưa được bật.'),
        findsOneWidget);
    expect(calls, 0);
  });

  testWidgets('non-doctor role is unauthorized and makes no calls',
      (tester) async {
    var calls = 0;
    final mock = MockClient((request) async {
      calls++;
      return _json({'detail': 'unexpected'}, 404);
    });
    final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mock);
    final session = await buildSession(role: 'normal');

    await tester.pumpWidget(MaterialApp(
      home: ScribeScreen(
        apiClient: apiClient,
        sessionStore: session,
        featureFlags: _resolver(enabled: true),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Tài khoản của bạn không có quyền sử dụng tính năng này.'),
        findsOneWidget);
    expect(calls, 0);
  });

  testWidgets(
      'audio processing is blocked without consent and unlocked after capture',
      (tester) async {
    var transcribeCalls = 0;
    var consentCalls = 0;
    final mock = MockClient((request) async {
      final path = request.url.path;
      final method = request.method;
      if (path.endsWith('/scribe/sessions') && method == 'GET') {
        return _json({
          'items': [
            {
              'id': 1,
              'title': 'Ca khám A',
              'status': 'draft',
              'transcript': '',
            },
          ],
          'total': 1,
        });
      }
      if (path.endsWith('/scribe/sessions/1') && method == 'GET') {
        return _json({
          'id': 1,
          'title': 'Ca khám A',
          'status': 'draft',
          'transcript': '',
        });
      }
      if (path.endsWith('/scribe/sessions/1/consent') && method == 'POST') {
        consentCalls++;
        return _json({'session_id': 1, 'consent_id': 9, 'captured': true});
      }
      if (path.endsWith('/scribe/transcribe') && method == 'POST') {
        transcribeCalls++;
        return _json({'text': 'bệnh nhân ho khan', 'language': 'vi'});
      }
      return _json({'detail': 'unexpected'}, 404);
    });

    final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mock);
    final session = await buildSession();

    await tester.pumpWidget(MaterialApp(
      home: ScribeScreen(
        apiClient: apiClient,
        sessionStore: session,
        featureFlags: _resolver(enabled: true),
        // Provide audio bytes so the upload affordance is rendered.
        audioProvider: () async =>
            ScribeAudioClip(bytes: utf8.encode('fake-audio'), filename: 'a.webm'),
      ),
    ));
    await tester.pumpAndSettle();

    // Open the session.
    await tester.tap(find.text('Ca khám A'));
    await tester.pumpAndSettle();

    // The consent gate is shown and processing is blocked.
    expect(find.byKey(const Key('scribe-consent-gate')), findsOneWidget);
    expect(find.text('Thu thập sự đồng ý'), findsOneWidget);

    // Attempt to upload/process audio WITHOUT consent → blocked, no call.
    await tester.tap(find.byKey(const Key('scribe-upload-audio')));
    await tester.pumpAndSettle();
    expect(transcribeCalls, 0,
        reason: 'audio must not be processed before consent (Req 4.4)');
    expect(
      find.textContaining('Cần thu thập sự đồng ý'),
      findsOneWidget,
    );

    // Capture consent.
    await tester.tap(find.widgetWithText(FilledButton, 'Thu thập sự đồng ý'));
    await tester.pumpAndSettle();
    expect(consentCalls, 1);

    // Now processing is unlocked: uploading audio reaches the endpoint.
    await tester.tap(find.byKey(const Key('scribe-upload-audio')));
    await tester.pumpAndSettle();
    expect(transcribeCalls, 1,
        reason: 'audio processing is allowed once consent is captured');
  });

  testWidgets('clinical transcript + SOAP are sanitized and absent from analytics',
      (tester) async {
    final transport = RecordingAnalyticsTransport();
    final analytics = consentedAnalytics(transport);

    // Backend clinical text deliberately contains internal telemetry labels
    // that must be stripped before display (Req 4.5).
    const dirtyTranscript = 'bệnh nhân ho RAG mode khan';
    const dirtyAssessment = 'viêm họng cấp retrieval';

    final mock = MockClient((request) async {
      final path = request.url.path;
      if (path.endsWith('/scribe/sessions') && request.method == 'GET') {
        return _json({
          'items': [
            {
              'id': 2,
              'title': 'Ca khám B',
              'status': 'ready',
              'transcript': dirtyTranscript,
            },
          ],
          'total': 1,
        });
      }
      if (path.endsWith('/scribe/sessions/2') && request.method == 'GET') {
        return _json({
          'id': 2,
          'title': 'Ca khám B',
          'status': 'ready',
          'transcript': dirtyTranscript,
          'soap': {
            'subjective': dirtyTranscript,
            'assessment': dirtyAssessment,
          },
        });
      }
      return _json({'detail': 'unexpected'}, 404);
    });

    final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mock);
    final session = await buildSession();

    await tester.pumpWidget(MaterialApp(
      home: ScribeScreen(
        apiClient: apiClient,
        sessionStore: session,
        featureFlags: _resolver(enabled: true),
        analytics: analytics,
      ),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Ca khám B'));
    await tester.pumpAndSettle();

    // The internal labels are stripped from the displayed clinical text.
    final transcriptWidget =
        tester.widget<Text>(find.byKey(const Key('scribe-transcript')));
    expect(transcriptWidget.data, isNot(contains('RAG mode')));
    expect(transcriptWidget.data, contains('bệnh nhân ho'));
    expect(find.textContaining('RAG mode'), findsNothing);
    expect(find.textContaining('retrieval'), findsNothing);
    // The genuine assessment content (minus the label) is still rendered.
    expect(find.textContaining('viêm họng cấp'), findsOneWidget);

    // No clinical free text reached analytics: every captured event carries
    // only coarse, non-PII props (Req 4.5, 11.5).
    final serialized = transport.captured
        .map((e) => '${e.name} ${jsonEncode(e.props)}')
        .join('\n');
    expect(serialized, isNot(contains('bệnh nhân')));
    expect(serialized, isNot(contains('viêm họng')));
    expect(serialized, isNot(contains('ho khan')));
    // The screen-view event was recorded (analytics is wired, transmissions
    // happen) — proving the absence above is meaningful, not just a no-op.
    expect(transport.capturedNames, contains('mobile_scribe_viewed'));
  });
}

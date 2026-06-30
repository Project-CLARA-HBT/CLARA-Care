// Widget tests for ChatScreen — clara-mobile-feature-parity Task 3.2
// (Requirements 1.1–1.6; design Property P5).
//
// Coverage:
//   * Progressive streaming render (Req 1.2): token frames from
//     `POST /chat/stream` accumulate into the assistant bubble; the standing
//     medical disclaimer (Req 1.4) is always present.
//   * Emergency fast-path (Req 1.5): when a terminal `done` envelope flags
//     `emergency: true`, the prominent emergency banner is surfaced; the
//     always-present emergency action opens directive-only guidance.
//   * Streaming error fallback (Req 1.3): a stream that fails before any token
//     falls back to the blocking `POST /chat` endpoint, preserving the flow.
//   * No-PII analytics (Req 11.2/11.5; Property P5): the typed message text is
//     NEVER transmitted to analytics from any chat interaction.
//   * Flag gating (Req 1.7): with `chat_mobile_enabled` off the surface is
//     disabled and `ChatScreen.maybe` returns null.
//
// A `MockClient` / `MockClient.streaming` (package:http/testing) backs a real
// [ApiClient] so the screen drives genuine request/response + SSE plumbing
// without a live server or platform channels (Requirement 14.6).

import 'dart:async';
import 'dart:convert';

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/screens/chat_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

import 'fakes/fakes.dart';

http.StreamedResponse _sseResponse(
  http.BaseRequest request,
  List<String> chunks, {
  int statusCode = 200,
}) {
  final controller = StreamController<List<int>>();
  for (final chunk in chunks) {
    controller.add(utf8.encode(chunk));
  }
  controller.close();
  return http.StreamedResponse(
    controller.stream,
    statusCode,
    request: request,
    headers: const {'content-type': 'text/event-stream'},
  );
}

MobileFeatureFlagResolver _enabledResolver() => MobileFeatureFlagResolver(
      summary: const {
        'feature_flags': {'chat_mobile_enabled': true},
      },
    );

Future<SessionStore> _session() => FakeSessionStore.authenticated(role: 'normal');

void main() {
  testWidgets(
      'streams tokens progressively and shows the standing disclaimer + emergency banner',
      (tester) async {
    final mock = MockClient.streaming((request, bodyStream) async {
      expect(request.url.path, '/api/v1/chat/stream');
      return _sseResponse(request, [
        'event: start\ndata: {}\n\n',
        'event: token\ndata: {"text":"Chào "}\n\n',
        'event: token\ndata: {"text":"bạn"}\n\n',
        'event: done\ndata: {"reply":"Chào bạn","role":"normal","emergency":true,"fallback":false}\n\n',
      ]);
    });
    final api = ApiClient(baseUrl: 'https://api.test', httpClient: mock);
    final session = await _session();

    await tester.pumpWidget(MaterialApp(
      home: ChatScreen(
        apiClient: api,
        sessionStore: session,
        resolver: _enabledResolver(),
      ),
    ));
    await tester.pumpAndSettle();

    // Standing disclaimer is present before any interaction (Req 1.4).
    expect(find.byKey(const Key('chat-standing-disclaimer')), findsOneWidget);

    // Type and send a message.
    await tester.enterText(find.byKey(const Key('chat-input')), 'xin chao');
    await tester.tap(find.byKey(const Key('chat-send')));
    await tester.pumpAndSettle();

    // Progressive tokens accumulated into the answer (Req 1.2) and rendered via
    // the End_User-safe answer view on completion (Req 1.6).
    expect(find.text('Chào bạn'), findsWidgets);

    // Emergency envelope surfaced the prominent banner (Req 1.5).
    expect(find.byKey(const Key('chat-emergency-banner')), findsOneWidget);
  });

  testWidgets('emergency fast-path action opens directive-only guidance',
      (tester) async {
    final mock = MockClient((request) async =>
        http.Response('{"detail":"unused"}', 404,
            headers: {'content-type': 'application/json'}));
    final api = ApiClient(baseUrl: 'https://api.test', httpClient: mock);
    final session = await _session();

    await tester.pumpWidget(MaterialApp(
      home: ChatScreen(
        apiClient: api,
        sessionStore: session,
        resolver: _enabledResolver(),
      ),
    ));
    await tester.pumpAndSettle();

    // The emergency affordance is always present (Req 1.5).
    await tester.tap(find.byKey(const Key('chat-emergency-action')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('chat-emergency-dialog')), findsOneWidget);
    expect(find.textContaining('115'), findsOneWidget);
  });

  testWidgets('falls back to the blocking chat endpoint when the stream errors',
      (tester) async {
    var blockingCalled = false;
    // Streaming endpoint returns an HTTP error before any token; blocking
    // endpoint then serves the answer (Req 1.3).
    final mock = MockClient.streaming((request, bodyStream) async {
      final path = request.url.path;
      if (path == '/api/v1/chat/stream') {
        return _sseResponse(request, ['{"detail":"stream down"}'],
            statusCode: 503);
      }
      if (path == '/api/v1/chat') {
        blockingCalled = true;
        return http.StreamedResponse(
          Stream.value(utf8.encode(jsonEncode({
            'reply': 'Câu trả lời dự phòng',
            'role': 'normal',
            'fallback': true,
          }))),
          200,
          request: request,
          headers: const {'content-type': 'application/json'},
        );
      }
      return http.StreamedResponse(
          Stream.value(utf8.encode('{"detail":"nope"}')), 404,
          request: request);
    });
    final api = ApiClient(baseUrl: 'https://api.test', httpClient: mock);
    final session = await _session();

    await tester.pumpWidget(MaterialApp(
      home: ChatScreen(
        apiClient: api,
        sessionStore: session,
        resolver: _enabledResolver(),
      ),
    ));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('chat-input')), 'xin chao');
    await tester.tap(find.byKey(const Key('chat-send')));
    await tester.pumpAndSettle();

    expect(blockingCalled, isTrue);
    expect(find.text('Câu trả lời dự phòng'), findsWidgets);
  });

  testWidgets('never transmits the message text to analytics (Property P5)',
      (tester) async {
    const secret = 'tôi bị đau ngực dữ dội ibuprofen';
    final recording = RecordingAnalyticsTransport();
    final analytics = Analytics(transport: recording);
    // Configured + consented, so transmissions are actually attempted.
    analytics.init(
      const AnalyticsConfig(provider: 'posthog', apiKey: 'k'),
      consentGranted: true,
    );

    final mock = MockClient.streaming((request, bodyStream) async {
      return _sseResponse(request, [
        'event: token\ndata: {"text":"ok"}\n\n',
        'event: done\ndata: {"reply":"ok","role":"normal","emergency":false}\n\n',
      ]);
    });
    final api = ApiClient(baseUrl: 'https://api.test', httpClient: mock);
    final session = await _session();

    await tester.pumpWidget(MaterialApp(
      home: ChatScreen(
        apiClient: api,
        sessionStore: session,
        resolver: _enabledResolver(),
        analytics: analytics,
      ),
    ));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('chat-input')), secret);
    await tester.tap(find.byKey(const Key('chat-send')));
    await tester.pumpAndSettle();

    // Events were emitted, but none carries the message text or its fragments.
    expect(recording.captured, isNotEmpty);
    final serialized = recording.captured
        .map((e) => '${e.name} ${jsonEncode(e.props)}')
        .join('\n');
    expect(serialized.contains(secret), isFalse);
    expect(serialized.toLowerCase().contains('ibuprofen'), isFalse);
    expect(serialized.toLowerCase().contains('đau ngực'), isFalse);
  });

  testWidgets('flag off disables the surface and ChatScreen.maybe returns null',
      (tester) async {
    final offResolver = MobileFeatureFlagResolver(
      summary: const {'feature_flags': <String, dynamic>{}},
    );
    final api = FakeApiClient();
    final session = await _session();

    expect(
      ChatScreen.maybe(
        apiClient: api,
        sessionStore: session,
        resolver: offResolver,
      ),
      isNull,
    );

    await tester.pumpWidget(MaterialApp(
      home: ChatScreen(
        apiClient: api,
        sessionStore: session,
        resolver: offResolver,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('chat-disabled')), findsOneWidget);
    expect(find.byKey(const Key('chat-input')), findsNothing);
  });
}

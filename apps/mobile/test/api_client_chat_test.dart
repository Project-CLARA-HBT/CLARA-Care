// Unit tests for the additive chat client methods added to [ApiClient] in
// task 3.1 of the clara-mobile-feature-parity spec.
//
// Covers:
//   * `chat` (blocking) -> POST /api/v1/chat with `{message: ...}`, returning
//     the ChatResponse envelope (Req 1.1).
//   * `streamChat` (SSE) -> POST /api/v1/chat/stream, parsing the server's
//     `start`/`step`/`token`/`done` frames via the shared SSE parser reused
//     from `streamResearchJob` (Req 1.2). Concatenating `token` frames yields
//     the full answer; a terminal `done` frame carries the final envelope.
//   * A terminal `error` frame is surfaced as an [SseEvent] so the caller can
//     fall back to the blocking endpoint and preserve streamed content (Req 1.3).
//   * Back-compat: the existing `streamResearchJob` still parses correctly
//     after being refactored onto the shared parser.
//
// A `MockClient` (and `MockClient.streaming`) backs a real [ApiClient] so the
// request method/path/headers/body and the SSE parsing are exercised without a
// live server or platform channels.

import 'dart:async';
import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

/// Wraps a list of raw SSE byte chunks as a streamed response body.
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

void main() {
  const token = 'test-token';
  const base = 'https://api.test';

  group('chat (blocking)', () {
    test('POSTs message to /api/v1/chat and returns the envelope', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request as http.Request;
        return http.Response(
          jsonEncode({
            'message': 'xin chao',
            'reply': 'Chào bạn, CLARA đang sẵn sàng.',
            'role': 'normal',
            'intent': 'general_guidance',
            'confidence': 0.9,
            'emergency': false,
            'model_used': 'api-safe-smalltalk-v1',
            'retrieved_ids': [],
            'fallback': false,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.chat(
        accessToken: token,
        payload: {'message': 'xin chao'},
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/chat');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(jsonDecode(captured.body)['message'], 'xin chao');
      expect(result['reply'], 'Chào bạn, CLARA đang sẵn sàng.');
      expect(result['role'], 'normal');
      expect(result['fallback'], isFalse);
    });

    test('surfaces server error detail as ApiException', () async {
      final mock = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'deepseek_required_unavailable'}),
          503,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      expect(
        () => api.chat(accessToken: token, payload: {'message': 'hi'}),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 503)
              .having((e) => e.message, 'message',
                  'deepseek_required_unavailable'),
        ),
      );
    });
  });

  group('streamChat (SSE)', () {
    test('POSTs to /chat/stream and parses start/step/token/done frames',
        () async {
      late http.BaseRequest captured;
      final mock = MockClient.streaming((request, bodyStream) async {
        captured = request;
        return _sseResponse(request, [
          'event: start\ndata: {}\n\n',
          'event: step\ndata: {"index":0,"stage":"retrieval","status":"running"}\n\n',
          'event: token\ndata: {"text":"Chào "}\n\n',
          'event: token\ndata: {"text":"bạn"}\n\n',
          'event: done\ndata: {"reply":"Chào bạn","role":"normal","fallback":false}\n\n',
        ]);
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final events = await api
          .streamChat(accessToken: token, payload: {'message': 'xin chao'})
          .toList();

      // Request shape.
      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/chat/stream');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(captured.headers['Accept'], 'text/event-stream');

      // Frame sequence.
      expect(events.map((e) => e.event).toList(),
          ['start', 'step', 'token', 'token', 'done']);

      // Concatenating token frames yields the streamed answer.
      final answer = events
          .where((e) => e.event == 'token')
          .map((e) => e.json?['text'] as String? ?? '')
          .join();
      expect(answer, 'Chào bạn');

      // Terminal done frame carries the final envelope.
      final done = events.firstWhere((e) => e.event == 'done');
      expect(done.json?['reply'], 'Chào bạn');
      expect(done.json?['role'], 'normal');
    });

    test('terminal error frame is surfaced as an SseEvent (not thrown)',
        () async {
      final mock = MockClient.streaming((request, bodyStream) async {
        return _sseResponse(request, [
          'event: token\ndata: {"text":"partial"}\n\n',
          'event: error\ndata: {"message":"chat stream proxy failed"}\n\n',
        ]);
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final events = await api
          .streamChat(accessToken: token, payload: {'message': 'hi'})
          .toList();

      expect(events.map((e) => e.event).toList(), ['token', 'error']);
      // Already-streamed content is preserved up to the error (Req 1.3).
      expect(events.first.json?['text'], 'partial');
      final error = events.last;
      expect(error.json?['message'], 'chat stream proxy failed');
    });

    test('handles frames split across chunk boundaries', () async {
      final mock = MockClient.streaming((request, bodyStream) async {
        return _sseResponse(request, [
          'event: tok',
          'en\ndata: {"text":"hel',
          'lo"}\n\n',
          'event: done\ndata: {"reply":"hello"}\n\n',
        ]);
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final events = await api
          .streamChat(accessToken: token, payload: {'message': 'hi'})
          .toList();

      expect(events.map((e) => e.event).toList(), ['token', 'done']);
      expect(events.first.json?['text'], 'hello');
    });

    test('an HTTP error before the stream surfaces as ApiException', () async {
      final mock = MockClient.streaming((request, bodyStream) async {
        return _sseResponse(
          request,
          ['{"detail":"unauthorized"}'],
          statusCode: 401,
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      expect(
        () => api
            .streamChat(accessToken: token, payload: {'message': 'hi'})
            .toList(),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 401)
              .having((e) => e.message, 'message', 'unauthorized'),
        ),
      );
    });
  });

  group('streamResearchJob (shared parser regression)', () {
    test('still parses GET SSE frames after the parser refactor', () async {
      late http.BaseRequest captured;
      final mock = MockClient.streaming((request, bodyStream) async {
        captured = request;
        return _sseResponse(request, [
          'event: progress\ndata: {"stage":"plan","status":"running"}\n\n',
          'event: completed\ndata: {"status":"completed"}\n\n',
        ]);
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final events = await api
          .streamResearchJob(accessToken: token, jobId: 'job-1')
          .toList();

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/v1/research/tier2/jobs/job-1/stream');
      expect(events.map((e) => e.event).toList(), ['progress', 'completed']);
      expect(events.last.json?['status'], 'completed');
    });
  });
}

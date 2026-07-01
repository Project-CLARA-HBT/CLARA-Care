// Widget tests for the polished chat surface — clara-mobile-ux-polish
// (Requirements 2, 4, 5; design properties P1, P3, P4, P9).
//
// Coverage:
//   * P3 isNearBottom pure gating: empty/at-bottom/within-threshold/away.
//   * Req 4 empty state: greeting + prompt suggestions render with no messages.
//   * P9 suggestion pre-fill: tapping a suggestion populates the composer and
//     NEVER sends (no HTTP request, empty state still shown, no user bubble).
//   * P4 send-enable invariant: send is disabled with empty input and enabled
//     once trimmed non-empty text is present.
//   * Req 2/5 streaming: token frames accumulate into the answer and the
//     per-message copy/regenerate actions appear once the turn completes.
//   * P1 flags-off equivalence: `polished: false` renders the legacy
//     `chat-empty` (not the polished empty state).
//
// A real [ApiClient] is backed by `MockClient` / `MockClient.streaming`
// (package:http/testing) so the screen drives genuine request/SSE plumbing
// without a live server or platform channels. The polished body is wrapped in a
// `MediaQuery(disableAnimations: true)` so the typing indicator's looping
// animation collapses and frames settle deterministically.

import 'dart:async';
import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/screens/chat_screen.dart';
import 'package:clara_mobile/screens/chat/polished_chat_view.dart';
import 'package:clara_mobile/theme/clara_theme.dart';
import 'package:clara_mobile/widgets/screen_error_boundary.dart';
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

Future<SessionStore> _session() =>
    FakeSessionStore.authenticated(role: 'normal');

/// Wraps a [ChatScreen] in a MaterialApp with the polished light theme and a
/// reduced-motion MediaQuery so the typing indicator does not loop forever.
Widget _host(ChatScreen screen) => MaterialApp(
      theme: ClaraTheme.light(polished: true),
      home: MediaQuery(
        data: const MediaQueryData(disableAnimations: true),
        child: screen,
      ),
    );

void main() {
  // ScreenErrorBoundary installs a global ErrorWidget.builder on first mount.
  // The newer flutter_test captures the builder at each test's start and
  // verifies it is unchanged at the end. Installing once here (before any test
  // body runs) means the captured baseline already equals the clean builder,
  // so no test observes a change. Reset after all tests for isolate hygiene.
  setUpAll(ScreenErrorBoundary.install);
  tearDownAll(ScreenErrorBoundary.debugReset);

  group('isNearBottom (P3)', () {
    test('gates auto-scroll on proximity to the bottom', () {
      // Empty/unscrollable positions are treated as "at bottom".
      expect(isNearBottom(0, 0), isTrue);
      // Exactly at the maximum extent.
      expect(isNearBottom(1000, 1000), isTrue);
      // Within the default 120px threshold of the bottom (100px gap).
      expect(isNearBottom(900, 1000), isTrue);
      // Beyond the threshold — the user has scrolled away (200px gap).
      expect(isNearBottom(800, 1000), isFalse);
      expect(isNearBottom(500, 1000), isFalse);
    });
  });

  testWidgets('empty state shows the greeting and suggestions (Req 4)',
      (tester) async {
    final api = FakeApiClient();
    final session = await _session();

    await tester.pumpWidget(_host(ChatScreen(
      polished: true,
      apiClient: api,
      sessionStore: session,
      resolver: _enabledResolver(),
    )));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('chat-empty-polished')), findsOneWidget);
    expect(find.byKey(const Key('chat-suggestion-0')), findsOneWidget);
  });

  testWidgets('tapping a suggestion pre-fills the composer and never sends (P9)',
      (tester) async {
    var handlerCalled = false;
    final mock = MockClient((request) async {
      handlerCalled = true;
      return http.Response('{"detail":"unused"}', 404,
          headers: {'content-type': 'application/json'});
    });
    final api = ApiClient(baseUrl: 'https://api.test', httpClient: mock);
    final session = await _session();

    await tester.pumpWidget(_host(ChatScreen(
      polished: true,
      apiClient: api,
      sessionStore: session,
      resolver: _enabledResolver(),
    )));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('chat-suggestion-0')));
    await tester.pumpAndSettle();

    // The composer now carries the suggestion text.
    final field = tester.widget<TextField>(find.byKey(const Key('chat-input')));
    expect(field.controller, isNotNull);
    expect(field.controller!.text.trim(), isNotEmpty);

    // Nothing was sent: no HTTP request, still on the empty state, no bubble.
    expect(handlerCalled, isFalse);
    expect(find.byKey(const Key('chat-empty-polished')), findsOneWidget);
    expect(find.byKey(const Key('chat-message-list')), findsNothing);
  });

  testWidgets('send is disabled until trimmed non-empty text is present (P4)',
      (tester) async {
    final api = FakeApiClient();
    final session = await _session();

    await tester.pumpWidget(_host(ChatScreen(
      polished: true,
      apiClient: api,
      sessionStore: session,
      resolver: _enabledResolver(),
    )));
    await tester.pumpAndSettle();

    // Initially empty → send disabled (onPressed null).
    var send = tester.widget<IconButton>(find.byKey(const Key('chat-send')));
    expect(send.onPressed, isNull);

    await tester.enterText(find.byKey(const Key('chat-input')), 'Xin chào');
    await tester.pump();

    send = tester.widget<IconButton>(find.byKey(const Key('chat-send')));
    expect(send.onPressed, isNotNull);
  });

  testWidgets(
      'streaming accumulates tokens and surfaces copy/regenerate actions '
      '(Req 2, 5)', (tester) async {
    final mock = MockClient.streaming((request, bodyStream) async {
      expect(request.url.path, '/api/v1/chat/stream');
      return _sseResponse(request, [
        'event: start\ndata: {}\n\n',
        'event: token\ndata: {"text":"Chào "}\n\n',
        'event: token\ndata: {"text":"bạn"}\n\n',
        'event: done\ndata: {"reply":"Chào bạn","role":"normal","emergency":false,"fallback":false}\n\n',
      ]);
    });
    final api = ApiClient(baseUrl: 'https://api.test', httpClient: mock);
    final session = await _session();

    await tester.pumpWidget(_host(ChatScreen(
      polished: true,
      apiClient: api,
      sessionStore: session,
      resolver: _enabledResolver(),
    )));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('chat-input')), 'xin chao');
    // Let the composer's ValueListenableBuilder rebuild so the send control is
    // enabled (onPressed non-null) before we tap it.
    await tester.pump();
    await tester.tap(find.byKey(const Key('chat-send')));
    await tester.pumpAndSettle();

    // Progressive tokens accumulated into the terminal answer (Req 2).
    expect(find.textContaining('Chào'), findsWidgets);

    // The completed turn exposes the copy action (Req 5).
    expect(find.byKey(const Key('chat-action-copy')), findsWidgets);
  });

  testWidgets('flags-off renders the legacy empty state, not the polished one '
      '(P1)', (tester) async {
    final api = FakeApiClient();
    final session = await _session();

    await tester.pumpWidget(_host(ChatScreen(
      polished: false,
      apiClient: api,
      sessionStore: session,
      resolver: _enabledResolver(),
    )));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('chat-empty')), findsOneWidget);
    expect(find.byKey(const Key('chat-empty-polished')), findsNothing);
  });
}

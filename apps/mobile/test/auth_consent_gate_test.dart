// Feature: clara-mobile-feature-parity — Task 8.3 (Req 6.6; Properties P8, P9).
//
// Widget tests for the auth-lifecycle + consent gate work of task 8.2:
//   (a) An expired stored session is cleared on launch and the app routes to
//       the login screen (Property P9 / Req 6.2, 6.3).
//   (b) The consent gate blocks gated medical content (the dashboard) until the
//       backend consent is accepted, then reveals it (Req 6.6).
//
// The reusable fakes (task 1.1) back the REAL `ClaraApp` shell, real
// `PersistentSessionStore`, and the real `ConsentGate`, so the tests exercise
// genuine routing/gating behavior without a live server or platform channels
// (Requirement 14.6).

import 'dart:convert';

import 'package:clara_mobile/app.dart';
import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/widgets/consent_gate.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fakes.dart';

/// Builds a minimal unsigned JWT whose `exp` claim is [secondsFromNow] from
/// now. The session store only parses the payload's `exp`, so the signature is
/// irrelevant. Padding is stripped because the store normalizes it back.
String _jwt({required int secondsFromNow}) {
  final exp = DateTime.now().toUtc().add(Duration(seconds: secondsFromNow));
  String seg(Map<String, dynamic> m) =>
      base64Url.encode(utf8.encode(jsonEncode(m))).replaceAll('=', '');
  final header = seg({'alg': 'HS256', 'typ': 'JWT'});
  final payload = seg({
    'sub': 'user@example.com',
    'exp': exp.millisecondsSinceEpoch ~/ 1000,
  });
  return '$header.$payload.signature';
}

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  testWidgets('expired stored session is cleared and routes to login',
      (tester) async {
    // Seed secure storage with a session whose access token is already expired.
    final storage = InMemorySessionSecureStorage({
      PersistentSessionStore.emailKey: 'user@example.com',
      PersistentSessionStore.accessTokenKey: _jwt(secondsFromNow: -60),
      PersistentSessionStore.refreshTokenKey: 'refresh-token',
      PersistentSessionStore.roleKey: 'normal',
    });
    final session = PersistentSessionStore(storage: storage);
    final api = FakeApiClient();

    await tester.pumpWidget(
      ClaraApp(apiClient: api, sessionStore: session),
    );
    await tester.pumpAndSettle();

    // The expired session was cleared on hydrate (Req 6.3) and the app shows
    // the login screen — never the gated dashboard.
    expect(session.isAuthenticated, isFalse);
    expect(find.widgetWithText(FilledButton, 'Đăng nhập'), findsOneWidget);
    expect(find.text('Công cụ'), findsNothing);
    // Credentials were wiped from secure storage (Req 6.3 / 6.5).
    expect(storage.isEmpty, isTrue);
    // The consent status was never consulted because we never authenticated.
    expect(api.wasCalled('getConsentStatus'), isFalse);
  });

  testWidgets(
      'consent gate blocks the dashboard until backend consent is accepted',
      (tester) async {
    // A valid (unexpired) session so hydrate restores the authenticated branch.
    final storage = InMemorySessionSecureStorage({
      PersistentSessionStore.emailKey: 'user@example.com',
      PersistentSessionStore.accessTokenKey: _jwt(secondsFromNow: 3600),
      PersistentSessionStore.refreshTokenKey: 'refresh-token',
      PersistentSessionStore.roleKey: 'normal',
    });
    final session = PersistentSessionStore(storage: storage);

    final api = FakeApiClient();
    // Backend reports consent NOT yet accepted for the required version.
    api.stub('getConsentStatus', response: const {
      'consent_type': 'medical_disclaimer',
      'required_version': '2026-04-v1',
      'accepted': false,
    });
    // Dashboard data, fetched only once the gate reveals the dashboard.
    api.stub('getMobileSummary', response: const {
      'feature_flags': {'research': true},
    });
    api.stub('acceptConsent', response: const {'accepted': true});

    await tester.pumpWidget(
      ClaraApp(apiClient: api, sessionStore: session),
    );
    await tester.pumpAndSettle();

    // Gated content is blocked: the dashboard ("Công cụ") is NOT shown and the
    // consent acceptance step is presented instead (Req 6.6).
    expect(find.text('Công cụ'), findsNothing);
    expect(find.widgetWithText(FilledButton, 'Tôi đồng ý'), findsOneWidget);
    // The gate must not have rendered the dashboard, so its summary load has
    // not run yet.
    expect(api.wasCalled('getMobileSummary'), isFalse);

    // Accept consent: the gate records acceptance for the required version and
    // then reveals the gated dashboard.
    await tester.tap(find.widgetWithText(FilledButton, 'Tôi đồng ý'));
    await tester.pumpAndSettle();

    final acceptCall = api.callsTo('acceptConsent').single;
    expect(acceptCall.args['consentVersion'], '2026-04-v1');

    // Now the gated content is reachable.
    expect(find.widgetWithText(FilledButton, 'Tôi đồng ý'), findsNothing);
    expect(find.text('Công cụ'), findsOneWidget);
    expect(api.wasCalled('getMobileSummary'), isTrue);
  });

  testWidgets('consent gate renders child directly when already accepted',
      (tester) async {
    final api = FakeApiClient();
    api.stub('getConsentStatus', response: const {
      'required_version': '2026-04-v1',
      'accepted': true,
    });

    await tester.pumpWidget(
      MaterialApp(
        home: ConsentGate(
          apiClient: api,
          accessToken: 'token',
          child: const Text('GATED'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('GATED'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Tôi đồng ý'), findsNothing);
  });

  testWidgets('consent gate fails closed when status cannot be loaded',
      (tester) async {
    final api = FakeApiClient();
    api.stub(
      'getConsentStatus',
      error: ApiException(message: 'Máy chủ không phản hồi', statusCode: 503),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ConsentGate(
          apiClient: api,
          accessToken: 'token',
          child: const Text('GATED'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Fail closed: gated content blocked, retry offered (Req 6.6 / 11.4).
    expect(find.text('GATED'), findsNothing);
    expect(find.widgetWithText(FilledButton, 'Thử lại'), findsOneWidget);
  });
}

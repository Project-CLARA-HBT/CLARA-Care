// Widget tests for the redesigned login surface (Experience_V3).
//
// clara-mobile-redesign, Task 10.3. These lock the auth behavior and safety
// discipline of the polished sign-in:
//
//   * Empty-field validation blocks submission and issues NO network call
//     (Requirement 10.1).
//   * A successful login persists the session via `SessionStore.setSession`
//     (Requirement 10.2).
//   * A 401 surfaces a friendly Vietnamese message distinct from other errors
//     (Requirement 10.4).
//   * The password field exposes a show/hide toggle affordance.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/experience/redesign/login_screen_v3.dart';

import 'fakes/fakes.dart';

Widget _host(Widget child) => MaterialApp(home: child);

void main() {
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  group('LoginScreenV3 (Requirement 10)', () {
    testWidgets('empty fields block submission and issue no network call',
        (tester) async {
      final api = FakeApiClient();
      final store = FakeSessionStore.empty();

      await tester.pumpWidget(_host(LoginScreenV3(
        apiClient: api,
        sessionStore: store,
      )));
      await tester.pumpAndSettle();

      // Tap the primary action with both fields empty.
      await tester.tap(find.text('Đăng nhập'));
      await tester.pumpAndSettle();

      // No login attempt was made; the session stays unauthenticated.
      expect(api.wasCalled('login'), isFalse);
      expect(store.isAuthenticated, isFalse);
    });

    testWidgets('a successful login persists the session (Req 10.2)',
        (tester) async {
      final api = FakeApiClient()
        ..stub('login', response: {
          'access_token': 'at-123',
          'refresh_token': 'rt-456',
          'role': 'doctor',
          'token_type': 'bearer',
        });
      final store = FakeSessionStore.empty();

      await tester.pumpWidget(_host(LoginScreenV3(
        apiClient: api,
        sessionStore: store,
      )));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byType(TextField).first,
        'user@example.com',
      );
      await tester.enterText(find.byType(TextField).last, 'secret-pass');
      await tester.tap(find.text('Đăng nhập'));
      await tester.pumpAndSettle();

      expect(api.wasCalled('login'), isTrue);
      expect(store.isAuthenticated, isTrue);
      expect(store.accessToken, 'at-123');
      expect(store.role, 'doctor');
    });

    testWidgets('a 401 surfaces a friendly Vietnamese message (Req 10.4)',
        (tester) async {
      final api = FakeApiClient()
        ..stub('login',
            error: ApiException(message: 'Unauthorized', statusCode: 401));
      final store = FakeSessionStore.empty();

      await tester.pumpWidget(_host(LoginScreenV3(
        apiClient: api,
        sessionStore: store,
      )));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField).first, 'user@example.com');
      await tester.enterText(find.byType(TextField).last, 'wrong-pass');
      await tester.tap(find.text('Đăng nhập'));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('kiểm tra lại email và mật khẩu'),
        findsOneWidget,
      );
      expect(store.isAuthenticated, isFalse);
    });

    testWidgets('the password field exposes a show/hide toggle',
        (tester) async {
      final api = FakeApiClient();
      final store = FakeSessionStore.empty();

      await tester.pumpWidget(_host(LoginScreenV3(
        apiClient: api,
        sessionStore: store,
      )));
      await tester.pumpAndSettle();

      // The toggle is labeled "Hiện mật khẩu" while obscured; tapping flips it.
      expect(find.bySemanticsLabel('Hiện mật khẩu'), findsOneWidget);
      await tester.tap(find.bySemanticsLabel('Hiện mật khẩu'));
      await tester.pumpAndSettle();
      expect(find.bySemanticsLabel('Ẩn mật khẩu'), findsOneWidget);
    });
  });
}

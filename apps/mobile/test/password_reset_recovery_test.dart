import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/screens/auth_flows_screen.dart';

import 'fakes/fakes.dart';

void main() {
  group('ForgotPasswordScreen & ResetPasswordScreen (PH03-A06)', () {
    testWidgets('ForgotPasswordScreen submits email and routes to ResetPasswordScreen', (tester) async {
      final fakeApi = FakeApiClient();
      fakeApi.stub('forgotPassword', response: {
        'accepted': true,
        'email_delivery_status': 'sent',
        'reset_token_preview': null,
      });
      final storage = InMemorySessionSecureStorage();
      final store = FakeSessionStore.empty(storage: storage);

      await tester.pumpWidget(MaterialApp(
        home: ForgotPasswordScreen(
          apiClient: fakeApi,
          sessionStore: store,
        ),
      ));
      await tester.pumpAndSettle();

      // Attempt submit without email
      await tester.tap(find.widgetWithText(FilledButton, 'Gửi yêu cầu'));
      await tester.pumpAndSettle();
      expect(find.text('Vui lòng nhập email.'), findsOneWidget);

      // Enter email and submit
      await tester.enterText(find.byType(TextField), 'patient@example.com');
      await tester.tap(find.widgetWithText(FilledButton, 'Gửi yêu cầu'));
      await tester.pumpAndSettle();

      // Neutral accepted envelope message shown
      expect(find.textContaining('Nếu email tồn tại trong hệ thống'), findsOneWidget);
      expect(find.text('Tôi đã có mã đặt lại'), findsOneWidget);

      // Tap navigate to reset
      await tester.tap(find.text('Tôi đã có mã đặt lại'));
      await tester.pumpAndSettle();

      expect(find.byType(ResetPasswordScreen), findsOneWidget);
    });

    testWidgets('ResetPasswordScreen successfully resets and purges session/caches', (tester) async {
      final fakeApi = FakeApiClient();
      fakeApi.stub('resetPassword', response: {'reset': true});
      final storage = InMemorySessionSecureStorage();
      final store = await FakeSessionStore.authenticated(
        email: 'patient@example.com',
        storage: storage,
      );
      await storage.write(PersistentSessionStore.careguardOfflineCacheKey, 'cached-meds');

      expect(store.isAuthenticated, isTrue);

      await tester.pumpWidget(MaterialApp(
        home: ResetPasswordScreen(
          apiClient: fakeApi,
          sessionStore: store,
        ),
      ));
      await tester.pumpAndSettle();

      final textFields = find.byType(TextField);
      expect(textFields, findsNWidgets(2));

      // Enter reset code and new password
      await tester.enterText(textFields.at(0), 'reset-token-123');
      await tester.enterText(textFields.at(1), 'NewPass1234');

      await tester.tap(find.widgetWithText(FilledButton, 'Đặt lại mật khẩu'));
      await tester.pumpAndSettle();

      // Verify reset confirmation shown
      expect(find.textContaining('Mật khẩu của bạn đã được đặt lại'), findsOneWidget);

      // Verify session was purged from store & secure storage
      expect(store.isAuthenticated, isFalse);
      expect(store.accessToken, isNull);
      expect(storage.isEmpty, isTrue);
    });

    testWidgets('ResetPasswordScreen validation rejects empty inputs', (tester) async {
      final fakeApi = FakeApiClient();
      final store = FakeSessionStore.empty();

      await tester.pumpWidget(MaterialApp(
        home: ResetPasswordScreen(
          apiClient: fakeApi,
          sessionStore: store,
        ),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(FilledButton, 'Đặt lại mật khẩu'));
      await tester.pumpAndSettle();

      expect(find.text('Vui lòng nhập mã đặt lại và mật khẩu mới.'), findsOneWidget);
    });
  });
}

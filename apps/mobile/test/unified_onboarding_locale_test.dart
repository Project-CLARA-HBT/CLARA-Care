import 'package:clara_mobile/experience/language_controller.dart';
import 'package:clara_mobile/experience/language_store.dart';
import 'package:clara_mobile/experience/unified/onboarding_flow.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fake_api_client.dart';
import 'fakes/fake_session_store.dart';

class _MemoryLanguageStorage implements LanguageSecureStorage {
  String? value;

  @override
  Future<String?> read(String key) async => value;

  @override
  Future<void> write(String key, String next) async {
    value = next;
  }
}

void main() {
  testWidgets('first-run onboarding follows the selected UI language',
      (tester) async {
    final language = LanguageController(
      store: LanguageStore(storage: _MemoryLanguageStorage()),
    );
    final session = await FakeSessionStore.authenticated(role: 'normal');

    await tester.pumpWidget(
      MaterialApp(
        home: OnboardingFlow(
          apiClient: FakeApiClient(),
          sessionStore: session,
          languageController: language,
          onDone: () {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Chào mừng bạn đến với CLARA'), findsOneWidget);
    expect(find.text('Bắt đầu'), findsOneWidget);

    await language.setLanguage('en');
    await tester.pump();

    expect(find.text('Welcome to CLARA'), findsOneWidget);
    expect(find.text('Get started'), findsOneWidget);
    expect(find.text('Chào mừng bạn đến với CLARA'), findsNothing);
  });
}

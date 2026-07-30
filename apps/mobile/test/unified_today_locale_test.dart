import 'package:clara_mobile/experience/language_controller.dart';
import 'package:clara_mobile/experience/language_store.dart';
import 'package:clara_mobile/experience/unified/today_surface.dart';
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
  testWidgets('Today uses the terminology contract after locale changes',
      (tester) async {
    final api = FakeApiClient()
      ..stub('getLifeMapToday', response: <String, dynamic>{
        'tasks': const <Map<String, dynamic>>[],
        'episodes': const <Map<String, dynamic>>[],
        'pending_confirmation_count': 0,
      });
    final session = await FakeSessionStore.authenticated();
    final language = LanguageController(
      store: LanguageStore(storage: _MemoryLanguageStorage()),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: TodaySurface(
            apiClient: api,
            sessionStore: session,
            languageController: language,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Hôm nay'), findsOneWidget);
    expect(find.text('Hôm nay chưa có việc nào'), findsOneWidget);

    await language.setLanguage('en');
    await tester.pump();

    expect(find.text('Today'), findsOneWidget);
    expect(find.text('No tasks for today'), findsOneWidget);
    expect(find.text('Hôm nay chưa có việc nào'), findsNothing);
  });
}

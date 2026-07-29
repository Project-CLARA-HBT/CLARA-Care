import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/lifemap_read_cache.dart';
import 'package:clara_mobile/experience/unified/today_surface.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fake_api_client.dart';
import 'fakes/fake_session_store.dart';

void main() {
  testWidgets('offline cache is labeled and cannot complete a task',
      (tester) async {
    final storage = InMemorySessionSecureStorage();
    final cache = LifeMapReadCache(storage: storage, enabled: true);
    await cache.save(
      <String, dynamic>{
        'generated_at': DateTime.now().toUtc().toIso8601String(),
        'tasks': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 'task-1',
            'title': 'Việc đã lưu',
            'due_at': null,
          },
        ],
        'episodes': const <Map<String, dynamic>>[],
        'pending_confirmation_count': 0,
      },
    );
    final session = await FakeSessionStore.authenticated(storage: storage);
    final api = FakeApiClient()
      ..stub(
        'getLifeMapToday',
        error: ApiException(message: 'network unavailable'),
      );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: TodaySurface(
            apiClient: api,
            sessionStore: session,
            readCache: cache,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Việc đã lưu'), findsOneWidget);
    expect(find.textContaining('Ngoại tuyến · lưu lúc'), findsOneWidget);
    final button = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Hoàn tất'),
    );
    expect(button.onPressed, isNull);
    expect(api.wasCalled('completeLifeMapTask'), isFalse);
  });
}

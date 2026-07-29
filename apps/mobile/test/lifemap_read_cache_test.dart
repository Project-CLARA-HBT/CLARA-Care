import 'package:clara_mobile/core/lifemap_read_cache.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:flutter_test/flutter_test.dart';

class MemoryStorage implements SessionSecureStorage {
  final Map<String, String> values = <String, String>{};

  @override
  Future<void> delete(String key) async => values.remove(key);

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async => values[key] = value;
}

void main() {
  test('cache is default closed', () async {
    final storage = MemoryStorage();
    final cache = LifeMapReadCache(storage: storage);
    expect(await cache.save(<String, dynamic>{}), isFalse);
    expect(await cache.read(), isNull);
    expect(storage.values, isEmpty);
  });

  test('encrypted-storage payload is least necessary and time bounded',
      () async {
    final storage = MemoryStorage();
    final cache = LifeMapReadCache(storage: storage, enabled: true);
    final now = DateTime.utc(2026, 7, 29, 10);
    await cache.save(
      <String, dynamic>{
        'generated_at': now.toIso8601String(),
        'tasks': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 'task-1',
            'title': 'Uống nước',
            'due_at': null,
            'provenance': <String, String>{'secret': 'must-drop'},
          },
        ],
        'episodes': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 'episode-1',
            'title': 'Theo dõi',
            'priority': 'routine',
            'medical_payload': 'must-drop',
          },
        ],
        'pending_confirmation_count': 2,
        'medications': <String>['must-drop'],
        'safety_status': 'must-drop',
      },
      now: now,
    );

    final raw = storage.values[LifeMapReadCache.storageKey]!;
    expect(raw, isNot(contains('must-drop')));
    expect(raw, isNot(contains('medications')));
    expect(raw, isNot(contains('safety_status')));
    final cached = await cache.read();
    expect(cached, isNotNull);
    expect(cached!.isStaleAt(now.add(const Duration(minutes: 14))), isFalse);
    expect(cached.isStaleAt(now.add(const Duration(minutes: 15))), isTrue);
  });

  test('logout removes the account-scoped health read cache', () async {
    final storage = MemoryStorage();
    storage.values[LifeMapReadCache.storageKey] = 'private projection';
    final session = PersistentSessionStore(storage: storage);
    await session.clear();
    expect(storage.values[LifeMapReadCache.storageKey], isNull);
  });
}

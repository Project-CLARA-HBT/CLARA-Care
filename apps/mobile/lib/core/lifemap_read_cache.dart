import 'dart:convert';

import 'session_store.dart';

/// Default-off encrypted cache for the least-necessary Today read projection.
const bool kLifeMapOfflineReadCacheEnabled = bool.fromEnvironment(
  'LIFEMAP_OFFLINE_READ_CACHE_ENABLED',
  defaultValue: false,
);

class CachedLifeMapToday {
  const CachedLifeMapToday({
    required this.cachedAt,
    required this.validUntil,
    required this.data,
  });

  final DateTime cachedAt;
  final DateTime validUntil;
  final Map<String, dynamic> data;

  bool isStaleAt(DateTime now) => !now.toUtc().isBefore(validUntil.toUtc());
}

/// Stores only the rendered Today projection in platform secure storage.
///
/// It deliberately excludes provenance, source documents, medications,
/// free-form event payloads, safety results, profile identity and credentials.
/// A cached projection is always presented as offline and can never authorize a
/// mutation, even before [validUntil].
class LifeMapReadCache {
  LifeMapReadCache({
    SessionSecureStorage? storage,
    this.userId,
    bool enabled = kLifeMapOfflineReadCacheEnabled,
  })  : _storage = storage ?? FlutterSecureSessionStorage(),
        _enabled = enabled;

  static const String baseStorageKey = 'clara.lifemap.today.read_projection';
  static const String storageKey = 'clara.lifemap.today.read_projection';
  static const int _version = 1;
  static const int _maxItems = 100;

  static String scopedStorageKey(String? userId) =>
      userId != null && userId.isNotEmpty
          ? 'clara.lifemap.today.$userId.read_projection'
          : storageKey;

  final SessionSecureStorage _storage;
  final String? userId;
  final bool _enabled;

  String get effectiveStorageKey => scopedStorageKey(userId);
  bool get enabled => _enabled;

  static Map<String, dynamic> project(Map<String, dynamic> input) {
    List<Map<String, dynamic>> items(Object? raw, Set<String> keys) {
      if (raw is! List) return const [];
      return raw.whereType<Map>().take(_maxItems).map((item) {
        final projected = <String, dynamic>{};
        for (final key in keys) {
          final value = item[key];
          if (value == null) continue;
          projected[key] = value is String && value.length > 500
              ? value.substring(0, 500)
              : value;
        }
        return projected;
      }).toList();
    }

    final count = input['pending_confirmation_count'];
    return <String, dynamic>{
      'generated_at': input['generated_at']?.toString(),
      'tasks': items(input['tasks'], const {'id', 'title', 'due_at'}),
      'episodes': items(input['episodes'], const {'id', 'title', 'priority'}),
      'pending_confirmation_count': count is int ? count.clamp(0, 10000) : 0,
    };
  }

  Future<bool> save(
    Map<String, dynamic> data, {
    DateTime? now,
    Duration validity = const Duration(minutes: 15),
  }) async {
    if (!_enabled) return false;
    final cachedAt = (now ?? DateTime.now()).toUtc();
    await _storage.write(
      effectiveStorageKey,
      jsonEncode(<String, dynamic>{
        'version': _version,
        'cached_at': cachedAt.toIso8601String(),
        'valid_until': cachedAt.add(validity).toIso8601String(),
        'data': project(data),
      }),
    );
    return true;
  }

  Future<CachedLifeMapToday?> read({DateTime? now}) async {
    if (!_enabled) return null;
    final raw = await _storage.read(effectiveStorageKey);
    if (raw == null || raw.isEmpty) return null;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map || decoded['version'] != _version) return null;
      final cachedAt =
          DateTime.tryParse(decoded['cached_at']?.toString() ?? '');
      final validUntil =
          DateTime.tryParse(decoded['valid_until']?.toString() ?? '');
      final data = decoded['data'];
      if (cachedAt == null || validUntil == null || data is! Map) return null;
      final cached = CachedLifeMapToday(
        cachedAt: cachedAt.toUtc(),
        validUntil: validUntil.toUtc(),
        data: project(data.cast<String, dynamic>()),
      );
      if (cached.isStaleAt(now ?? DateTime.now())) {
        return null;
      }
      return cached;
    } catch (_) {
      return null;
    }
  }

  Future<void> clear() async {
    await _storage.delete(effectiveStorageKey);
    if (effectiveStorageKey != storageKey) {
      await _storage.delete(storageKey);
    }
  }
}

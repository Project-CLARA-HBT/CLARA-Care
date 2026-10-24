import 'dart:convert';

import 'lifemap_timeline_models.dart';
import 'session_store.dart';

/// Container for a cached timeline snapshot.
class CachedLifeMapTimeline {
  const CachedLifeMapTimeline({
    required this.cachedAt,
    required this.validUntil,
    required this.events,
  });

  final DateTime cachedAt;
  final DateTime validUntil;
  final List<LifeMapTimelineEvent> events;

  bool isStaleAt(DateTime now) => !now.toUtc().isBefore(validUntil.toUtc());
}

/// Secure offline read cache for the LifeMap longitudinal timeline.
///
/// Follows safety invariant:
/// - Deliberately excludes raw credentials, auth tokens, external documents,
///   and full binary attachments.
/// - Scoped per authenticated user (`clara.lifemap.timeline.$userId.read_projection`).
/// - Default TTL of 15 minutes.
/// - Read-only projection: cached events can never authorize mutations.
class LifeMapTimelineReadCache {
  LifeMapTimelineReadCache({
    SessionSecureStorage? storage,
    this.userId,
    this.enabled = true,
  }) : _storage = storage ?? FlutterSecureSessionStorage();

  static const String baseStorageKey = 'clara.lifemap.timeline.read_projection';
  static const int _version = 1;
  static const int _maxEvents = 150;

  static String scopedStorageKey(String? userId) =>
      userId != null && userId.isNotEmpty
          ? 'clara.lifemap.timeline.$userId.read_projection'
          : baseStorageKey;

  final SessionSecureStorage _storage;
  final String? userId;
  final bool enabled;

  String get effectiveStorageKey => scopedStorageKey(userId);

  /// Projects events down to essential, non-PII, length-capped timeline data.
  static List<Map<String, dynamic>> projectEvents(List<LifeMapTimelineEvent> events) {
    return events.take(_maxEvents).map((event) {
      String sanitize(String? text) {
        if (text == null) return '';
        final trimmed = text.trim();
        return trimmed.length > 500 ? '${trimmed.substring(0, 500)}...' : trimmed;
      }

      return <String, dynamic>{
        'id': event.id,
        'event_type': event.eventType,
        'truth_state': event.truthState.wireValue,
        'occurred_at': event.occurredAt.toIso8601String(),
        'recorded_at': event.recordedAt.toIso8601String(),
        'title': sanitize(event.title),
        if (event.summary != null) 'summary': sanitize(event.summary),
        if (event.sourceKind != null) 'source_kind': event.sourceKind,
        if (event.episodeId != null) 'episode_id': event.episodeId,
        'revision_no': event.revisionNo,
      };
    }).toList();
  }

  /// Persists a timeline snapshot into secure storage.
  Future<bool> save(
    List<LifeMapTimelineEvent> events, {
    DateTime? now,
    Duration validity = const Duration(minutes: 15),
  }) async {
    if (!enabled) return false;
    final cachedAt = (now ?? DateTime.now()).toUtc();
    final validUntil = cachedAt.add(validity);

    try {
      final payload = jsonEncode(<String, dynamic>{
        'version': _version,
        'cached_at': cachedAt.toIso8601String(),
        'valid_until': validUntil.toIso8601String(),
        'events': projectEvents(events),
      });

      await _storage.write(effectiveStorageKey, payload);
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Reads cached timeline events if not stale.
  Future<CachedLifeMapTimeline?> read({DateTime? now}) async {
    if (!enabled) return null;
    final raw = await _storage.read(effectiveStorageKey);
    if (raw == null || raw.isEmpty) return null;

    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map || decoded['version'] != _version) return null;

      final cachedAtStr = decoded['cached_at']?.toString();
      final validUntilStr = decoded['valid_until']?.toString();
      final rawEvents = decoded['events'];

      if (cachedAtStr == null || validUntilStr == null || rawEvents is! List) {
        return null;
      }

      final DateTime cachedAt;
      final DateTime validUntil;
      try {
        cachedAt = DateTime.parse(cachedAtStr);
        validUntil = DateTime.parse(validUntilStr);
      } catch (_) {
        return null;
      }

      final events = <LifeMapTimelineEvent>[];
      for (final item in rawEvents) {
        if (item is Map) {
          events.add(LifeMapTimelineEvent.fromJson(item.cast<String, dynamic>()));
        }
      }

      final cached = CachedLifeMapTimeline(
        cachedAt: cachedAt.toUtc(),
        validUntil: validUntil.toUtc(),
        events: events,
      );

      if (cached.isStaleAt(now ?? DateTime.now())) {
        return null;
      }

      return cached;
    } catch (_) {
      return null;
    }
  }

  /// Clears the scoped timeline cache.
  Future<void> clear() async {
    await _storage.delete(effectiveStorageKey);
    if (effectiveStorageKey != baseStorageKey) {
      await _storage.delete(baseStorageKey);
    }
  }
}

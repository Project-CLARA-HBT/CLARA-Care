import 'dart:convert';

import 'api_client.dart';
import 'session_store.dart';

/// CareGuard offline / degraded-mode client fallback (CLARA_Mobile).
///
/// When `CAREGUARD_OFFLINE_FALLBACK_ENABLED` is on and a fresh DDI check cannot
/// reach the API, the client renders the last successfully retrieved End_User
/// DDI projection, clearly labeled "offline / không phải thời gian thực" so the
/// user knows the result is stale (Requirement 6.3). Mirrors the web behavior
/// in `apps/web/lib/careguard-offline.ts`.
///
/// Safety boundaries:
///  - **Default OFF.** With the flag off, [CareguardOfflineCache.save] is a
///    no-op and [CareguardOfflineCache.read] returns `null`, so behavior is
///    unchanged (Requirement 12.1, 12.2).
///  - **Projection only.** Only the four End_User fields are persisted; the
///    cache re-projects on both write and read so no runtime mode, fallback
///    flag, connector identifier, or `source_errors` fragment can be written to
///    device storage (Requirement 3.4, 6.2).
///  - **No fabricated all-clear.** A cache miss returns `null`; the caller
///    keeps its normal error instead of inventing a "no interaction" result
///    (Requirement 6.4).

/// Build-time, client-readable feature flag. Override with
/// `--dart-define=CAREGUARD_OFFLINE_FALLBACK_ENABLED=true`. Defaults to OFF.
const bool kCareguardOfflineFallbackEnabled =
    bool.fromEnvironment('CAREGUARD_OFFLINE_FALLBACK_ENABLED', defaultValue: false);

/// Vietnamese-first label shown on a stale, offline-served DDI result (Req 6.3).
const String careguardOfflineLabel = 'offline / không phải thời gian thực';

/// A cached last-known DDI projection plus the time it was captured.
class CachedDdiProjection {
  const CachedDdiProjection({required this.cachedAt, required this.view});

  final DateTime cachedAt;

  /// The sanitized four-field End_User projection
  /// (`riskLevel`, `alerts`, `recommendations`, `sources`).
  final Map<String, dynamic> view;
}

/// Heuristic: did this failure look like the device could not reach the API
/// (offline / network / timeout / gateway), as opposed to a normal server-side
/// rejection (4xx with a real body)?
bool isLikelyOfflineFailure(Object error) {
  if (error is ApiException) {
    final status = error.statusCode;
    // No status => the request never reached a server response (socket/timeout
    // wrapped by the streaming path). Gateway statuses are degraded upstream.
    return status == null || status == 502 || status == 503 || status == 504;
  }
  // SocketException / http ClientException / TimeoutException and friends all
  // indicate the client could not complete the round-trip.
  return true;
}

/// Persists and restores the last-known End_User DDI projection on device.
class CareguardOfflineCache {
  CareguardOfflineCache({
    required SessionSecureStorage storage,
    bool enabled = kCareguardOfflineFallbackEnabled,
  })  : _storage = storage,
        _enabled = enabled;

  static const String storageKey = 'clara.careguard.ddi.last_known_view';
  static const int _version = 1;

  final SessionSecureStorage _storage;
  final bool _enabled;

  bool get enabled => _enabled;

  /// Re-project an arbitrary view map down to exactly the four user-facing
  /// fields, dropping anything else so only the End_User projection — never an
  /// internal/diagnostic field — is persisted (Requirement 3.4, 6.2).
  static Map<String, dynamic> projectForCache(Map<String, dynamic> view) {
    return <String, dynamic>{
      'riskLevel': (view['riskLevel'] ?? 'unknown').toString(),
      'alerts': _projectAlerts(view['alerts']),
      'recommendations': _projectStringList(view['recommendations']),
      'sources': _projectSources(view['sources']),
    };
  }

  static List<Map<String, dynamic>> _projectAlerts(dynamic raw) {
    if (raw is! List) return const [];
    final out = <Map<String, dynamic>>[];
    for (final item in raw) {
      if (item is! Map) continue;
      final map = item.cast<String, dynamic>();
      final message = (map['message'] ?? '').toString();
      final alert = <String, dynamic>{
        'message': message,
        'severity': (map['severity'] ?? 'unknown').toString(),
      };
      final details = map['details'];
      if (details is String && details.trim().isNotEmpty) {
        alert['details'] = details;
      }
      out.add(alert);
    }
    return out;
  }

  static List<Map<String, dynamic>> _projectSources(dynamic raw) {
    if (raw is! List) return const [];
    final out = <Map<String, dynamic>>[];
    for (final item in raw) {
      if (item is! Map) continue;
      final map = item.cast<String, dynamic>();
      final label = (map['label'] ?? '').toString();
      final source = <String, dynamic>{'label': label};
      final url = map['url'];
      if (url is String && url.trim().isNotEmpty) {
        source['url'] = url;
      }
      out.add(source);
    }
    return out;
  }

  static List<String> _projectStringList(dynamic raw) {
    if (raw is! List) return const [];
    return raw
        .where((item) => item is String && item.trim().isNotEmpty)
        .map((item) => item as String)
        .toList();
  }

  /// Persist the last successfully retrieved DDI projection. No-op when the
  /// flag is off. Returns `true` only when a value was written.
  Future<bool> save(Map<String, dynamic> view, {DateTime? now}) async {
    if (!_enabled) return false;
    final payload = <String, dynamic>{
      'version': _version,
      'cachedAt': (now ?? DateTime.now().toUtc()).toIso8601String(),
      'view': projectForCache(view),
    };
    await _storage.write(storageKey, jsonEncode(payload));
    return true;
  }

  /// Read the last-known projection, or `null` when the flag is off, no cache
  /// exists, or the stored value is missing/invalid. Never fabricates a result.
  Future<CachedDdiProjection?> read() async {
    if (!_enabled) return null;
    final raw = await _storage.read(storageKey);
    if (raw == null || raw.isEmpty) return null;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return null;
      if (decoded['version'] != _version) return null;
      final cachedAtRaw = decoded['cachedAt'];
      final viewRaw = decoded['view'];
      if (cachedAtRaw is! String || viewRaw is! Map) return null;
      final cachedAt = DateTime.tryParse(cachedAtRaw);
      if (cachedAt == null) return null;
      return CachedDdiProjection(
        cachedAt: cachedAt,
        view: projectForCache(viewRaw.cast<String, dynamic>()),
      );
    } catch (_) {
      return null;
    }
  }

  /// Remove any cached last-known DDI projection.
  Future<void> clear() async {
    await _storage.delete(storageKey);
  }
}

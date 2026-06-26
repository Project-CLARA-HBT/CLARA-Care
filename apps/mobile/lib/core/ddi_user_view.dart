// CareGuard End_User DDI projection (CLARA_Mobile).
//
// Single source of truth for the four-field End_User projection shared by the
// manual DDI check screen (`careguard_screen.dart`) and the cabinet CRUD screen
// (`careguard_cabinet_screen.dart`). Parsing the raw CareGuard `analyze` payload
// here — once — guarantees both surfaces drop runtime mode, fallback flags,
// connector identifiers, HTTP status detail, and `source_errors`, exposing only
// risk level, alerts, recommendations, and reference sources
// (Requirements 3.1, 3.4, 3.6, 8.1, 8.4).
//
// Pure Dart (no Flutter dependency) so it can be unit-tested without platform
// channels and reused by both the model and offline-cache layers.

/// A single user-facing interaction alert. Only a human-readable message and an
/// optional detail line are exposed — never the contributing source set,
/// raw severity, or any connector/runtime field (Requirement 3.4, 8.4).
class DdiAlert {
  const DdiAlert({required this.message, this.details});

  final String message;
  final String? details;
}

/// End_User DDI projection: only risk level, alerts, recommendations, and
/// reference sources. Runtime mode, fallback flags, connector identifiers, and
/// `source_errors` are intentionally excluded (Requirements 3.1, 3.4, 3.6).
class DdiUserView {
  DdiUserView({
    required this.riskLevel,
    required this.alerts,
    required this.recommendations,
    required this.sources,
  });

  final String riskLevel;
  final List<DdiAlert> alerts;
  final List<String> recommendations;
  final List<String> sources;

  /// Serialize to the four-field End_User projection for offline caching.
  /// Only user-facing fields are emitted (Requirement 3.4, 6.2).
  Map<String, dynamic> toCacheJson() {
    return <String, dynamic>{
      'riskLevel': riskLevel,
      'alerts': alerts
          .map((alert) => <String, dynamic>{
                'message': alert.message,
                'severity': riskLevel,
                if (alert.details != null) 'details': alert.details,
              })
          .toList(),
      'recommendations': recommendations,
      'sources':
          sources.map((label) => <String, dynamic>{'label': label}).toList(),
    };
  }

  /// Rebuild a view from a cached four-field projection.
  factory DdiUserView.fromCacheJson(Map<String, dynamic> json) {
    final alerts = <DdiAlert>[];
    final rawAlerts = json['alerts'];
    if (rawAlerts is List) {
      for (final item in rawAlerts) {
        if (item is Map) {
          final map = item.cast<String, dynamic>();
          final message = (map['message'] ?? '').toString().trim();
          if (message.isEmpty) continue;
          final details = map['details']?.toString().trim();
          alerts.add(DdiAlert(
            message: message,
            details: (details != null && details.isNotEmpty) ? details : null,
          ));
        }
      }
    }
    final sources = <String>[];
    final rawSources = json['sources'];
    if (rawSources is List) {
      for (final item in rawSources) {
        if (item is Map) {
          final label =
              item.cast<String, dynamic>()['label']?.toString().trim();
          if (label != null && label.isNotEmpty) sources.add(label);
        }
      }
    }
    return DdiUserView(
      riskLevel: _classifyRisk((json['riskLevel'] ?? '').toString()),
      alerts: alerts,
      recommendations: _stringList(json['recommendations']),
      sources: sources,
    );
  }

  String get riskLabel {
    switch (riskLevel) {
      case 'high':
      case 'critical':
        return 'Cao';
      case 'medium':
        return 'Trung bình';
      case 'low':
        return 'Thấp';
      default:
        return 'Chưa xác định';
    }
  }

  static String _classifyRisk(String? raw) {
    final value = (raw ?? '').toLowerCase();
    if (RegExp(r'critical|contra|fatal').hasMatch(value)) return 'critical';
    if (RegExp(r'severe|major|high|danger').hasMatch(value)) return 'high';
    if (RegExp(r'moderate|medium|amber').hasMatch(value)) return 'medium';
    if (RegExp(r'minor|low|safe|none').hasMatch(value)) return 'low';
    return 'unknown';
  }

  static List<String> _stringList(dynamic value) {
    if (value is List) {
      return value
          .map((item) => item?.toString().trim() ?? '')
          .where((item) => item.isNotEmpty)
          .toList();
    }
    if (value is String && value.trim().isNotEmpty) {
      return [value.trim()];
    }
    return const [];
  }

  factory DdiUserView.fromPayload(Map<String, dynamic> payload) {
    final risk = payload['risk'];
    final riskTier = payload['risk_tier'] ??
        payload['riskTier'] ??
        payload['tier'] ??
        (risk is Map ? risk['level'] : risk);

    final rawAlerts = payload['ddi_alerts'] ?? payload['ddiAlerts'];
    final alerts = <DdiAlert>[];
    if (rawAlerts is List) {
      for (final item in rawAlerts) {
        if (item is String && item.trim().isNotEmpty) {
          alerts.add(DdiAlert(message: item.trim()));
        } else if (item is Map) {
          final map = item.cast<String, dynamic>();
          final message = (map['title'] ??
                  map['interaction'] ??
                  map['message'] ??
                  map['summary'])
              ?.toString()
              .trim();
          if (message != null && message.isNotEmpty) {
            final details =
                (map['details'] ?? map['description'] ?? map['recommendation'])
                    ?.toString()
                    .trim();
            alerts.add(DdiAlert(
              message: message,
              details: (details != null && details.isNotEmpty) ? details : null,
            ));
          }
        }
      }
    }

    final recommendations = <String>[
      ..._stringList(payload['recommendations']),
      ..._stringList(payload['recommendation']),
    ];

    // Sources come from the attribution block (label only); connector errors
    // are never surfaced.
    final sources = <String>[];
    final attribution = payload['attribution'];
    if (attribution is Map) {
      final list = attribution['sources'];
      if (list is List) {
        for (final item in list) {
          if (item is Map) {
            final name = item['name']?.toString().trim();
            if (name != null && name.isNotEmpty && !sources.contains(name)) {
              sources.add(name);
            }
          }
        }
      }
    }

    return DdiUserView(
      riskLevel: _classifyRisk(riskTier?.toString()),
      alerts: alerts,
      recommendations: recommendations.toSet().toList(),
      sources: sources,
    );
  }
}

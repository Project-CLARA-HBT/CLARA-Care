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

/// A single user-facing interaction alert. A human-readable message, an optional
/// detail line, a coarse severity band, and the interacting medication names are
/// exposed — never the contributing source set or any connector/runtime field
/// (Requirement 3.4, 8.4). Severity is a coarse band (`critical`/`high`/`medium`
/// /`low`/`unknown`) suitable for text+icon ranking, not a raw upstream code.
class DdiAlert {
  const DdiAlert({
    required this.message,
    this.details,
    this.severity = 'unknown',
    this.medications = const [],
  });

  final String message;
  final String? details;
  final String severity;
  final List<String> medications;

  /// Coarse severity rank for sorting (higher = more severe). Text+icon convey
  /// meaning too, so this is never the sole signal (a11y).
  int get severityRank {
    switch (severity) {
      case 'critical':
        return 4;
      case 'high':
        return 3;
      case 'medium':
        return 2;
      case 'low':
        return 1;
      default:
        return 0;
    }
  }

  /// Vietnamese-first severity label.
  String get severityLabel {
    switch (severity) {
      case 'critical':
        return 'Nghiêm trọng';
      case 'high':
        return 'Cao';
      case 'medium':
        return 'Trung bình';
      case 'low':
        return 'Thấp';
      default:
        return 'Chưa xác định';
    }
  }
}

/// A DrugBank identity offered by the server for an unresolved cabinet label.
///
/// This is not a local normalization, an AI suggestion, or a risk result. The
/// user may choose one only to resubmit it to the owner-scoped API, which
/// verifies the cabinet item, raw alias, DrugBank ID, and index version again.
class CareguardClarificationCandidate {
  const CareguardClarificationCandidate({
    required this.drugbankId,
    required this.normalizedName,
    required this.activeIngredients,
    required this.sourceVersion,
  });

  final String drugbankId;
  final String normalizedName;
  final List<String> activeIngredients;
  final String sourceVersion;

  factory CareguardClarificationCandidate.fromJson(Map<String, dynamic> json) {
    final rawIngredients = json['active_ingredients'];
    return CareguardClarificationCandidate(
      drugbankId: _trimmed(json['drugbank_id']),
      normalizedName: _trimmed(json['normalized_name']),
      activeIngredients: rawIngredients is List
          ? rawIngredients
              .map(_trimmed)
              .where((item) => item.isNotEmpty)
              .toList(growable: false)
          : const <String>[],
      sourceVersion: _trimmed(json['source_version']),
    );
  }

  /// A malformed candidate is never selectable. This ensures the app cannot
  /// manufacture a DrugBank choice when the source-backed contract is absent.
  bool get isSourceBacked =>
      drugbankId.isNotEmpty &&
      normalizedName.isNotEmpty &&
      sourceVersion.isNotEmpty;
}

/// A terminal, fail-closed clarification request from CareGuard.
class CareguardMedicationClarification {
  const CareguardMedicationClarification({
    required this.cabinetItemId,
    required this.inputAlias,
    required this.candidates,
  });

  final int cabinetItemId;
  final String inputAlias;
  final List<CareguardClarificationCandidate> candidates;

  factory CareguardMedicationClarification.fromJson(Map<String, dynamic> json) {
    final itemId = json['cabinet_item_id'];
    final rawCandidates = json['candidates'];
    return CareguardMedicationClarification(
      cabinetItemId: itemId is num ? itemId.toInt() : 0,
      inputAlias: _trimmed(json['input_alias']),
      candidates: rawCandidates is List
          ? rawCandidates
              .whereType<Map>()
              .map(
                (candidate) => CareguardClarificationCandidate.fromJson(
                  candidate.cast<String, dynamic>(),
                ),
              )
              .where((candidate) => candidate.isSourceBacked)
              .toList(growable: false)
          : const <CareguardClarificationCandidate>[],
    );
  }

  bool get isValid => cabinetItemId > 0 && inputAlias.isNotEmpty;
}

String _trimmed(Object? value) => value?.toString().trim() ?? '';

/// Parses only CareGuard's explicit terminal clarification state.
///
/// `null` means this was not a clarification response. An empty list means the
/// server intentionally withheld a usable source-backed choice, so callers
/// must show the incomplete-check state and must not render or cache a DDI
/// result. Invalid rows are dropped rather than guessed.
List<CareguardMedicationClarification>? medicationClarificationsFromPayload(
  Map<String, dynamic> payload,
) {
  if (payload['status'] != 'requires_medication_clarification') return null;
  final raw = payload['clarifications'];
  if (raw is! List) return const <CareguardMedicationClarification>[];
  return raw
      .whereType<Map>()
      .map(
        (item) => CareguardMedicationClarification.fromJson(
          item.cast<String, dynamic>(),
        ),
      )
      .where((item) => item.isValid)
      .toList(growable: false);
}

/// End_User DDI projection: only risk level, alerts, recommendations, and
/// reference sources. Runtime mode, fallback flags, connector identifiers, and
/// `source_errors` are intentionally excluded (Requirements 3.1, 3.4, 3.6).
class DdiUserView {
  DdiUserView({
    required this.riskLevel,
    required List<DdiAlert> alerts,
    required this.recommendations,
    required this.sources,
  }) : alerts = _sortBySeverity(alerts);

  /// Alerts sorted most-severe-first so the highest-risk interaction is always
  /// surfaced at the top of the professional result view. Stable within a band.
  static List<DdiAlert> _sortBySeverity(List<DdiAlert> input) {
    final sorted = [...input];
    sorted.sort((a, b) => b.severityRank.compareTo(a.severityRank));
    return sorted;
  }

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
                'severity': alert.severity,
                if (alert.medications.isNotEmpty)
                  'medications': alert.medications,
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
            severity: _classifyRisk((map['severity'] ?? '').toString()),
            medications: _stringList(map['medications']),
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
            // Per-alert severity: prefer the alert's own severity, else fall
            // back to the overall risk tier. Medications name the interacting
            // pair (DrugBank rows carry a sorted two-medication list).
            final alertSeverity = (map['severity'] ?? riskTier)?.toString();
            alerts.add(DdiAlert(
              message: message,
              details: (details != null && details.isNotEmpty) ? details : null,
              severity: _classifyRisk(alertSeverity),
              medications: _stringList(map['medications']),
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

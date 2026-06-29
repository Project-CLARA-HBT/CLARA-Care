// =============================================================================
// EndUserSafeAnswer — End_User-safe projection + answer view for CLARA_Mobile.
// clara-mobile-feature-parity Task 3.3 (Requirement 1.6; design Property P3/P4).
//
//   * 1.6  The chat answer view excludes internal runtime fields
//          (RAG/research/fallback mode, retrieval, connector source_errors,
//          policy verdicts) for non-admin roles.
//   * P3   Chat / DDI / scribe views never contain internal runtime fields for
//          non-admin roles.
//   * P4   User-facing text is passed through `stripTelemetryLabels`, so no
//          internal label survives in the rendered copy.
//
// The projection is a **pure function** (`endUserSafeProjection`) with no
// Flutter dependency, so it is unit/property testable in isolation (it is also
// the building block for the Property P3 generated test in task 3.4). The
// [EndUserSafeAnswer] widget composes that projection with `stripTelemetryLabels`
// to render only the End_User-safe content (answer text, citations, disclaimer);
// an `admin` role additionally sees the full, unredacted envelope detail.
//
// Mirrors the web End_User-safe philosophy used by the DDI projection
// (`toDdiUserView`) and the chat answer renderer: a denylist of internal /
// telemetry keys is dropped at every nesting depth, and everything else (the
// genuine user-facing signal) is preserved.
// =============================================================================

import 'package:flutter/material.dart';

import '../core/research_telemetry_gate.dart' show kAdminRole, stripTelemetryLabels;
import 'error_retry_view.dart' show kMinTouchTarget;

// -----------------------------------------------------------------------------
// Pure projection
// -----------------------------------------------------------------------------

/// Distinctive normalized markers identifying an internal/telemetry key.
///
/// A key is internal when its normalized form (lower-cased, with `_`/`-`/spaces
/// removed) *contains* any of these markers. They are chosen to be distinctive
/// enough that genuine user-facing keys (e.g. `model_used`, `model_family`,
/// `model_version`) are preserved while runtime fields are dropped.
const List<String> _kInternalKeyMarkers = <String>[
  'retrieval', // retrieval, retrieval_errors, retrieval_route
  'retrieved', // retrieved_ids, retrieved_chunks
  'sourceerror', // source_errors, source_error, sourceErrors
  'policy', // policy, policy_verdict(s), policy_decision
  'telemetry', // telemetry, telemetry_errors
  'debug', // debug, debug_info
  'reasoning', // reasoning, reasoning_digest
  'pipeline', // pipeline, pipeline_stage
  'fallback', // fallback, fallback_used, fallback_reason, fallback_mode
  'degraded', // degraded_path
  'connector', // connector, connectors
  'verificationmatrix', // verification_matrix
  'routerconfidence', // router_confidence
];

/// Normalizes a key for internal-field matching: lower-cased with separators
/// (`_`, `-`, whitespace) removed.
String _normalizeKey(String key) =>
    key.toLowerCase().replaceAll(RegExp(r'[\s_\-]+'), '');

/// Whether [key] denotes an internal runtime / telemetry field that must be
/// dropped from a non-admin End_User projection (Requirement 1.6; Property P3).
///
/// `mode` is matched exactly or as a suffix (`rag_mode`, `research_mode`,
/// `fallback_mode`) so that `model`, `model_used`, and similar user-facing keys
/// are **not** swept up. Every other marker is matched as a substring of the
/// normalized key.
bool isInternalRuntimeKey(String key) {
  final normalized = _normalizeKey(key);
  if (normalized.isEmpty) {
    return false;
  }
  // Runtime "mode" fields (mode / rag_mode / research_mode / fallback_mode)
  // without catching "model"/"model_used" (which do not end in "mode").
  if (normalized == 'mode' || normalized.endsWith('mode')) {
    return true;
  }
  for (final marker in _kInternalKeyMarkers) {
    if (normalized.contains(marker)) {
      return true;
    }
  }
  return false;
}

/// Recursively strips internal runtime keys from an arbitrary JSON-like value.
Object? _stripInternal(Object? value) {
  if (value is Map) {
    final out = <String, dynamic>{};
    value.forEach((dynamic rawKey, dynamic rawValue) {
      final key = rawKey.toString();
      if (isInternalRuntimeKey(key)) {
        return; // drop internal runtime field at any nesting depth
      }
      out[key] = _stripInternal(rawValue);
    });
    return out;
  }
  if (value is List) {
    return value.map(_stripInternal).toList();
  }
  return value;
}

/// Deep copy of a JSON-like value (used for the admin/full path so the caller
/// never mutates the source envelope).
Object? _deepCopy(Object? value) {
  if (value is Map) {
    final out = <String, dynamic>{};
    value.forEach((dynamic k, dynamic v) => out[k.toString()] = _deepCopy(v));
    return out;
  }
  if (value is List) {
    return value.map(_deepCopy).toList();
  }
  return value;
}

/// Projects an answer [envelope] into an End_User-safe map.
///
/// * When [isAdmin] is true, the full envelope is returned (deep-copied so the
///   source is never mutated) — admins may see the complete runtime detail.
/// * Otherwise every internal runtime / telemetry field
///   (`mode`/`rag_mode`/`fallback_mode`, `retrieval*`, `retrieved_ids`,
///   `source_errors`, `policy*`, `debug`, `telemetry`, `reasoning*`,
///   `pipeline*`, `fallback*`, …) is removed at **every nesting depth**,
///   leaving only the user-facing content (Requirement 1.6; Property P3).
///
/// Pure: no Flutter dependency, no I/O, no mutation of [envelope].
Map<String, dynamic> endUserSafeProjection(
  Map<String, dynamic> envelope, {
  required bool isAdmin,
}) {
  if (isAdmin) {
    return (_deepCopy(envelope) as Map).cast<String, dynamic>();
  }
  return (_stripInternal(envelope) as Map).cast<String, dynamic>();
}

/// Convenience: the role unlocking full (admin) detail. Reuses the single
/// definition of the admin role from the telemetry gate so the two surfaces
/// can never disagree on what counts as `admin`.
bool isAdminRole(String? role) => role?.trim().toLowerCase() == kAdminRole;

// -----------------------------------------------------------------------------
// A single citation/source reference (title + optional url/source).
// -----------------------------------------------------------------------------

/// A user-facing citation extracted from an answer envelope. Only a label and
/// an optional url are exposed — never connector identifiers or runtime detail.
@immutable
class AnswerCitation {
  const AnswerCitation({required this.label, this.url});

  final String label;
  final String? url;
}

/// Extracts a user-facing answer string from a (projected) [envelope].
///
/// Prefers `reply`, then `answer`, then `text`/`content`. The chat envelope's
/// `message` field echoes the *user's* prompt, so it is intentionally **not**
/// treated as the assistant answer.
String extractAnswerText(Map<String, dynamic> envelope) {
  for (final key in const <String>['reply', 'answer', 'text', 'content']) {
    final value = envelope[key];
    if (value is String && value.trim().isNotEmpty) {
      return value.trim();
    }
  }
  return '';
}

/// Extracts user-facing citations from a (projected) [envelope]. Looks at
/// `citations` then `sources`; each entry may be a string or a map carrying a
/// `title`/`name`/`source`/`label` and an optional `url`.
List<AnswerCitation> extractCitations(Map<String, dynamic> envelope) {
  final out = <AnswerCitation>[];
  for (final key in const <String>['citations', 'sources']) {
    final raw = envelope[key];
    if (raw is! List) continue;
    for (final item in raw) {
      if (item is String) {
        final label = item.trim();
        if (label.isNotEmpty) out.add(AnswerCitation(label: label));
      } else if (item is Map) {
        final map = item.cast<String, dynamic>();
        final label = (map['title'] ??
                map['name'] ??
                map['source'] ??
                map['label'] ??
                map['url'])
            ?.toString()
            .trim();
        if (label != null && label.isNotEmpty) {
          final url = map['url']?.toString().trim();
          out.add(AnswerCitation(
            label: label,
            url: (url != null && url.isNotEmpty) ? url : null,
          ));
        }
      }
    }
    if (out.isNotEmpty) break; // first non-empty list wins (citations > sources)
  }
  return out;
}

// -----------------------------------------------------------------------------
// Widget
// -----------------------------------------------------------------------------

/// Default Vietnamese-first standing medical disclaimer (Requirement 1.4).
const String _kDisclaimerVi =
    'Thông tin chỉ mang tính hỗ trợ quyết định, không thay thế tư vấn của '
    'bác sĩ. Hãy trao đổi với nhân viên y tế có chuyên môn.';
const String _kDisclaimerEn =
    'This information supports decisions only and does not replace a doctor. '
    'Please review with a licensed clinician.';

/// Renders an answer envelope as End_User-safe content.
///
/// Non-admin roles see only the sanitized answer text (passed through
/// `stripTelemetryLabels`), its citations, and the standing disclaimer — never
/// any internal runtime field. An `admin` role additionally sees the full,
/// unredacted envelope detail in an expandable section.
class EndUserSafeAnswer extends StatelessWidget {
  const EndUserSafeAnswer({
    super.key,
    required this.envelope,
    this.role,
    this.isEnglish = false,
    this.showDisclaimer = true,
  });

  /// The raw answer envelope returned by CLARA_API.
  final Map<String, dynamic> envelope;

  /// The authenticated user's role; `admin` unlocks full detail.
  final String? role;

  /// Vietnamese-first by default; pass `true` for English copy.
  final bool isEnglish;

  /// Whether to render the standing medical disclaimer (Requirement 1.4).
  final bool showDisclaimer;

  bool get _isAdmin => isAdminRole(role);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final projected = endUserSafeProjection(envelope, isAdmin: _isAdmin);

    // User-facing answer text is always sanitized of internal labels (P4).
    final answer = stripTelemetryLabels(extractAnswerText(projected));
    final citations = extractCitations(projected);

    final children = <Widget>[
      if (answer.isNotEmpty)
        Semantics(
          label: answer,
          child: Text(answer, style: theme.textTheme.bodyMedium),
        )
      else
        Text(
          isEnglish ? '(No answer text)' : '(Chưa có nội dung trả lời)',
          style: theme.textTheme.bodyMedium
              ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
      if (citations.isNotEmpty) ...[
        const SizedBox(height: 12),
        _CitationList(citations: citations, isEnglish: isEnglish),
      ],
      if (showDisclaimer) ...[
        const SizedBox(height: 12),
        _Disclaimer(isEnglish: isEnglish),
      ],
      if (_isAdmin) ...[
        const SizedBox(height: 12),
        _AdminDetail(envelope: projected, isEnglish: isEnglish),
      ],
    ];

    return Column(
      key: const Key('end-user-safe-answer'),
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: children,
    );
  }
}

class _CitationList extends StatelessWidget {
  const _CitationList({required this.citations, required this.isEnglish});

  final List<AnswerCitation> citations;
  final bool isEnglish;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final heading = isEnglish
        ? 'References (${citations.length})'
        : 'Nguồn tham khảo (${citations.length})';
    return Column(
      key: const Key('end-user-safe-citations'),
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          heading,
          style: theme.textTheme.labelSmall
              ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
        const SizedBox(height: 4),
        for (var i = 0; i < citations.length; i++)
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Semantics(
              label: '[${i + 1}] ${citations[i].label}',
              child: Text(
                '[${i + 1}] ${citations[i].label}',
                style: theme.textTheme.bodySmall,
              ),
            ),
          ),
      ],
    );
  }
}

class _Disclaimer extends StatelessWidget {
  const _Disclaimer({required this.isEnglish});

  final bool isEnglish;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final text = isEnglish ? _kDisclaimerEn : _kDisclaimerVi;
    return Semantics(
      label: text,
      child: Container(
        key: const Key('end-user-safe-disclaimer'),
        constraints: const BoxConstraints(minHeight: kMinTouchTarget),
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ExcludeSemantics(
              child: Icon(Icons.info_outline,
                  size: 16, color: theme.colorScheme.onSurfaceVariant),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                text,
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Admin-only expandable view of the full (unredacted) envelope detail.
class _AdminDetail extends StatelessWidget {
  const _AdminDetail({required this.envelope, required this.isEnglish});

  final Map<String, dynamic> envelope;
  final bool isEnglish;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final entries = envelope.entries.toList()
      ..sort((a, b) => a.key.compareTo(b.key));
    return ExpansionTile(
      key: const Key('end-user-safe-admin-detail'),
      tilePadding: EdgeInsets.zero,
      title: Text(
        isEnglish ? 'Full detail (admin)' : 'Chi tiết đầy đủ (quản trị)',
        style: theme.textTheme.labelMedium,
      ),
      children: [
        for (final entry in entries)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(
                '${entry.key}: ${entry.value}',
                style: theme.textTheme.bodySmall,
              ),
            ),
          ),
      ],
    );
  }
}

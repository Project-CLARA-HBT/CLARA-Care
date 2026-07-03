// Hidden-by-default research telemetry panel for CLARA_Mobile.
//
// CLARA Pro (deep_beta) and Deep answers used to inline their technical
// artifacts — verification/claim matrices, multi-pass retrieval logs, reasoning
// nodes, and source dumps — directly in the answer body, which made the prose
// long, rigid, and mixed-language. The ML pipeline now keeps the answer body as
// clean explanatory prose and ships that technical material separately in the
// response envelope. This widget renders it in a COLLAPSED-by-default panel so
// the End_User sees a clean answer, and anyone who wants the details can expand.
//
// It reads only from the fields the envelope already carries and shows nothing
// when there is no telemetry (so fast/simple answers render no panel at all):
//   * citations / sources        → reference list
//   * verification_matrix.summary → supported/unsupported/contradicted counts
//   * reasoning_steps / parallel_reasoning_nodes → reasoning trace
//   * context_debug.source_used / source_attempts → sources consulted
//
// Vietnamese-first. Pure presentational: no network, no PII beyond what the
// answer already surfaced.

import 'package:flutter/material.dart';

/// Extracts a display list of source/citation titles from the envelope.
List<_TelemetrySource> _extractSources(Map<String, dynamic> envelope) {
  final raw = envelope['citations'] ?? envelope['sources'];
  final out = <_TelemetrySource>[];
  if (raw is List) {
    for (final item in raw) {
      if (item is String && item.trim().isNotEmpty) {
        out.add(_TelemetrySource(title: item.trim()));
      } else if (item is Map) {
        final map = item.cast<String, dynamic>();
        final title =
            (map['title'] ?? map['name'] ?? map['source'] ?? map['url'])
                ?.toString()
                .trim();
        if (title != null && title.isNotEmpty) {
          out.add(_TelemetrySource(
            title: title,
            url: map['url']?.toString(),
            source: map['source']?.toString(),
          ));
        }
      }
    }
  }
  return out;
}

/// Extracts the verification-matrix summary counts, when present.
_VerificationSummary? _extractVerification(Map<String, dynamic> envelope) {
  Object? matrix = envelope['verification_matrix'];
  if (matrix is! Map) {
    final verification = envelope['verification'];
    if (verification is Map) {
      matrix = verification['verification_matrix'];
    }
  }
  if (matrix is! Map) return null;
  final summary = matrix['summary'];
  final map = summary is Map
      ? summary.cast<String, dynamic>()
      : matrix.cast<String, dynamic>();

  int asInt(Object? v) {
    if (v is int) return v;
    if (v is num) return v.toInt();
    if (v is List) return v.length;
    return int.tryParse('${v ?? ''}') ?? 0;
  }

  final supported = asInt(map['supported_claims'] ?? map['supported']);
  final unsupported = asInt(map['unsupported_claims'] ?? map['unsupported']);
  final contradicted = asInt(map['contradicted_claims'] ?? map['contradicted']);
  final total = asInt(map['total_claims'] ?? map['total']);
  if (supported == 0 && unsupported == 0 && contradicted == 0 && total == 0) {
    return null;
  }
  return _VerificationSummary(
    supported: supported,
    unsupported: unsupported,
    contradicted: contradicted,
    total: total,
  );
}

/// Extracts a compact reasoning trace (node/step labels) from the envelope.
List<String> _extractReasoning(Map<String, dynamic> envelope) {
  final out = <String>[];
  void addFrom(Object? raw) {
    if (raw is! List) return;
    for (final item in raw) {
      if (item is Map) {
        final map = item.cast<String, dynamic>();
        final label = (map['node'] ??
                map['stage'] ??
                map['step'] ??
                map['label'] ??
                map['title'])
            ?.toString()
            .trim();
        final status = (map['status'] ?? '').toString().trim();
        if (label != null && label.isNotEmpty) {
          out.add(status.isEmpty ? label : '$label — $status');
        }
      } else if (item is String && item.trim().isNotEmpty) {
        out.add(item.trim());
      }
    }
  }

  addFrom(envelope['parallel_reasoning_nodes']);
  if (out.isEmpty) addFrom(envelope['reasoning_steps']);
  return out;
}

/// A collapsed-by-default panel exposing the technical telemetry that backs a
/// research answer. Renders nothing when there is no telemetry to show.
class ResearchTelemetryPanel extends StatelessWidget {
  const ResearchTelemetryPanel({
    super.key,
    required this.envelope,
    this.initiallyExpanded = false,
  });

  /// The normalized answer envelope (chat/research result map).
  final Map<String, dynamic> envelope;
  final bool initiallyExpanded;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sources = _extractSources(envelope);
    final verification = _extractVerification(envelope);
    final reasoning = _extractReasoning(envelope);

    // Nothing to show ⇒ render nothing (fast/simple answers stay clean).
    if (sources.isEmpty && verification == null && reasoning.isEmpty) {
      return const SizedBox.shrink();
    }

    final children = <Widget>[];
    if (verification != null) {
      children.add(_SectionLabel(
        icon: Icons.verified_outlined,
        label: 'Kiểm chứng bằng chứng',
      ));
      children.add(_VerificationChips(summary: verification));
      children.add(const SizedBox(height: 12));
    }
    if (reasoning.isNotEmpty) {
      children.add(_SectionLabel(
        icon: Icons.account_tree_outlined,
        label: 'Chuỗi suy luận',
      ));
      for (final step in reasoning.take(20)) {
        children.add(Padding(
          padding: const EdgeInsets.only(left: 4, top: 2, bottom: 2),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.only(top: 2, right: 6),
                child: Icon(Icons.chevron_right, size: 16),
              ),
              Expanded(
                child: Text(step, style: theme.textTheme.bodySmall),
              ),
            ],
          ),
        ));
      }
      children.add(const SizedBox(height: 12));
    }
    if (sources.isNotEmpty) {
      children.add(_SectionLabel(
        icon: Icons.link_outlined,
        label: 'Nguồn tham khảo (${sources.length})',
      ));
      for (final s in sources.take(40)) {
        children.add(Padding(
          padding: const EdgeInsets.symmetric(vertical: 3),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.only(top: 2, right: 6),
                child: Icon(Icons.article_outlined, size: 15),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(s.title, style: theme.textTheme.bodySmall),
                    if (s.url != null && s.url!.isNotEmpty)
                      Text(
                        s.url!,
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.primary,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                  ],
                ),
              ),
            ],
          ),
        ));
      }
    }

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Theme(
        // Remove the divider lines for a cleaner embedded look.
        data: theme.copyWith(dividerColor: Colors.transparent),
        child: Container(
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainerHighest
                .withValues(alpha: 0.4),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: theme.colorScheme.outlineVariant.withValues(alpha: 0.5),
            ),
          ),
          clipBehavior: Clip.antiAlias,
          child: ExpansionTile(
            initiallyExpanded: initiallyExpanded,
            tilePadding: const EdgeInsets.symmetric(horizontal: 12),
            childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
            leading: const Icon(Icons.insights_outlined, size: 20),
            title: Text(
              'Chi tiết kỹ thuật',
              style: theme.textTheme.labelLarge,
            ),
            subtitle: Text(
              'Kiểm chứng, suy luận & nguồn',
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: children,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 6, top: 2),
      child: Row(
        children: [
          Icon(icon, size: 16, color: theme.colorScheme.primary),
          const SizedBox(width: 6),
          Text(
            label,
            style: theme.textTheme.labelMedium?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _VerificationChips extends StatelessWidget {
  const _VerificationChips({required this.summary});

  final _VerificationSummary summary;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    Widget chip(String label, int value, Color color) => Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.10),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: color.withValues(alpha: 0.24)),
          ),
          child: Text(
            '$label: $value',
            style: theme.textTheme.labelSmall?.copyWith(
              color: theme.colorScheme.onSurface,
              fontWeight: FontWeight.w600,
            ),
          ),
        );

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        if (summary.total > 0)
          chip('Tổng claim', summary.total, theme.colorScheme.primary),
        chip('Được hỗ trợ', summary.supported, Colors.green.shade700),
        if (summary.unsupported > 0)
          chip('Chưa đủ bằng chứng', summary.unsupported,
              Colors.orange.shade800),
        if (summary.contradicted > 0)
          chip('Mâu thuẫn', summary.contradicted, theme.colorScheme.error),
      ],
    );
  }
}

class _TelemetrySource {
  const _TelemetrySource({required this.title, this.url, this.source});

  final String title;
  final String? url;
  final String? source;
}

class _VerificationSummary {
  const _VerificationSummary({
    required this.supported,
    required this.unsupported,
    required this.contradicted,
    required this.total,
  });

  final int supported;
  final int unsupported;
  final int contradicted;
  final int total;
}

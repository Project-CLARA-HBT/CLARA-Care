// Accessible review summary for focused CLARA mobile flows.
//
// The section deliberately accepts display-ready, user-safe strings rather
// than domain objects or exceptions. This keeps transport errors, internal
// identifiers, and model/provider details out of the presentation primitive.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../tokens.dart';

/// Meaning of a review value.
///
/// The meaning is always rendered as text and an icon; color is decorative.
enum ClaraReviewValueKind {
  entered,
  source,
  aiDraft,
  unknown,
  conflict,
}

/// One label/value pair shown in a [ClaraReviewSection].
@immutable
class ClaraReviewItem {
  const ClaraReviewItem({
    required this.label,
    required this.value,
    required this.kindLabel,
    this.kind = ClaraReviewValueKind.entered,
    this.supportingText,
  });

  /// Short field label, such as "Tên thuốc".
  final String label;

  /// Display-ready value. Callers must not pass secrets or raw errors.
  final String value;

  /// Localized, visible description of [kind], such as "Bạn đã nhập".
  final String kindLabel;

  final ClaraReviewValueKind kind;

  /// Optional user-safe explanation or provenance note.
  final String? supportingText;
}

/// A focused, semantic review card used before an authoritative commit.
///
/// It contains one heading, optional context, a sequence of review items, an
/// optional edit action, and optional supplementary content. It performs no
/// I/O and intentionally has no API for exceptions or raw upstream errors.
class ClaraReviewSection extends StatelessWidget {
  const ClaraReviewSection({
    super.key,
    required this.title,
    required this.items,
    this.description,
    this.editLabel,
    this.onEdit,
    this.child,
  }) : assert(
          (editLabel == null) == (onEdit == null),
          'editLabel and onEdit must be supplied together',
        );

  final String title;
  final String? description;
  final List<ClaraReviewItem> items;

  /// Localized edit-action label. Must be paired with [onEdit].
  final String? editLabel;
  final VoidCallback? onEdit;

  /// Optional supplementary review content placed after [items].
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final textScaler = A11y.resolveTextScaler(context);

    return Semantics(
      container: true,
      explicitChildNodes: true,
      label: title,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: scheme.surface,
          border: Border.all(color: scheme.outlineVariant),
          borderRadius: BorderRadius.circular(ClaraTokens.radiusLg),
          boxShadow: <BoxShadow>[
            BoxShadow(
              color: scheme.shadow.withValues(alpha: 0.08),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.all(ClaraTokens.spaceMd),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Semantics(
                          header: true,
                          child: Text(
                            title,
                            style: theme.textTheme.titleMedium,
                            textScaler: textScaler,
                          ),
                        ),
                        if (description != null) ...<Widget>[
                          const SizedBox(height: ClaraTokens.spaceXs),
                          Text(
                            description!,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: scheme.onSurfaceVariant,
                            ),
                            textScaler: textScaler,
                          ),
                        ],
                      ],
                    ),
                  ),
                  if (onEdit != null) ...<Widget>[
                    const SizedBox(width: ClaraTokens.spaceSm),
                    Semantics(
                      button: true,
                      label: editLabel,
                      child: ExcludeSemantics(
                        child: TextButton(
                          onPressed: onEdit,
                          style: const ButtonStyle(
                            minimumSize: WidgetStatePropertyAll(
                              Size(
                                A11y.minTapTargetDimension,
                                A11y.minTapTargetDimension,
                              ),
                            ),
                          ),
                          child: Text(editLabel!),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
              if (items.isNotEmpty) ...<Widget>[
                const SizedBox(height: ClaraTokens.spaceMd),
                for (var index = 0; index < items.length; index++) ...<Widget>[
                  if (index > 0)
                    Divider(
                        height: ClaraTokens.spaceLg,
                        color: scheme.outlineVariant),
                  _ReviewItemRow(item: items[index]),
                ],
              ],
              if (child != null) ...<Widget>[
                const SizedBox(height: ClaraTokens.spaceMd),
                child!,
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ReviewItemRow extends StatelessWidget {
  const _ReviewItemRow({required this.item});

  final ClaraReviewItem item;

  (IconData, Color, Color) _visuals(ColorScheme scheme) {
    switch (item.kind) {
      case ClaraReviewValueKind.entered:
        return (
          Icons.edit_note_outlined,
          scheme.onPrimaryContainer,
          scheme.primaryContainer,
        );
      case ClaraReviewValueKind.source:
        return (
          Icons.source_outlined,
          scheme.onSecondaryContainer,
          scheme.secondaryContainer,
        );
      case ClaraReviewValueKind.aiDraft:
        return (
          Icons.auto_awesome_outlined,
          scheme.onTertiaryContainer,
          scheme.tertiaryContainer,
        );
      case ClaraReviewValueKind.unknown:
        return (
          Icons.help_outline,
          scheme.onSurfaceVariant,
          scheme.surfaceContainerHighest,
        );
      case ClaraReviewValueKind.conflict:
        return (
          Icons.compare_arrows_outlined,
          scheme.onErrorContainer,
          scheme.errorContainer,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final textScaler = A11y.resolveTextScaler(context);
    final (icon, foreground, background) = _visuals(scheme);
    final supporting = item.supportingText?.trim();

    return Semantics(
      container: true,
      excludeSemantics: true,
      label: '${item.label}: ${item.value}. ${item.kindLabel}'
          '${supporting == null || supporting.isEmpty ? '' : '. $supporting'}',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            item.label,
            style: theme.textTheme.bodySmall?.copyWith(
              color: scheme.onSurfaceVariant,
            ),
            textScaler: textScaler,
          ),
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(
            item.value,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: scheme.onSurface,
              fontWeight: FontWeight.w600,
            ),
            textScaler: textScaler,
          ),
          const SizedBox(height: ClaraTokens.spaceSm),
          DecoratedBox(
            decoration: BoxDecoration(
              color: background,
              borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: ClaraTokens.spaceSm,
                vertical: ClaraTokens.spaceXs,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Icon(icon, size: 18, color: foreground),
                  const SizedBox(width: ClaraTokens.spaceXs),
                  Flexible(
                    child: Text(
                      item.kindLabel,
                      style: theme.textTheme.labelMedium?.copyWith(
                        color: foreground,
                        fontWeight: FontWeight.w600,
                      ),
                      textScaler: textScaler,
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (supporting != null && supporting.isNotEmpty) ...<Widget>[
            const SizedBox(height: ClaraTokens.spaceSm),
            Text(
              supporting,
              style: theme.textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
              textScaler: textScaler,
            ),
          ],
        ],
      ),
    );
  }
}

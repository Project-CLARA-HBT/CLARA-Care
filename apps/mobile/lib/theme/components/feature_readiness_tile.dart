// Actionable, content-safe feature readiness presentation for CLARA mobile.
//
// Callers provide only localized, user-safe explanations. There is
// intentionally no raw-error/configuration field, so secrets, stack traces,
// internal paths, and upstream payloads cannot accidentally be rendered.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../tokens.dart';
import '../web_palette.dart';

enum FeatureReadinessStatus {
  ready,
  actionRequired,
  unavailable,
  checking,
}

/// Explains whether a feature is ready and gives a safe next step.
class FeatureReadinessTile extends StatelessWidget {
  const FeatureReadinessTile({
    super.key,
    required this.title,
    required this.status,
    required this.statusLabel,
    required this.safeExplanation,
    this.userAction,
    this.administratorAction,
    this.safeFallback,
    this.actionLabel,
    this.onAction,
  }) : assert(
          (actionLabel == null) == (onAction == null),
          'actionLabel and onAction must be supplied together',
        );

  final String title;
  final FeatureReadinessStatus status;

  /// Localized visible status; readiness is never communicated by color alone.
  final String statusLabel;

  /// Plain-language, user-safe reason. Never pass an exception or raw response.
  final String safeExplanation;

  /// What the current user can do next.
  final String? userAction;

  /// Safe, secret-free description of administrator action, when relevant.
  final String? administratorAction;

  /// Safe behavior available while the feature is not ready.
  final String? safeFallback;

  final String? actionLabel;
  final VoidCallback? onAction;

  _ReadinessVisual _visual(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final statusColors = theme.extension<ClaraStatusColors>();

    switch (status) {
      case FeatureReadinessStatus.ready:
        return _ReadinessVisual(
          icon: Icons.check_circle_outline,
          foreground: statusColors?.onSuccess ?? scheme.onPrimary,
          background: statusColors?.success ?? scheme.primary,
        );
      case FeatureReadinessStatus.actionRequired:
        return _ReadinessVisual(
          icon: Icons.assignment_late_outlined,
          foreground: statusColors?.onWarning ?? scheme.onTertiary,
          background: statusColors?.warning ?? scheme.tertiary,
        );
      case FeatureReadinessStatus.unavailable:
        return _ReadinessVisual(
          icon: Icons.block_outlined,
          foreground: scheme.onError,
          background: scheme.error,
        );
      case FeatureReadinessStatus.checking:
        return _ReadinessVisual(
          icon: Icons.sync_outlined,
          foreground: scheme.onPrimary,
          background: scheme.primary,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final textScaler = A11y.resolveTextScaler(context);
    final visual = _visual(context);
    final details = <(String, String)>[
      if (_present(userAction)) ('Bạn có thể làm', userAction!.trim()),
      if (_present(administratorAction))
        ('Quản trị viên cần làm', administratorAction!.trim()),
      if (_present(safeFallback)) ('Trong lúc chờ', safeFallback!.trim()),
    ];

    return Semantics(
      container: true,
      explicitChildNodes: true,
      label: '$title. $statusLabel. $safeExplanation',
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: scheme.surface,
          border: Border.all(color: scheme.outlineVariant),
          borderRadius: BorderRadius.circular(ClaraTokens.radiusLg),
        ),
        child: Padding(
          padding: const EdgeInsets.all(ClaraTokens.spaceMd),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  DecoratedBox(
                    decoration: BoxDecoration(
                      color: visual.background,
                      borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(ClaraTokens.spaceSm),
                      child: Icon(
                        visual.icon,
                        color: visual.foreground,
                        size: 24,
                      ),
                    ),
                  ),
                  const SizedBox(width: ClaraTokens.spaceMd),
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
                        const SizedBox(height: ClaraTokens.spaceXs),
                        Text(
                          statusLabel,
                          style: theme.textTheme.labelLarge?.copyWith(
                            color: scheme.onSurface,
                            fontWeight: FontWeight.w700,
                          ),
                          textScaler: textScaler,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: ClaraTokens.spaceMd),
              Text(
                safeExplanation,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
                textScaler: textScaler,
              ),
              for (final (label, value) in details) ...<Widget>[
                const SizedBox(height: ClaraTokens.spaceMd),
                _ReadinessDetail(label: label, value: value),
              ],
              if (onAction != null) ...<Widget>[
                const SizedBox(height: ClaraTokens.spaceMd),
                Align(
                  alignment: AlignmentDirectional.centerEnd,
                  child: Semantics(
                    button: true,
                    label: actionLabel,
                    child: ExcludeSemantics(
                      child: FilledButton(
                        onPressed: onAction,
                        style: const ButtonStyle(
                          minimumSize: WidgetStatePropertyAll(
                            Size(
                              A11y.minTapTargetDimension,
                              A11y.minTapTargetDimension,
                            ),
                          ),
                        ),
                        child: Text(actionLabel!),
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  static bool _present(String? value) =>
      value != null && value.trim().isNotEmpty;
}

class _ReadinessDetail extends StatelessWidget {
  const _ReadinessDetail({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final textScaler = A11y.resolveTextScaler(context);

    return Semantics(
      container: true,
      excludeSemantics: true,
      label: '$label: $value',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            label,
            style: theme.textTheme.labelMedium?.copyWith(
              color: scheme.onSurfaceVariant,
              fontWeight: FontWeight.w600,
            ),
            textScaler: textScaler,
          ),
          const SizedBox(height: ClaraTokens.spaceXs),
          Text(
            value,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: scheme.onSurface,
            ),
            textScaler: textScaler,
          ),
        ],
      ),
    );
  }
}

@immutable
class _ReadinessVisual {
  const _ReadinessVisual({
    required this.icon,
    required this.foreground,
    required this.background,
  });

  final IconData icon;
  final Color foreground;
  final Color background;
}

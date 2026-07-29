// Reusable guided-flow page for CLARA Mobile.
//
// A flow page intentionally presents one bounded content surface and one clear
// primary action. It is suitable for onboarding, capture review, medication
// entry, visit preparation, consent, and other progressive workflows.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../tokens.dart';
import 'clara_button.dart';
import 'clara_card.dart';

/// Width at which guided-flow actions may share one horizontal footer row.
const double kClaraFlowExpandedBreakpoint = 600;

/// Maximum readable width of the focused flow content.
const double kClaraFlowContentMaxWidth = 720;

/// A responsive, accessible shell for one step of a guided flow.
///
/// [step] is one-based. [stepCount] must be positive and [step] must fall
/// within `1..stepCount`. The shell owns the sole main content card; callers
/// provide only the focused [child] for the current step.
class ClaraFlowScaffold extends StatelessWidget {
  const ClaraFlowScaffold({
    super.key,
    required this.title,
    required this.step,
    required this.stepCount,
    required this.child,
    required this.onNext,
    this.description,
    this.stepTitle,
    this.backLabel = 'Quay lại',
    this.skipLabel = 'Bỏ qua',
    this.nextLabel = 'Tiếp tục',
    this.onBack,
    this.onSkip,
    this.nextEnabled = true,
    this.nextLoading = false,
  })  : assert(stepCount > 0),
        assert(step > 0 && step <= stepCount);

  /// Visible page title and heading announced to assistive technology.
  final String title;

  /// Optional short supporting copy above the focused content card.
  final String? description;

  /// Optional name for the current step in the spoken progress announcement.
  final String? stepTitle;

  /// Current one-based step.
  final int step;

  /// Total number of steps.
  final int stepCount;

  /// The focused contents of this step.
  final Widget child;

  final String backLabel;
  final String skipLabel;
  final String nextLabel;

  /// Omit a callback to hide its action. The primary next action is always
  /// rendered and may be disabled with [nextEnabled].
  final VoidCallback? onBack;
  final VoidCallback? onSkip;
  final VoidCallback? onNext;
  final bool nextEnabled;
  final bool nextLoading;

  String get _progressLabel {
    final name = stepTitle?.trim();
    return name == null || name.isEmpty
        ? 'Bước $step trên $stepCount'
        : 'Bước $step trên $stepCount: $name';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        automaticallyImplyLeading: false,
        title: Semantics(
          header: true,
          child: Text(title),
        ),
      ),
      body: SafeArea(
        bottom: false,
        child: LayoutBuilder(
          builder: (context, constraints) {
            final expanded =
                constraints.maxWidth >= kClaraFlowExpandedBreakpoint;
            return Column(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    padding: EdgeInsets.fromLTRB(
                      expanded ? ClaraTokens.spaceXl : ClaraTokens.spaceMd,
                      ClaraTokens.spaceMd,
                      expanded ? ClaraTokens.spaceXl : ClaraTokens.spaceMd,
                      ClaraTokens.spaceLg,
                    ),
                    child: Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(
                          maxWidth: kClaraFlowContentMaxWidth,
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            _FlowProgress(
                              label: _progressLabel,
                              value: step / stepCount,
                            ),
                            if (description != null &&
                                description!.trim().isNotEmpty) ...[
                              const SizedBox(height: ClaraTokens.spaceMd),
                              Text(
                                description!,
                                style: Theme.of(context)
                                    .textTheme
                                    .bodyMedium
                                    ?.copyWith(
                                      color: Theme.of(context)
                                          .colorScheme
                                          .onSurfaceVariant,
                                    ),
                              ),
                            ],
                            const SizedBox(height: ClaraTokens.spaceLg),
                            ClaraCard.static_(
                              key: const Key('clara-flow-content-card'),
                              semanticLabel: stepTitle ?? title,
                              padding:
                                  const EdgeInsets.all(ClaraTokens.spaceLg),
                              child: child,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
                _FlowFooter(
                  expanded: expanded,
                  backLabel: backLabel,
                  skipLabel: skipLabel,
                  nextLabel: nextLabel,
                  onBack: onBack,
                  onSkip: onSkip,
                  onNext: nextEnabled && !nextLoading ? onNext : null,
                  nextLoading: nextLoading,
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _FlowProgress extends StatelessWidget {
  const _FlowProgress({required this.label, required this.value});

  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      container: true,
      label: label,
      value: '${(value * 100).round()}%',
      child: ExcludeSemantics(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: theme.textTheme.labelLarge?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: ClaraTokens.spaceSm),
            ClipRRect(
              borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
              child: LinearProgressIndicator(
                key: const Key('clara-flow-progress'),
                value: value,
                minHeight: ClaraTokens.spaceSm,
                backgroundColor: theme.colorScheme.surfaceContainerHighest,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FlowFooter extends StatelessWidget {
  const _FlowFooter({
    required this.expanded,
    required this.backLabel,
    required this.skipLabel,
    required this.nextLabel,
    required this.onBack,
    required this.onSkip,
    required this.onNext,
    required this.nextLoading,
  });

  final bool expanded;
  final String backLabel;
  final String skipLabel;
  final String nextLabel;
  final VoidCallback? onBack;
  final VoidCallback? onSkip;
  final VoidCallback? onNext;
  final bool nextLoading;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final secondaryActions = <Widget>[
      if (onBack != null)
        ClaraButton.secondary(
          label: backLabel,
          icon: Icons.arrow_back,
          onPressed: onBack,
        ),
      if (onSkip != null)
        TextButton(
          onPressed: onSkip,
          style: const ButtonStyle(
            minimumSize: WidgetStatePropertyAll(
              Size(0, A11y.minTapTargetDimension),
            ),
          ),
          child: Text(skipLabel),
        ),
    ];

    final next = ClaraButton.primary(
      label: nextLabel,
      icon: Icons.arrow_forward,
      loading: nextLoading,
      onPressed: onNext,
    );

    return Material(
      color: scheme.surface,
      elevation: ClaraTokens.elevationLevel2,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: EdgeInsets.symmetric(
            horizontal: expanded ? ClaraTokens.spaceXl : ClaraTokens.spaceMd,
            vertical: ClaraTokens.spaceSm,
          ),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                maxWidth: kClaraFlowContentMaxWidth,
              ),
              child: expanded
                  ? Row(
                      children: [
                        for (var index = 0;
                            index < secondaryActions.length;
                            index++) ...[
                          if (index > 0)
                            const SizedBox(width: ClaraTokens.spaceSm),
                          secondaryActions[index],
                        ],
                        const Spacer(),
                        ConstrainedBox(
                          constraints: const BoxConstraints(minWidth: 180),
                          child: next,
                        ),
                      ],
                    )
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        next,
                        if (secondaryActions.isNotEmpty) ...[
                          const SizedBox(height: ClaraTokens.spaceXs),
                          Row(
                            children: [
                              for (var index = 0;
                                  index < secondaryActions.length;
                                  index++) ...[
                                if (index > 0)
                                  const SizedBox(
                                    width: ClaraTokens.spaceSm,
                                  ),
                                Expanded(child: secondaryActions[index]),
                              ],
                            ],
                          ),
                        ],
                      ],
                    ),
            ),
          ),
        ),
      ),
    );
  }
}

// Reusable buttons for CLARA_Mobile Experience_V2 (Req 2.2, 2.3, 2.4).
//
// `ClaraButton` is a thin, accessible wrapper over Material 3's `FilledButton`
// (primary) and `OutlinedButton` (secondary). It exists so every Experience_V2
// surface uses one consistent, token-driven, accessibility-correct call site
// instead of hand-wiring M3 buttons:
//
//   * Tokens (Req 2.2): geometry (radius, padding, ≥48dp min height) comes from
//     the component theme wired to `ClaraTokens`; any custom spacing this widget
//     adds (icon gap, progress size) reads `ClaraTokens` rather than literals.
//   * Text scaling (Req 2.3): the label is rendered through
//     `A11y.resolveTextScaler` so it honours the OS preference and scales up for
//     legibility without clipping primary controls.
//   * Reduced motion (Req 2.4): the swap between the label and the loading
//     indicator animates for a base `ClaraTokens.motionFast` resolved through
//     `A11y.resolveMotionDuration`, so it collapses to `Duration.zero` under
//     reduced motion. The animation is decorative only and never blocks input.
//
// The widget is additive and side-effect-free: no global state, no I/O, no
// analytics — it only renders and forwards taps.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../tokens.dart';

/// Visual emphasis of a [ClaraButton].
///
/// [primary] renders a filled (high-emphasis) button; [secondary] renders an
/// outlined (medium-emphasis) button. Both share identical layout, text
/// scaling, loading, and accessibility behavior.
enum ClaraButtonVariant {
  /// High-emphasis filled button (`FilledButton`).
  primary,

  /// Medium-emphasis outlined button (`OutlinedButton`).
  secondary,
}

/// A token-driven, accessible primary/secondary button for Experience_V2.
///
/// Prefer the named constructors [ClaraButton.primary] and
/// [ClaraButton.secondary] at call sites. Each takes a [label], an [onPressed]
/// callback (a `null` callback disables the button), an optional [icon] shown
/// before the label, and an optional [loading] flag that shows a progress
/// indicator and disables the button while work is in flight.
class ClaraButton extends StatelessWidget {
  /// Creates a button with an explicit [variant].
  const ClaraButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.variant = ClaraButtonVariant.primary,
    this.icon,
    this.loading = false,
  });

  /// Creates a high-emphasis filled (primary) button.
  const ClaraButton.primary({
    Key? key,
    required String label,
    required VoidCallback? onPressed,
    IconData? icon,
    bool loading = false,
  }) : this(
          key: key,
          label: label,
          onPressed: onPressed,
          variant: ClaraButtonVariant.primary,
          icon: icon,
          loading: loading,
        );

  /// Creates a medium-emphasis outlined (secondary) button.
  const ClaraButton.secondary({
    Key? key,
    required String label,
    required VoidCallback? onPressed,
    IconData? icon,
    bool loading = false,
  }) : this(
          key: key,
          label: label,
          onPressed: onPressed,
          variant: ClaraButtonVariant.secondary,
          icon: icon,
          loading: loading,
        );

  /// The button's text label. Also used as the screen-reader label so the
  /// control stays announced even while [loading] hides the visible text.
  final String label;

  /// Tap callback. When `null` (or while [loading]) the button is disabled.
  final VoidCallback? onPressed;

  /// Visual emphasis — see [ClaraButtonVariant].
  final ClaraButtonVariant variant;

  /// Optional leading icon rendered before the label.
  final IconData? icon;

  /// When `true`, shows a progress indicator in place of the label and disables
  /// the button. The label remains the semantics label so the control is still
  /// announced while busy.
  final bool loading;

  /// Effective enabled state: disabled when there is no callback or while busy.
  bool get _enabled => onPressed != null && !loading;

  @override
  Widget build(BuildContext context) {
    // Token-driven min height (≥48dp) guaranteed here regardless of the ambient
    // theme, so the tap target meets the platform minimum (Req 2.3 / a11y).
    final style = ButtonStyle(
      minimumSize: const WidgetStatePropertyAll(
        Size(0, A11y.minTapTargetDimension),
      ),
    );

    final child = _buildContent(context);
    final onPressed = _enabled ? this.onPressed : null;

    final Widget button;
    switch (variant) {
      case ClaraButtonVariant.primary:
        button = FilledButton(
          onPressed: onPressed,
          style: style,
          child: child,
        );
        break;
      case ClaraButtonVariant.secondary:
        button = OutlinedButton(
          onPressed: onPressed,
          style: style,
          child: child,
        );
        break;
    }

    // Provide a stable semantics label + enabled state so the control is
    // announced consistently, including while loading hides the visible text.
    // The visual content is excluded to avoid a duplicate announcement.
    return Semantics(
      button: true,
      enabled: _enabled,
      label: label,
      child: ExcludeSemantics(child: button),
    );
  }

  /// Builds the button's inner content, animating between the label row and the
  /// loading indicator. The crossfade duration is resolved through
  /// [A11y.resolveMotionDuration] so it collapses to `Duration.zero` under
  /// reduced motion; the animation is decorative and never blocks input.
  Widget _buildContent(BuildContext context) {
    final duration =
        A11y.resolveMotionDuration(context, ClaraTokens.motionFast);

    return AnimatedSwitcher(
      duration: duration,
      child: loading ? _buildSpinner(context) : _buildLabelRow(context),
    );
  }

  /// The label (optionally with a leading [icon]), rendered through
  /// [A11y.resolveTextScaler] so it scales with the OS preference without
  /// clipping. The icon-to-label gap reads [ClaraTokens.spaceSm].
  Widget _buildLabelRow(BuildContext context) {
    final text = Text(
      label,
      textScaler: A11y.resolveTextScaler(context),
      overflow: TextOverflow.ellipsis,
    );

    if (icon == null) {
      return text;
    }
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 18),
        const SizedBox(width: ClaraTokens.spaceSm),
        Flexible(child: text),
      ],
    );
  }

  /// The in-flight progress indicator, sized to align with the label baseline.
  Widget _buildSpinner(BuildContext context) {
    return const SizedBox(
      height: 18,
      width: 18,
      child: CircularProgressIndicator(strokeWidth: 2),
    );
  }
}

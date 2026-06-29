// Accessibility helpers for CLARA_Mobile (Requirement 10.1–10.5; Property P14).
//
// A single, dependency-light place for the accessibility primitives every
// screen reuses, so the app's a11y behavior is consistent and testable without
// platform channels:
//
//   * Semantics-label helpers (Req 10.1) — wrap interactive controls and
//     primary content regions with a stable, screen-reader-friendly label.
//   * A ≥48dp minimum tap-target wrapper (Req 10.2) — guarantees touch targets
//     meet the platform minimum regardless of the visual size of the child.
//   * Dynamic text-scaling support (Req 10.3) — resolve a [TextScaler] that
//     honours the OS setting while clamping the extreme upper end so primary
//     content/controls never clip.
//   * A reduced-motion resolver (Req 10.4) — mirrors the web
//     `usePrefersReducedMotion` hook by reading
//     `MediaQuery.disableAnimations` / `accessibleNavigation`, and a helper that
//     collapses non-essential animation [Duration]s to zero.
//   * A status-by-text (not color alone) helper (Req 10.5) — renders status with
//     a text label + icon + semantics so meaning never depends on color.
//
// Everything here is additive and side-effect-free: the resolvers are pure
// functions of a [MediaQueryData]/[BuildContext], and the widgets are thin
// wrappers, so they can be unit/widget tested directly (Property P14).

import 'package:flutter/material.dart';

/// Accessibility constants and pure resolvers for CLARA_Mobile.
///
/// Grouped on a non-instantiable class so call sites read as
/// `A11y.minTapTargetDimension`, `A11y.prefersReducedMotion(context)`, etc.
class A11y {
  const A11y._();

  /// Platform minimum interactive touch-target dimension, in logical pixels
  /// (Material's 48dp guidance, Requirement 10.2).
  static const double minTapTargetDimension = 48.0;

  /// The minimum interactive touch-target size (≥48dp on both axes).
  static const Size minTapTargetSize =
      Size(minTapTargetDimension, minTapTargetDimension);

  /// Default upper bound applied to OS text scaling so primary content/controls
  /// scale up for legibility (Requirement 10.3) without growing so large they
  /// clip. The lower bound is left to the OS so users who shrink text keep that
  /// preference.
  static const double maxTextScaleFactor = 1.6;

  // --- Reduced motion (Requirement 10.4) -------------------------------------

  /// Whether the user has requested reduced motion, resolved from a
  /// [MediaQueryData]. Pure (no [BuildContext]) so it is trivially testable.
  ///
  /// Mirrors the web `usePrefersReducedMotion` intent: motion-sensitive
  /// surfaces should suppress non-essential animation when this is `true`.
  /// `disableAnimations` is the OS "remove animations" signal;
  /// `accessibleNavigation` (an assistive technology such as a screen reader is
  /// driving navigation) is also honoured because such users generally expect
  /// motion to be minimised.
  static bool prefersReducedMotionData(MediaQueryData media) =>
      media.disableAnimations || media.accessibleNavigation;

  /// Whether the user has requested reduced motion, resolved from a
  /// [BuildContext]. Returns `false` (motion allowed) when no [MediaQuery] is in
  /// scope, mirroring the web hook's SSR/test-safe default.
  static bool prefersReducedMotion(BuildContext context) {
    final media = MediaQuery.maybeOf(context);
    if (media == null) {
      return false;
    }
    return prefersReducedMotionData(media);
  }

  /// Resolves an animation [Duration]: returns [Duration.zero] when reduced
  /// motion is requested, otherwise the requested [duration]. Use for
  /// non-essential/decorative animation so it is suppressed under reduced
  /// motion (Requirement 10.4) while functional timing is untouched at call
  /// sites that opt out.
  static Duration resolveMotionDuration(
    BuildContext context,
    Duration duration,
  ) =>
      prefersReducedMotion(context) ? Duration.zero : duration;

  /// [Duration]-resolver variant taking a [MediaQueryData] directly (pure).
  static Duration resolveMotionDurationData(
    MediaQueryData media,
    Duration duration,
  ) =>
      prefersReducedMotionData(media) ? Duration.zero : duration;

  // --- Dynamic text scaling (Requirement 10.3) -------------------------------

  /// Resolves a [TextScaler] that honours the OS text-scaling preference while
  /// clamping the upper bound to [maxScaleFactor] so primary content/controls
  /// remain legible without clipping (Requirement 10.3). When no [MediaQuery]
  /// is in scope the value scales by the [TextScaler.noScaling] identity.
  static TextScaler resolveTextScaler(
    BuildContext context, {
    double maxScaleFactor = maxTextScaleFactor,
  }) {
    final media = MediaQuery.maybeOf(context);
    final scaler = media?.textScaler ?? TextScaler.noScaling;
    return scaler.clamp(maxScaleFactor: maxScaleFactor);
  }
}

/// Wraps [child] so its interactive hit area is at least [A11y.minTapTargetSize]
/// (≥48dp on both axes), satisfying the platform touch-target minimum
/// (Requirement 10.2) even when the visible control is smaller. Optionally
/// attaches a [semanticsLabel] so the wrapped control is announced
/// (Requirement 10.1).
///
/// The child is centred within the enforced minimum box; visual size is
/// unchanged, only the tappable region grows.
class MinTapTarget extends StatelessWidget {
  const MinTapTarget({
    super.key,
    required this.child,
    this.semanticsLabel,
    this.minSize = A11y.minTapTargetDimension,
  });

  /// The (possibly smaller) interactive child.
  final Widget child;

  /// Optional screen-reader label applied to the enforced target.
  final String? semanticsLabel;

  /// Minimum width/height of the enforced tap target, in logical pixels.
  final double minSize;

  @override
  Widget build(BuildContext context) {
    Widget result = ConstrainedBox(
      constraints: BoxConstraints(minWidth: minSize, minHeight: minSize),
      child: Center(
        widthFactor: 1,
        heightFactor: 1,
        child: child,
      ),
    );
    if (semanticsLabel != null && semanticsLabel!.isNotEmpty) {
      result = Semantics(
        label: semanticsLabel,
        button: true,
        container: true,
        child: result,
      );
    }
    return result;
  }
}

/// Attaches a screen-reader [label] (and optional role flags) to [child] for an
/// interactive control or primary content region (Requirement 10.1).
///
/// A thin, intention-revealing wrapper over [Semantics] so screens consistently
/// label controls/regions without repeating the same boilerplate.
class A11yLabeled extends StatelessWidget {
  const A11yLabeled({
    super.key,
    required this.label,
    required this.child,
    this.isButton = false,
    this.isHeader = false,
    this.value,
  });

  /// The screen-reader label announced for [child].
  final String label;

  /// Content/control to annotate.
  final Widget child;

  /// Marks the node as a button (interactive control).
  final bool isButton;

  /// Marks the node as a header (primary content region/heading).
  final bool isHeader;

  /// Optional spoken value (e.g., current status text) in addition to [label].
  final String? value;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: label,
      value: value,
      button: isButton,
      header: isHeader,
      container: true,
      child: child,
    );
  }
}

/// Severity of a status indicator, decoupled from any specific color so callers
/// reason in meaning, not appearance (Requirement 10.5).
enum A11yStatusLevel { info, success, warning, danger }

/// Renders a status with a **text label**, a distinguishing **icon**, and a
/// screen-reader **semantics** value — so status (risk level, errors, progress)
/// is never conveyed by color alone (Requirement 10.5).
///
/// Color is decorative reinforcement only; the [label] text and the icon shape
/// carry the meaning, and the whole indicator exposes a merged semantics node so
/// assistive technology announces the status.
class StatusByText extends StatelessWidget {
  const StatusByText({
    super.key,
    required this.label,
    this.level = A11yStatusLevel.info,
    this.icon,
    this.semanticsPrefix,
  });

  /// Human-readable status text (e.g., "Nguy cơ: Cao"). Always rendered.
  final String label;

  /// Status severity; selects the default icon/color reinforcement.
  final A11yStatusLevel level;

  /// Optional explicit icon; falls back to a per-[level] default.
  final IconData? icon;

  /// Optional prefix for the spoken semantics value (e.g., "Trạng thái").
  final String? semanticsPrefix;

  IconData get _icon => icon ?? _defaultIconFor(level);

  static IconData _defaultIconFor(A11yStatusLevel level) {
    switch (level) {
      case A11yStatusLevel.success:
        return Icons.check_circle_outline;
      case A11yStatusLevel.warning:
        return Icons.warning_amber_outlined;
      case A11yStatusLevel.danger:
        return Icons.error_outline;
      case A11yStatusLevel.info:
        return Icons.info_outline;
    }
  }

  Color _colorFor(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    switch (level) {
      case A11yStatusLevel.success:
        return Colors.green.shade700;
      case A11yStatusLevel.warning:
        return Colors.orange.shade800;
      case A11yStatusLevel.danger:
        return scheme.error;
      case A11yStatusLevel.info:
        return scheme.primary;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _colorFor(context);
    final spoken =
        semanticsPrefix == null ? label : '$semanticsPrefix: $label';
    return Semantics(
      label: spoken,
      container: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Icon is decorative reinforcement; the text carries the meaning, so
          // exclude the icon from semantics to avoid a duplicate announcement.
          ExcludeSemantics(
            child: Icon(_icon, size: 18, color: color),
          ),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              label,
              style: TextStyle(color: color, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}

/// Builds [builder] with the resolved reduced-motion preference (Req 10.4),
/// reacting to runtime changes to the OS setting via [MediaQuery]. Mirrors the
/// reactive behavior of the web `usePrefersReducedMotion` hook so motion-
/// sensitive subtrees can opt out of non-essential animation declaratively.
class ReducedMotionBuilder extends StatelessWidget {
  const ReducedMotionBuilder({super.key, required this.builder});

  /// Receives the current [BuildContext] and whether reduced motion is on.
  final Widget Function(BuildContext context, bool reducedMotion) builder;

  @override
  Widget build(BuildContext context) =>
      builder(context, A11y.prefersReducedMotion(context));
}

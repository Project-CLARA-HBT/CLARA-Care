// Skeleton placeholders for CLARA_Mobile Experience_V2 loading states
// (Requirement 6.1).
//
// Polished, motion-aware placeholder blocks shown while a data surface is
// in-flight, instead of a bare spinner or a blank screen. A single
// [ClaraSkeleton] box is the primitive; [ClaraSkeletonList] composes several
// rows into a believable list placeholder.
//
// Accessibility & motion:
//   * The shimmer is a *non-essential* animation. Its period is resolved
//     through `A11y.resolveMotionDuration` (seeded from a `ClaraTokens` motion
//     duration), so under reduced motion the duration collapses to
//     `Duration.zero` and the widget renders a calm, static placeholder with no
//     pulsing — never blocking layout or input.
//   * Skeletons are decorative. They expose no interactive semantics; callers
//     that want a screen-reader cue should wrap with an `A11yLabeled`
//     "Đang tải…" region at the surface level.
//
// Sizing/spacing/radius all read from `ClaraTokens` so placeholders match the
// real content they stand in for. Pure UI: no analytics, no I/O, no new
// dependency — the pulse is a plain `AnimationController` + `FadeTransition`.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/tokens.dart';

/// A single shimmering placeholder block sized from [ClaraTokens].
///
/// Renders a rounded, theme-tinted box that gently pulses opacity to signal
/// "content loading here". Under reduced motion (resolved via
/// [A11y.resolveMotionDuration]) the pulse is disabled and a static block is
/// shown instead.
///
/// ```dart
/// const ClaraSkeleton(width: 160, height: 20); // a title placeholder
/// const ClaraSkeleton.circle(diameter: 40);     // an avatar placeholder
/// ```
class ClaraSkeleton extends StatefulWidget {
  const ClaraSkeleton({
    super.key,
    this.width,
    this.height = ClaraTokens.spaceMd,
    this.borderRadius,
    this.shape = BoxShape.rectangle,
  });

  /// Convenience constructor for a circular placeholder (e.g., an avatar).
  const ClaraSkeleton.circle({Key? key, required double diameter})
      : this(
          key: key,
          width: diameter,
          height: diameter,
          shape: BoxShape.circle,
        );

  /// Logical width; when null the block expands to the available width.
  final double? width;

  /// Logical height of the block.
  final double height;

  /// Corner radius for rectangular blocks; defaults to [ClaraTokens.radiusSm].
  /// Ignored when [shape] is [BoxShape.circle].
  final BorderRadius? borderRadius;

  /// Block shape; circles ignore [borderRadius].
  final BoxShape shape;

  @override
  State<ClaraSkeleton> createState() => _ClaraSkeletonState();
}

class _ClaraSkeletonState extends State<ClaraSkeleton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    // BASE shimmer period; resolved against reduced motion in `build` so the
    // controller only animates when motion is allowed.
    duration: ClaraTokens.motionSlow,
  );

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _syncAnimation(BuildContext context) {
    // Collapse the shimmer to a static block under reduced motion; otherwise
    // run a continuous, gentle opacity pulse.
    final resolved =
        A11y.resolveMotionDuration(context, ClaraTokens.motionSlow);
    if (resolved == Duration.zero) {
      if (_controller.isAnimating) {
        _controller.stop();
      }
      _controller.value = 1.0; // steady, fully-resting opacity
    } else {
      _controller.duration = resolved;
      if (!_controller.isAnimating) {
        _controller.repeat(reverse: true);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    _syncAnimation(context);

    final scheme = Theme.of(context).colorScheme;
    final baseColor = scheme.surfaceContainerHighest;
    final radius = widget.shape == BoxShape.circle
        ? null
        : (widget.borderRadius ??
            BorderRadius.circular(ClaraTokens.radiusSm));

    final block = DecoratedBox(
      decoration: BoxDecoration(
        color: baseColor,
        shape: widget.shape,
        borderRadius: radius,
      ),
      child: SizedBox(width: widget.width, height: widget.height),
    );

    // Decorative only: hide from assistive tech so it is not announced.
    return ExcludeSemantics(
      child: FadeTransition(
        // Pulse between a faint and a stronger opacity; when static (reduced
        // motion) the controller rests at 1.0 → a calm, fully-opaque block.
        opacity: Tween<double>(begin: 0.45, end: 1.0).animate(
          CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
        ),
        child: block,
      ),
    );
  }
}

/// A vertical list of [ClaraSkeleton] rows that stands in for a loading list
/// (Requirement 6.1).
///
/// Each row pairs an optional circular leading placeholder with two stacked
/// line placeholders (a "title" and a "subtitle"), spaced with [ClaraTokens].
///
/// ```dart
/// const ClaraSkeletonList(itemCount: 5); // 5 placeholder rows
/// ```
class ClaraSkeletonList extends StatelessWidget {
  const ClaraSkeletonList({
    super.key,
    this.itemCount = 3,
    this.showLeading = true,
    this.padding = const EdgeInsets.all(ClaraTokens.spaceMd),
  });

  /// Number of placeholder rows to render.
  final int itemCount;

  /// Whether each row shows a circular leading placeholder (e.g., an avatar).
  final bool showLeading;

  /// Outer padding around the list of rows.
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      child: Padding(
        padding: padding,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: List<Widget>.generate(
            itemCount,
            (_) => Padding(
              padding: const EdgeInsets.symmetric(
                vertical: ClaraTokens.spaceSm,
              ),
              child: _SkeletonRow(showLeading: showLeading),
            ),
          ),
        ),
      ),
    );
  }
}

/// One placeholder row: optional avatar + two stacked line placeholders.
class _SkeletonRow extends StatelessWidget {
  const _SkeletonRow({this.showLeading = true});

  /// Whether to render the circular leading placeholder.
  final bool showLeading;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        if (showLeading) ...const [
          ClaraSkeleton.circle(diameter: 40),
          SizedBox(width: ClaraTokens.spaceMd),
        ],
        const Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              ClaraSkeleton(width: 180, height: 16),
              SizedBox(height: ClaraTokens.spaceSm),
              ClaraSkeleton(height: 12),
            ],
          ),
        ),
      ],
    );
  }
}

// Micro-interactions & transitions for CLARA_Mobile Experience_V2
// (Requirement 7.1, 7.3).
//
// Tasteful, accessible motion primitives shared across Experience_V2 surfaces:
//
//   * [ClaraPageTransitionsBuilder] — a fade-through / shared-axis style route
//     transition for `PageTransitionsTheme`. It combines a gentle fade with a
//     small vertical slide. Under reduced motion it collapses to *no*
//     transition (the incoming page appears instantly), and it is built from
//     `FadeTransition`/`SlideTransition` only — never a modal barrier — so user
//     input is never blocked while a route animates.
//   * [ClaraPressable] — wraps a tappable child (typically a `ClaraCard`) with
//     a subtle scale-down on press for tactile feedback. The animation duration
//     is resolved through `A11y.resolveMotionDuration(context,
//     ClaraTokens.motionFast)`; under reduced motion the scale change is instant
//     (`Duration.zero`) but the tap still fires immediately.
//   * [ClaraListReveal] — a staggered fade + slide-in for list items as a
//     surface first appears. The per-item duration resolves through
//     `A11y.resolveMotionDuration(context, ClaraTokens.motionMedium)`; under
//     reduced motion items appear immediately and interactivity is never
//     delayed (children are laid out and hit-testable from frame one).
//
// Accessibility & motion contract:
//   * Every duration is a *base* `ClaraTokens` value resolved through the shared
//     `A11y` reduced-motion resolver, so `disableAnimations` /
//     `accessibleNavigation` collapse non-essential motion to `Duration.zero`.
//   * Reveal/press effects only animate opacity and transform; they never gate
//     pointer events, so functional state changes remain available regardless of
//     motion preference (Requirement 7.3).
//
// Pure UI: no analytics, no I/O, no new dependency — everything is built from
// stock `flutter/material` animation widgets.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/tokens.dart';

/// A [PageTransitionsBuilder] implementing CLARA_Mobile's fade-through route
/// transition (Requirement 7.1).
///
/// The incoming route fades in while sliding up a short distance; the outgoing
/// route fades out. Under reduced motion — resolved from the route's
/// [BuildContext] via [A11y.prefersReducedMotion] — the transition collapses to
/// no motion and the child is returned directly, so navigation is instant.
///
/// The builder composes only [FadeTransition] and [SlideTransition]; it never
/// introduces a modal barrier or absorbs pointers, so input to the page is
/// never blocked while it animates.
///
/// Wire it into a theme via:
/// ```dart
/// PageTransitionsTheme(builders: {
///   TargetPlatform.android: const ClaraPageTransitionsBuilder(),
///   TargetPlatform.iOS: const ClaraPageTransitionsBuilder(),
/// });
/// ```
class ClaraPageTransitionsBuilder extends PageTransitionsBuilder {
  const ClaraPageTransitionsBuilder();

  @override
  Widget buildTransitions<T>(
    PageRoute<T>? route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) {
    // Collapse to no transition under reduced motion: return the child as-is so
    // the incoming page is shown instantly with no fade or slide.
    if (A11y.prefersReducedMotion(context)) {
      return child;
    }

    final curved = CurvedAnimation(
      parent: animation,
      curve: Curves.easeOutCubic,
      reverseCurve: Curves.easeInCubic,
    );

    return FadeTransition(
      opacity: curved,
      child: SlideTransition(
        position: Tween<Offset>(
          // A short upward slide (8% of the page height) for a fade-through feel.
          begin: const Offset(0, 0.08),
          end: Offset.zero,
        ).animate(curved),
        child: child,
      ),
    );
  }
}

/// Wraps [child] with subtle press feedback: a gentle scale-down while the
/// pointer is held, springing back on release (Requirement 7.1).
///
/// The scale animation duration resolves through
/// [A11y.resolveMotionDuration] seeded from [ClaraTokens.motionFast], so under
/// reduced motion the scale change is instant (`Duration.zero`). Either way the
/// [onTap] callback fires on a normal tap — the feedback never blocks or delays
/// input (Requirement 7.3).
///
/// ```dart
/// ClaraPressable(
///   onTap: () => openTool(),
///   child: const ClaraCard(child: Text('Hồ sơ sức khỏe')),
/// );
/// ```
class ClaraPressable extends StatefulWidget {
  const ClaraPressable({
    super.key,
    required this.child,
    this.onTap,
    this.pressedScale = 0.97,
    this.semanticsLabel,
  });

  /// The content that receives press feedback.
  final Widget child;

  /// Tap handler; when null the widget is inert (no scale, no hit target).
  final VoidCallback? onTap;

  /// Scale applied while pressed (0–1). Defaults to a subtle 0.97.
  final double pressedScale;

  /// Optional screen-reader label; when set the control is announced as a
  /// button.
  final String? semanticsLabel;

  @override
  State<ClaraPressable> createState() => _ClaraPressableState();
}

class _ClaraPressableState extends State<ClaraPressable> {
  bool _pressed = false;

  void _setPressed(bool value) {
    if (_pressed != value) {
      setState(() => _pressed = value);
    }
  }

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onTap != null;
    // Resolve the press duration; collapses to zero (instant) under reduced
    // motion so the scale snaps without animating.
    final duration =
        A11y.resolveMotionDuration(context, ClaraTokens.motionFast);
    final scale = (enabled && _pressed) ? widget.pressedScale : 1.0;

    Widget result = AnimatedScale(
      scale: scale,
      duration: duration,
      curve: Curves.easeOut,
      child: widget.child,
    );

    if (enabled) {
      result = GestureDetector(
        // Opaque so the whole child area is tappable, but this does NOT block
        // input — taps are delivered to onTap and press state is visual only.
        behavior: HitTestBehavior.opaque,
        onTapDown: (_) => _setPressed(true),
        onTapUp: (_) => _setPressed(false),
        onTapCancel: () => _setPressed(false),
        onTap: widget.onTap,
        child: result,
      );
    }

    final label = widget.semanticsLabel;
    if (label != null && label.isNotEmpty) {
      result = Semantics(
        label: label,
        button: enabled,
        container: true,
        child: result,
      );
    }

    return result;
  }
}

/// Staggered fade + slide-in reveal for a list of [children] as a surface first
/// appears (Requirement 7.1).
///
/// Each child animates in with a small delay relative to the previous one,
/// producing a gentle cascade. The base per-item duration resolves through
/// [A11y.resolveMotionDuration] seeded from [ClaraTokens.motionMedium]; under
/// reduced motion every item is shown immediately with no fade, slide, or
/// stagger.
///
/// Interactivity is never delayed: children are always laid out and
/// hit-testable from the first frame — only opacity/offset animate
/// (Requirement 7.3).
///
/// ```dart
/// ClaraListReveal(
///   children: [for (final item in items) ClaraCard(child: Text(item.title))],
/// );
/// ```
class ClaraListReveal extends StatelessWidget {
  const ClaraListReveal({
    super.key,
    required this.children,
    this.spacing = ClaraTokens.spaceMd,
    this.staggerFraction = 0.5,
  });

  /// The items to reveal, top to bottom.
  final List<Widget> children;

  /// Vertical gap inserted between revealed items.
  final double spacing;

  /// Fraction of the per-item duration used as the inter-item delay. A value of
  /// `0.5` means each item starts halfway through the previous item's reveal.
  final double staggerFraction;

  @override
  Widget build(BuildContext context) {
    final base =
        A11y.resolveMotionDuration(context, ClaraTokens.motionMedium);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < children.length; i++) ...[
          if (i > 0) SizedBox(height: spacing),
          claraListRevealItem(
            context,
            index: i,
            baseDuration: base,
            staggerFraction: staggerFraction,
            child: children[i],
          ),
        ],
      ],
    );
  }
}

/// Wraps a single [child] in a one-shot fade + slide-in reveal, offset by
/// [index] for a staggered cascade.
///
/// [baseDuration] is the already-resolved per-item duration (pass the result of
/// [A11y.resolveMotionDuration]). When it is [Duration.zero] (reduced motion)
/// the child is returned directly — shown immediately with no animation and no
/// delayed interactivity.
///
/// Exposed as a standalone helper so callers driving their own
/// `ListView.builder` can reveal items without the [ClaraListReveal] column.
Widget claraListRevealItem(
  BuildContext context, {
  required int index,
  required Duration baseDuration,
  required Widget child,
  double staggerFraction = 0.5,
}) {
  // Reduced motion (or any zero duration): no animation, immediate render.
  if (baseDuration == Duration.zero) {
    return child;
  }

  final delay = baseDuration * (staggerFraction * index);
  return _RevealItem(
    duration: baseDuration,
    delay: delay,
    child: child,
  );
}

/// One-shot fade + upward slide reveal for a single item, after an optional
/// [delay]. Only opacity/offset animate; the child is laid out and
/// hit-testable immediately, so interactivity is never delayed.
class _RevealItem extends StatefulWidget {
  const _RevealItem({
    required this.duration,
    required this.delay,
    required this.child,
  });

  final Duration duration;
  final Duration delay;
  final Widget child;

  @override
  State<_RevealItem> createState() => _RevealItemState();
}

class _RevealItemState extends State<_RevealItem>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: widget.duration,
  );

  late final Animation<double> _opacity = CurvedAnimation(
    parent: _controller,
    curve: Curves.easeOut,
  );

  late final Animation<Offset> _offset = Tween<Offset>(
    begin: const Offset(0, 0.06),
    end: Offset.zero,
  ).animate(_opacity);

  @override
  void initState() {
    super.initState();
    if (widget.delay == Duration.zero) {
      _controller.forward();
    } else {
      Future<void>.delayed(widget.delay, () {
        if (mounted) {
          _controller.forward();
        }
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _opacity,
      child: SlideTransition(
        position: _offset,
        child: widget.child,
      ),
    );
  }
}

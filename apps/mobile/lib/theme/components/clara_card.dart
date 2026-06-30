// ClaraCard — a token-driven surface for CLARA_Mobile Experience_V2
// (Requirements 2.2, 2.3).
//
// A thin, accessible wrapper over Material's [Card] that standardizes the
// modern look: a large rounded radius (`ClaraTokens.radiusLg`), a subtly raised
// resting elevation (`ClaraTokens.elevationLevel1`), and a consistent content
// inset (`ClaraTokens.spaceMd`). It comes in two flavors:
//
//   * Static — a presentational surface (no [onTap]); an optional
//     [semanticLabel] can still group it as a labeled region for screen
//     readers.
//   * Tappable — when [onTap] is provided, the surface becomes an interactive
//     control wrapped in [InkWell] and exposed via `A11yLabeled(isButton: true)`
//     with a *required* [semanticLabel] so assistive technology announces it.
//
// Press feedback (the ink splash) is timed through
// `A11y.resolveMotionDuration(context, ClaraTokens.motionFast)`, so it collapses
// to instant under reduced motion (Requirement 2.4) while the tap itself always
// works. The card honors dynamic text scaling implicitly: it sizes to its
// child and never clips content.
//
// Pure widget: no I/O, no analytics. User-facing labels are Vietnamese-first
// and always supplied by callers (no hard-coded strings here).

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../tokens.dart';

/// A modern, token-driven card surface.
///
/// Use the default constructor for a tappable card (requires [semanticLabel]),
/// or [ClaraCard.static_] for a presentational surface where [semanticLabel] is
/// optional.
class ClaraCard extends StatelessWidget {
  /// Creates a tappable card. [semanticLabel] is required so the interactive
  /// surface is announced by screen readers as a button.
  const ClaraCard({
    super.key,
    required this.child,
    required this.onTap,
    required String this.semanticLabel,
    this.padding,
  });

  /// Creates a static (presentational) card. [semanticLabel] is optional; when
  /// provided it groups the surface as a labeled region for screen readers.
  const ClaraCard.static_({
    super.key,
    required this.child,
    this.semanticLabel,
    this.padding,
  }) : onTap = null;

  /// The card's content. Sized to fit; never clipped.
  final Widget child;

  /// Tap handler. When non-null the card is interactive; when null the card is
  /// a static surface.
  final VoidCallback? onTap;

  /// Screen-reader label. Required for tappable cards (announced as a button),
  /// optional for static cards (announced as a labeled region).
  final String? semanticLabel;

  /// Content inset; defaults to `ClaraTokens.spaceMd` on all sides.
  final EdgeInsetsGeometry? padding;

  /// Whether this card is interactive.
  bool get _isTappable => onTap != null;

  @override
  Widget build(BuildContext context) {
    final shape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(ClaraTokens.radiusLg),
    );
    final resolvedPadding =
        padding ?? const EdgeInsets.all(ClaraTokens.spaceMd);

    final content = Padding(padding: resolvedPadding, child: child);

    final card = Card(
      elevation: ClaraTokens.elevationLevel1,
      shape: shape,
      clipBehavior: Clip.antiAlias,
      margin: EdgeInsets.zero,
      child: _isTappable
          ? InkWell(
              onTap: onTap,
              borderRadius: BorderRadius.circular(ClaraTokens.radiusLg),
              // Press feedback collapses to instant under reduced motion.
              splashColor: null,
              child: AnimatedContainer(
                duration: A11y.resolveMotionDuration(
                  context,
                  ClaraTokens.motionFast,
                ),
                child: content,
              ),
            )
          : content,
    );

    if (_isTappable) {
      return A11yLabeled(
        label: semanticLabel!,
        isButton: true,
        child: card,
      );
    }

    if (semanticLabel != null && semanticLabel!.isNotEmpty) {
      return A11yLabeled(label: semanticLabel!, child: card);
    }

    return card;
  }
}

// GlassSurface — the reusable liquid-glass material for CLARA_Mobile chrome
// (clara-mobile-liquid-glass, R1, R6, R11).
//
// A single widget that renders the iOS-26-inspired "liquid glass" material:
// backdrop blur + translucent fill + specular hairline edge + diagonal sheen +
// soft layered shadow, clipped to a continuous (squircle) corner shape. Chrome
// surfaces (nav/tab bars, floating controls, sheet/app-bar headers, decorative
// cards) are built from this.
//
// Safety-first fallback (R6, R11): the translucent path renders ONLY when the
// ambient [GlassScope] is enabled AND this surface is not marked [clinical].
// Otherwise the EXACT same layout is rendered opaque (solid fill, no
// `BackdropFilter`) with the squircle, border, and shadow preserved — so the
// visual language holds while contrast and performance stay safe. Clinical
// content (chat answers, DDI results, FIDES verdicts, consent copy, dosages)
// must pass `clinical: true` so it is never placed on translucent glass.
//
// Reduced motion (R7): the sheen never animates here; motion is opt-in at call
// sites and always resolved through `A11y.resolveMotionDuration`.

import 'dart:ui';

import 'package:flutter/material.dart';

import 'glass_scope.dart';
import 'glass_tokens.dart';

/// The tint a glass surface fills with, per brightness. Light glass tints white;
/// dark glass tints a deep slate so the material reads as tinted glass, not gray.
Color _glassTint(Brightness brightness) => brightness == Brightness.dark
    ? const Color(0xFF1D2840) // WebPalette.darkSurface
    : const Color(0xFFFFFFFF);

/// Fill "thickness" presets mapping to the token opacities (R1.1, R11.2).
enum GlassFill { thin, regular, thick }

double _fillOpacity(GlassFill fill) {
  switch (fill) {
    case GlassFill.thin:
      return GlassTokens.fillThin;
    case GlassFill.regular:
      return GlassTokens.fillRegular;
    case GlassFill.thick:
      return GlassTokens.fillThick;
  }
}

/// A liquid-glass surface. See file header for the safety-first fallback rules.
class GlassSurface extends StatelessWidget {
  const GlassSurface({
    super.key,
    required this.child,
    this.blurSigma = GlassTokens.blurCard,
    this.radius = GlassTokens.radiusCard,
    this.fill = GlassFill.regular,
    this.padding = EdgeInsets.zero,
    this.clinical = false,
    this.showShadow = true,
    this.showSheen = true,
    this.borderRadiusOverride,
  });

  /// The surface content. For chrome only — never clinical text unless
  /// [clinical] is set (which forces the opaque path).
  final Widget child;

  /// Gaussian blur sigma for the translucent path. Capped at
  /// [GlassTokens.blurMax].
  final double blurSigma;

  /// Outer corner radius (a continuous/squircle shape is derived from it).
  final double radius;

  /// Fill thickness preset.
  final GlassFill fill;

  /// Inner padding around [child].
  final EdgeInsetsGeometry padding;

  /// When true, this surface hosts clinical content and MUST render opaque
  /// (never translucent), regardless of the [GlassScope] (R11).
  final bool clinical;

  /// Whether to paint the soft layered shadow.
  final bool showShadow;

  /// Whether to paint the diagonal sheen highlight (translucent path only).
  final bool showSheen;

  /// Optional explicit border radius (e.g., sheet top-corners-only). When null a
  /// symmetric [radius] is used.
  final BorderRadiusGeometry? borderRadiusOverride;

  @override
  Widget build(BuildContext context) {
    final brightness = Theme.of(context).brightness;
    final glassEnabled = GlassScope.of(context) && !clinical;
    final tint = _glassTint(brightness);

    // Continuous (squircle) shape. `ContinuousRectangleBorder` under-curves, so
    // apply the squircle factor to match Apple's perceived roundness.
    final shape = borderRadiusOverride == null
        ? ContinuousRectangleBorder(
            borderRadius:
                BorderRadius.circular(radius * GlassTokens.squircleFactor),
          )
        : ContinuousRectangleBorder(borderRadius: borderRadiusOverride!);

    final borderColor = (brightness == Brightness.dark
            ? const Color(0xFFFFFFFF)
            : const Color(0xFFFFFFFF))
        .withValues(alpha: glassEnabled ? GlassTokens.borderHairline : 0.0);

    // The fill: translucent when glass is on, near-opaque otherwise so the same
    // layout renders solid without a BackdropFilter (R6).
    final fillAlpha =
        glassEnabled ? _fillOpacity(fill) : GlassTokens.fillOpaque;
    final fillColor = tint.withValues(alpha: fillAlpha);

    final content = Container(
      padding: padding,
      decoration: ShapeDecoration(
        shape: shape,
        color: fillColor,
        // Hairline specular rim (only visible on the translucent path).
      ),
      foregroundDecoration: glassEnabled && showSheen
          ? ShapeDecoration(
              shape: shape,
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                stops: const [0.0, 0.5, 1.0],
                colors: [
                  Colors.white.withValues(alpha: GlassTokens.sheenPeak),
                  Colors.white.withValues(alpha: 0.0),
                  Colors.white.withValues(alpha: GlassTokens.sheenPeak * 0.4),
                ],
              ),
            )
          : null,
      child: child,
    );

    // The clipped body: blur behind the fill only when glass is enabled.
    final clipped = ClipPath(
      clipper: ShapeBorderClipper(shape: shape),
      child: glassEnabled
          ? BackdropFilter(
              filter: ImageFilter.blur(
                sigmaX: blurSigma.clamp(0.0, GlassTokens.blurMax),
                sigmaY: blurSigma.clamp(0.0, GlassTokens.blurMax),
                tileMode: TileMode.mirror,
              ),
              child: content,
            )
          : content,
    );

    // Decorate with the border + soft shadow OUTSIDE the clip so the shadow is
    // not clipped away and the hairline rim sits on the shape edge.
    return DecoratedBox(
      decoration: ShapeDecoration(
        shape: shape.copyWith(
          side: borderColor.a > 0
              ? BorderSide(color: borderColor, width: GlassTokens.borderWidth)
              : BorderSide.none,
        ),
        shadows: showShadow ? GlassTokens.cardShadow : null,
      ),
      child: clipped,
    );
  }
}

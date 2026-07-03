// Liquid-glass design tokens for CLARA_Mobile (clara-mobile-liquid-glass, R1).
//
// A single, pure-constant source of truth for the iOS-26-inspired "liquid
// glass" material: blur sigmas per surface role, translucent fill opacities,
// edge/highlight/sheen values, soft layered shadows, and the continuous
// (squircle) corner radii. Chrome surfaces (nav/tab bars, floating controls,
// sheets, headers) read these tokens so the glass look stays consistent and is
// tunable in one place.
//
// Safety-first intent (R1, R11): glass is for CHROME only. Clinical content
// (chat answers, DDI results, FIDES verdicts, consent copy, dosage numbers) is
// never placed on translucent glass — it stays on opaque, high-contrast
// surfaces. The `fillOpaque*` tokens are the reduced-transparency / low-end
// fallback so the exact same layout renders solid (no blur) with the squircle,
// border, and shadow preserved.
//
// Everything here is pure and side-effect-free (no widgets, no logic), grouped
// on a non-instantiable class so call sites read as `GlassTokens.blurNav`,
// `GlassTokens.fillRegular`, etc., mirroring the `ClaraTokens` style.

import 'package:flutter/material.dart';

/// Pure liquid-glass token constants for CLARA_Mobile.
///
/// Non-instantiable namespace. Light-first values tuned for the web-derived
/// light canvas (`WebPalette.lightCanvas`); the dark variants keep the same
/// geometry with brightness-appropriate fills/edges.
class GlassTokens {
  const GlassTokens._();

  // --- Blur sigma by surface role (R1.1) ------------------------------------
  // Gaussian sigma for `ImageFilter.blur`. Cost scales with blurred area ×
  // sigma, so keep persistent/large surfaces modest and cap at ~30.

  /// Bottom nav / tab bar — persistent, over scrolling content.
  static const double blurNav = 24.0;

  /// Top nav / app bar / header.
  static const double blurBar = 20.0;

  /// Floating card / chip / small control.
  static const double blurCard = 12.0;

  /// Modal sheet / dialog surface — reads as a deeper layer.
  static const double blurSheet = 30.0;

  /// Maximum sigma the system will ever apply (perf ceiling, R11.4).
  static const double blurMax = 30.0;

  // --- Fill opacity (alpha over the tint color) (R1.1, R11.2) ---------------

  /// Thin fill — nav/tab bars where more see-through is wanted.
  static const double fillThin = 0.45;

  /// Regular fill — default cards/controls.
  static const double fillRegular = 0.60;

  /// Thick fill — sheets and anything hosting secondary text.
  static const double fillThick = 0.75;

  /// Opaque fallback (reduced transparency / low-end): no blur, solid fill.
  static const double fillOpaque = 0.96;

  // --- Edge / highlight / sheen (R1.1) --------------------------------------

  /// Hairline specular rim opacity (bright edge that catches light).
  static const double borderHairline = 0.70;

  /// Hairline rim stroke width, logical px.
  static const double borderWidth = 1.0;

  /// Top inner-highlight peak opacity (fades to 0 toward center).
  static const double highlightTop = 0.35;

  /// Diagonal sheen peak opacity (kept subtle so it reads as glass, not glare).
  static const double sheenPeak = 0.22;

  // --- Continuous (squircle) corner radii (R1.1, R2) ------------------------
  // Outer radii. `ContinuousRectangleBorder` under-curves vs Apple's squircle,
  // so downstream shape helpers apply the `squircleFactor` multiplier.

  /// Chip / small pill.
  static const double radiusChip = 12.0;

  /// Control (button, segmented control, input).
  static const double radiusControl = 16.0;

  /// Card / floating surface.
  static const double radiusCard = 24.0;

  /// Sheet (top corners only).
  static const double radiusSheet = 32.0;

  /// Fully-rounded pill (FAB, segmented control track).
  static const double radiusPill = 999.0;

  /// Multiplier applied to a radius when building a [ContinuousRectangleBorder]
  /// so its perceived roundness matches Apple's superellipse (~1.7×).
  static const double squircleFactor = 1.7;

  // --- Soft layered shadows (R1.1) ------------------------------------------
  // Glass hovers; shadows are soft and low-opacity, never the hard Material
  // default. Stacked ambient + contact for depth.

  /// Card-level soft shadow stack (ambient + contact).
  static List<BoxShadow> get cardShadow => <BoxShadow>[
        BoxShadow(
          color: const Color(0xFF000000).withValues(alpha: 0.06),
          blurRadius: 24,
          offset: const Offset(0, 8),
        ),
        BoxShadow(
          color: const Color(0xFF000000).withValues(alpha: 0.04),
          blurRadius: 6,
          offset: const Offset(0, 2),
        ),
      ];

  /// Modal / sheet soft shadow (deeper).
  static List<BoxShadow> get modalShadow => <BoxShadow>[
        BoxShadow(
          color: const Color(0xFF000000).withValues(alpha: 0.10),
          blurRadius: 40,
          offset: const Offset(0, 16),
        ),
      ];

  // --- Spring motion (R1.4) --------------------------------------------------

  /// Signature spring for press/settle and FAB→sheet morphs.
  static const SpringDescription spring =
      SpringDescription(mass: 1, stiffness: 500, damping: 28);
}

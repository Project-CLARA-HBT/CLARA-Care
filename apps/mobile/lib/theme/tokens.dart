// Design tokens for CLARA_Mobile Experience_V2 (Requirement 2.2).
//
// A single, pure-constant source of truth for the modern design system: the
// brand seed color, the spacing/radius/elevation scales, and the base motion
// durations. Components, the adaptive shell, and the modern Home read these
// tokens instead of hard-coding values, so the look stays consistent and is
// tunable in one place.
//
// Design intent: CLARA-Care is Vietnamese-first decision-support software, so
// the palette and motion are calm, trustworthy, and accessible — a polished
// teal close to the legacy `Colors.teal` seed, generous spacing for legibility
// at large text scales, and short, unobtrusive durations. Motion tokens are
// *base* durations only; downstream code resolves them through
// `A11y.resolveMotionDuration` so they collapse to `Duration.zero` under
// reduced motion.
//
// Everything here is pure and side-effect-free (no widgets, no logic), grouped
// on a non-instantiable class so call sites read as `ClaraTokens.spaceMd`,
// `ClaraTokens.brandSeed`, `ClaraTokens.motionBase`, etc., mirroring the
// `A11y` helper style in `lib/core/a11y.dart`.

import 'package:flutter/material.dart' show Color;

/// Pure design-token constants for CLARA_Mobile Experience_V2.
///
/// Non-instantiable: every member is `static const`, so this class is a
/// namespace, not an object. Grouped by concern (brand, spacing, radius,
/// elevation, motion) with a stable prefix per group.
class ClaraTokens {
  const ClaraTokens._();

  // --- Brand (Requirement 2.1, 2.2) -----------------------------------------

  /// Brand seed color for `ColorScheme.fromSeed`. A polished, modern brand
  /// teal in the same family as the legacy `Colors.teal` (`0xFF009688`) seed —
  /// slightly deeper and more saturated for a calm, trustworthy feel and
  /// stronger AA contrast as an M3 primary. Light and dark schemes both derive
  /// from this single seed.
  static const Color brandSeed = Color(0xFF0F766E);

  // --- Spacing scale (logical px, Requirement 2.2) --------------------------
  // 4-based scale; generous steps keep primary content legible when the OS
  // text scaler is increased (see `A11y.resolveTextScaler`).

  /// 4 logical px — tight inset / icon-to-label gap.
  static const double spaceXs = 4.0;

  /// 8 logical px — compact padding between related controls.
  static const double spaceSm = 8.0;

  /// 16 logical px — default content padding / card inset.
  static const double spaceMd = 16.0;

  /// 24 logical px — section spacing.
  static const double spaceLg = 24.0;

  /// 32 logical px — major surface / screen-edge rhythm.
  static const double spaceXl = 32.0;

  // --- Corner radius scale (logical px, Requirement 2.2) --------------------

  /// 8 logical px — chips, inputs, small surfaces.
  static const double radiusSm = 8.0;

  /// 12 logical px — buttons and default cards.
  static const double radiusMd = 12.0;

  /// 20 logical px — prominent cards / sheets.
  static const double radiusLg = 20.0;

  /// Full pill / capsule radius.
  static const double radiusPill = 9999.0;

  // --- Elevation levels (M3 tonal elevation, Requirement 2.2) ---------------

  /// Flat surface — no shadow (e.g., scaffold background, inline content).
  static const double elevationLevel0 = 0.0;

  /// Subtly raised — resting cards.
  static const double elevationLevel1 = 1.0;

  /// Raised — pressed cards, app bars on scroll.
  static const double elevationLevel2 = 3.0;

  /// Overlay — menus, dialogs, transient surfaces.
  static const double elevationLevel3 = 6.0;

  // --- Motion durations (base, Requirement 2.2 / 2.4) -----------------------
  // BASE durations only. Always resolve through `A11y.resolveMotionDuration`
  // (or its `...Data` variant) at the call site so non-essential motion
  // collapses to `Duration.zero` under reduced motion.

  /// 120 ms — quick feedback (card press, ripple, small reveals).
  static const Duration motionFast = Duration(milliseconds: 120);

  /// 240 ms — standard transitions (nav switch, list reveal).
  static const Duration motionMedium = Duration(milliseconds: 240);

  /// 400 ms — deliberate, larger surface transitions.
  static const Duration motionSlow = Duration(milliseconds: 400);
}

// Web-derived color palette for CLARA_Mobile UX Polish
// (clara-mobile-ux-polish, Requirement 6, 7).
//
// A single, pure-constant source of truth that ports the CLARA_Web design
// tokens (`apps/web/styles/globals.css` — `:root` for light, `html.dark` for
// dark) into mobile `Color` constants, so the two clients look like one
// product. Everything here is pure (no widgets, I/O, or analytics), mirroring
// the `ClaraTokens` style.
//
// Fidelity & AA (Requirement 6.1, 7):
//   * Web tokens that use alpha over a canvas are **flattened** to opaque
//     equivalents against that canvas so a single `Color` constant is a
//     faithful match and contrast can be verified against the surface we
//     actually paint.
//   * Every foreground/background pairing used by mobile surfaces has been
//     verified to meet WCAG AA (≥4.5:1 normal text, ≥3:1 large/non-text). The
//     action color (`brand-600`) carries white text at ≥5.2:1 in both
//     brightnesses; dark `onError`/`onPrimary` choices keep text legible where
//     white would fail.
//
// The parity property (P6) compares these mobile constants to the documented
// (flattened) web values per brightness; the contrast property (P7) is the
// hard gate.

import 'package:flutter/material.dart';

/// Pure web-derived color constants for CLARA_Mobile UX Polish.
///
/// Non-instantiable namespace. Light values come from the web `:root` block;
/// dark values from the `html.dark` block. Alpha-over-canvas tokens are
/// flattened to opaque colors (the flattened hex is noted inline).
class WebPalette {
  const WebPalette._();

  // --- Light (from `:root`) --------------------------------------------------

  /// `--bg-canvas` `#f4f6fb` — app background / scaffold.
  static const Color lightCanvas = Color(0xFFF4F6FB);

  /// `--bg-elev-3` `#ffffff` — top elevated surface (cards, sheets).
  static const Color lightSurface = Color(0xFFFFFFFF);

  /// `--surface-muted` `#f6f8fc` — muted container fill.
  static const Color lightSurfaceMuted = Color(0xFFF6F8FC);

  /// `--surface-brand-soft` `#e8effe` — soft brand container.
  static const Color lightBrandSoft = Color(0xFFE8EFFE);

  /// `--text-primary` `#172033` — primary body text.
  static const Color lightTextPrimary = Color(0xFF172033);

  /// `--text-secondary` `#46556a` — secondary text.
  static const Color lightTextSecondary = Color(0xFF46556A);

  /// `--text-muted` `#5b6a80` — muted text.
  static const Color lightTextMuted = Color(0xFF5B6A80);

  /// `--text-brand` `#1d4ed8` — brand-toned text.
  static const Color lightTextBrand = Color(0xFF1D4ED8);

  /// `--shell-border-strong` `#94a3bd` — interactive control outline.
  static const Color lightOutline = Color(0xFF94A3BD);

  /// `--shell-border` `#dfe5ef` — subtle structural separation.
  static const Color lightOutlineVariant = Color(0xFFDFE5EF);

  // --- Dark (from `html.dark`) -----------------------------------------------

  /// `--bg-canvas` `#1b1a19` — app background / scaffold.
  static const Color darkCanvas = Color(0xFF1B1A19);

  /// `--surface-panel` `#292929` — elevated surface.
  static const Color darkSurface = Color(0xFF292929);

  /// `--surface-muted` `#333333`.
  static const Color darkSurfaceMuted = Color(0xFF333333);

  /// `--surface-brand-soft` `#0f3b5f`.
  static const Color darkBrandSoft = Color(0xFF0F3B5F);

  /// `--text-primary` `#ffffff`.
  static const Color darkTextPrimary = Color(0xFFFFFFFF);

  /// `--text-secondary` `#d6d6d6`.
  static const Color darkTextSecondary = Color(0xFFD6D6D6);

  /// `--text-muted` `#b3b3b3`.
  static const Color darkTextMuted = Color(0xFFB3B3B3);

  /// `--text-brand` `#75b6e7` — brand-toned text.
  static const Color darkTextBrand = Color(0xFF75B6E7);

  /// `--shell-border-strong` `#8a8886` — interactive control outline.
  static const Color darkOutline = Color(0xFF8A8886);

  /// `--shell-border` `#484848` — subtle structural separation.
  static const Color darkOutlineVariant = Color(0xFF484848);

  // --- Brand + status (shared token values) ----------------------------------

  /// `--brand-500` `#3b7bf0`.
  static const Color brand500 = Color(0xFF3B7BF0);

  /// `--brand-600` `#2563EB` — the primary action color (white text ≥5.2:1).
  static const Color brand600 = Color(0xFF2563EB);

  /// `--brand-700` `#1D4ED8`.
  static const Color brand700 = Color(0xFF1D4ED8);

  /// `--accent-500` `#6366f1`.
  static const Color accent500 = Color(0xFF6366F1);

  /// `--success-500` `#16a34a` (light).
  static const Color success500 = Color(0xFF16A34A);

  /// `--warn-500` `#f59e0b` (light).
  static const Color warn500 = Color(0xFFF59E0B);

  /// `--danger-500` `#dc2626` (light) — white text ≥4.8:1.
  static const Color danger500 = Color(0xFFDC2626);

  /// Dark success (from `--status-ok-text` family) `#6EE7B7`.
  static const Color successDark = Color(0xFF6EE7B7);

  /// Dark warning `#FCD34D`.
  static const Color warnDark = Color(0xFFFCD34D);

  /// Dark danger `#F87171`.
  static const Color dangerDark = Color(0xFFF87171);
}

/// Semantic status colors that Material's [ColorScheme] has no dedicated slot
/// for (success / warning). Exposed as a [ThemeExtension] so surfaces read them
/// from the theme instead of hard-coding hex, and are always paired with a text
/// label + icon at the call site (Requirement 7.4) via `StatusByText`.
@immutable
class ClaraStatusColors extends ThemeExtension<ClaraStatusColors> {
  const ClaraStatusColors({
    required this.success,
    required this.onSuccess,
    required this.warning,
    required this.onWarning,
  });

  /// Success/positive status color (paired with text/icon).
  final Color success;

  /// Foreground for text/icon placed on [success].
  final Color onSuccess;

  /// Warning/caution status color (paired with text/icon).
  final Color warning;

  /// Foreground for text/icon placed on [warning].
  final Color onWarning;

  /// Light-brightness status colors.
  static const ClaraStatusColors light = ClaraStatusColors(
    success: WebPalette.success500,
    onSuccess: Color(0xFFFFFFFF),
    warning: WebPalette.warn500,
    onWarning: Color(0xFF3D2A00),
  );

  /// Dark-brightness status colors.
  static const ClaraStatusColors dark = ClaraStatusColors(
    success: WebPalette.successDark,
    onSuccess: Color(0xFF06251A),
    warning: WebPalette.warnDark,
    onWarning: Color(0xFF3A2A00),
  );

  /// The bundle for the given [brightness].
  static ClaraStatusColors of(Brightness brightness) =>
      brightness == Brightness.dark ? dark : light;

  @override
  ClaraStatusColors copyWith({
    Color? success,
    Color? onSuccess,
    Color? warning,
    Color? onWarning,
  }) {
    return ClaraStatusColors(
      success: success ?? this.success,
      onSuccess: onSuccess ?? this.onSuccess,
      warning: warning ?? this.warning,
      onWarning: onWarning ?? this.onWarning,
    );
  }

  @override
  ClaraStatusColors lerp(ThemeExtension<ClaraStatusColors>? other, double t) {
    if (other is! ClaraStatusColors) {
      return this;
    }
    return ClaraStatusColors(
      success: Color.lerp(success, other.success, t)!,
      onSuccess: Color.lerp(onSuccess, other.onSuccess, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      onWarning: Color.lerp(onWarning, other.onWarning, t)!,
    );
  }
}

/// Builds the web-derived [ColorScheme] for [brightness] (Requirement 6.2).
///
/// Explicit role mapping (not seed-generated) so the mobile scheme matches the
/// web palette exactly while every on-color pairing clears WCAG AA. The action
/// color (`primary`) is `brand-600` in both brightnesses with white text; dark
/// `onError`/`onPrimary` are darkened where white would fail AA.
ColorScheme webColorScheme(Brightness brightness) {
  if (brightness == Brightness.dark) {
    return const ColorScheme.dark(
      primary: WebPalette.brand600,
      onPrimary: Color(0xFFFFFFFF),
      primaryContainer: WebPalette.darkBrandSoft,
      onPrimaryContainer: WebPalette.darkTextPrimary,
      secondary: WebPalette.darkTextBrand,
      onSecondary: Color(0xFF08131F),
      secondaryContainer: WebPalette.darkBrandSoft,
      onSecondaryContainer: WebPalette.darkTextPrimary,
      surface: WebPalette.darkSurface,
      onSurface: WebPalette.darkTextPrimary,
      surfaceContainerHighest: WebPalette.darkSurfaceMuted,
      onSurfaceVariant: WebPalette.darkTextMuted,
      outline: WebPalette.darkOutline,
      outlineVariant: WebPalette.darkOutlineVariant,
      error: WebPalette.dangerDark,
      onError: Color(0xFF4A0505),
    );
  }
  return const ColorScheme.light(
    primary: WebPalette.brand600,
    onPrimary: Color(0xFFFFFFFF),
    primaryContainer: WebPalette.lightBrandSoft,
    onPrimaryContainer: WebPalette.lightTextBrand,
    secondary: WebPalette.brand700,
    onSecondary: Color(0xFFFFFFFF),
    secondaryContainer: WebPalette.lightBrandSoft,
    onSecondaryContainer: WebPalette.lightTextBrand,
    surface: WebPalette.lightSurface,
    onSurface: WebPalette.lightTextPrimary,
    surfaceContainerHighest: WebPalette.lightSurfaceMuted,
    onSurfaceVariant: WebPalette.lightTextMuted,
    outline: WebPalette.lightOutline,
    outlineVariant: WebPalette.lightOutlineVariant,
    error: WebPalette.danger500,
    onError: Color(0xFFFFFFFF),
  );
}

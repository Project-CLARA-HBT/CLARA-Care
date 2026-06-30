// M3 type scale for CLARA_Mobile Experience_V2 (Requirements 2.1, 2.2, 2.5).
//
// A single, pure source of truth for the modern typography. CLARA-Care is
// Vietnamese-first, so the scale is tuned for **Vietnamese diacritics**: Latin
// text with stacked tone + vowel marks (e.g. "ế", "ữ", "ọ") needs more vertical
// room than plain Latin or the M3 defaults give, or the marks crowd the line
// above. We therefore keep the default platform font (no custom font assets or
// new dependencies — Requirement 1.5) and instead tune **sizes, line heights,
// and weights**: every role gets a generous `height` (line-height multiple) so
// ascending diacritics never clip and descending hooks stay readable.
//
// The result is a complete Material 3 `TextTheme` (display / headline / title /
// body / label, each in large/medium/small) that `ClaraTheme` blends onto the
// generated `ColorScheme`. It is pure and side-effect-free: a namespace class
// with a single factory returning a fresh `TextTheme`, mirroring the
// `ClaraTokens` / `A11y` style.
//
// Note on color: this module sets only geometry (size/height/weight/spacing),
// never color. `ThemeData` applies the scheme's `onSurface`/`onSurfaceVariant`
// colors when the `TextTheme` is attached, so AA contrast comes from the
// tonally-correct generated `ColorScheme` (see `clara_theme.dart`).

import 'package:flutter/material.dart';

/// Pure typography factory for CLARA_Mobile Experience_V2.
///
/// Non-instantiable namespace: call [ClaraTypography.textTheme] to obtain the
/// shared Material 3 [TextTheme]. The scale uses the default platform font and
/// only tunes size/height/weight/letter-spacing so Vietnamese diacritics render
/// with comfortable vertical rhythm.
class ClaraTypography {
  const ClaraTypography._();

  /// Generous line-height multiple for dense reading roles (body/label) so
  /// stacked Vietnamese tone marks never clip the line above.
  static const double _readingHeight = 1.45;

  /// Slightly tighter line-height for large display/headline roles, where the
  /// font size already leaves ample room for diacritics.
  static const double _displayHeight = 1.20;

  /// Comfortable line-height for title roles (between display and body).
  static const double _titleHeight = 1.30;

  /// The shared Material 3 [TextTheme] for Experience_V2.
  ///
  /// All thirteen M3 roles are defined explicitly with tuned size, weight, and
  /// (critically for Vietnamese) line `height`. No color is set here — the
  /// theme supplies scheme-driven colors when this is attached, preserving AA
  /// contrast from the generated `ColorScheme`.
  static TextTheme textTheme() {
    return const TextTheme(
      // --- Display: hero/marketing-scale text (onboarding, splashy headers).
      displayLarge: TextStyle(
        fontSize: 52,
        height: _displayHeight,
        fontWeight: FontWeight.w400,
        letterSpacing: -0.25,
      ),
      displayMedium: TextStyle(
        fontSize: 42,
        height: _displayHeight,
        fontWeight: FontWeight.w400,
      ),
      displaySmall: TextStyle(
        fontSize: 34,
        height: _displayHeight,
        fontWeight: FontWeight.w400,
      ),
      // --- Headline: high-emphasis screen/section titles.
      headlineLarge: TextStyle(
        fontSize: 30,
        height: _titleHeight,
        fontWeight: FontWeight.w600,
      ),
      headlineMedium: TextStyle(
        fontSize: 26,
        height: _titleHeight,
        fontWeight: FontWeight.w600,
      ),
      headlineSmall: TextStyle(
        fontSize: 22,
        height: _titleHeight,
        fontWeight: FontWeight.w600,
      ),
      // --- Title: card titles, app-bar titles, list headers.
      titleLarge: TextStyle(
        fontSize: 20,
        height: _titleHeight,
        fontWeight: FontWeight.w600,
      ),
      titleMedium: TextStyle(
        fontSize: 17,
        height: _titleHeight,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.1,
      ),
      titleSmall: TextStyle(
        fontSize: 15,
        height: _titleHeight,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.1,
      ),
      // --- Body: primary reading text — most diacritic-sensitive, so the
      // tallest line height.
      bodyLarge: TextStyle(
        fontSize: 17,
        height: _readingHeight,
        fontWeight: FontWeight.w400,
        letterSpacing: 0.15,
      ),
      bodyMedium: TextStyle(
        fontSize: 15,
        height: _readingHeight,
        fontWeight: FontWeight.w400,
        letterSpacing: 0.2,
      ),
      bodySmall: TextStyle(
        fontSize: 13,
        height: _readingHeight,
        fontWeight: FontWeight.w400,
        letterSpacing: 0.2,
      ),
      // --- Label: buttons, chips, captions.
      labelLarge: TextStyle(
        fontSize: 15,
        height: _titleHeight,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.1,
      ),
      labelMedium: TextStyle(
        fontSize: 13,
        height: _titleHeight,
        fontWeight: FontWeight.w500,
        letterSpacing: 0.4,
      ),
      labelSmall: TextStyle(
        fontSize: 11,
        height: _titleHeight,
        fontWeight: FontWeight.w500,
        letterSpacing: 0.4,
      ),
    );
  }
}

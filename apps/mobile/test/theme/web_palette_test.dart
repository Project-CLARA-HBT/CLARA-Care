// Tests for the web-derived color palette (clara-mobile-ux-polish, Req 6, 7).
//
//   * Palette parity (P6): the mobile `Color` constants exactly preserve the
//     documented (flattened) web token values.
//   * WCAG AA contrast (P7): every foreground/background pairing painted by the
//     mobile scheme clears the AA threshold (>=4.5:1 for text, >=3:1 for the
//     status colors which are always paired with a text label + icon).

import 'dart:math' as math;

import 'package:clara_mobile/theme/web_palette.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// WCAG relative luminance for a single sRGB channel already normalized to
/// the 0..1 range.
double _linearize(double channel) {
  return channel <= 0.03928
      ? channel / 12.92
      : math.pow((channel + 0.055) / 1.055, 2.4).toDouble();
}

/// WCAG relative luminance of [color].
///
/// In this Flutter version `Color.r/.g/.b` are already doubles in the 0..1
/// range, so they are linearized directly (no divide-by-255 needed).
double _relativeLuminance(Color color) {
  final double r = _linearize(color.r);
  final double g = _linearize(color.g);
  final double b = _linearize(color.b);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/// WCAG contrast ratio between two colors (order-independent).
double contrastRatio(Color a, Color b) {
  final double la = _relativeLuminance(a);
  final double lb = _relativeLuminance(b);
  final double lighter = math.max(la, lb);
  final double darker = math.min(la, lb);
  return (lighter + 0.05) / (darker + 0.05);
}

void main() {
  group('Palette parity (P6)', () {
    test('light values exactly preserve documented web tokens', () {
      expect(WebPalette.lightCanvas, const Color(0xFFF7F9FB));
      expect(WebPalette.lightSurface, const Color(0xFFFFFFFF));
      expect(WebPalette.lightSurfaceMuted, const Color(0xFFEFF6FF));
      expect(WebPalette.lightBrandSoft, const Color(0xFFDBEAFE));
      expect(WebPalette.lightTextPrimary, const Color(0xFF1F2937));
      expect(WebPalette.lightTextSecondary, const Color(0xFF374151));
      expect(WebPalette.lightTextMuted, const Color(0xFF4B5563));
      expect(WebPalette.lightTextBrand, const Color(0xFF1E40AF));
      expect(WebPalette.lightOutline, const Color(0xFFDDE8FA));
    });

    test('dark values exactly preserve documented web tokens', () {
      expect(WebPalette.darkCanvas, const Color(0xFF111A2D));
      expect(WebPalette.darkSurface, const Color(0xFF1D2840));
      expect(WebPalette.darkSurfaceMuted, const Color(0xFF223257));
      expect(WebPalette.darkBrandSoft, const Color(0xFF192D51));
      expect(WebPalette.darkTextPrimary, const Color(0xFFDAE2FD));
      expect(WebPalette.darkTextSecondary, const Color(0xFFC3C6D0));
      expect(WebPalette.darkTextMuted, const Color(0xFF9DA2AD));
      expect(WebPalette.darkTextBrand, const Color(0xFF93C5FD));
      expect(WebPalette.darkOutline, const Color(0xFF1A3159));
    });

    test('brand + status values exactly preserve documented web tokens', () {
      expect(WebPalette.brand500, const Color(0xFF3B82F6));
      expect(WebPalette.brand600, const Color(0xFF2563EB));
      expect(WebPalette.brand700, const Color(0xFF1D4ED8));
      expect(WebPalette.accent500, const Color(0xFFB7C8E1));
      expect(WebPalette.success500, const Color(0xFF16A34A));
      expect(WebPalette.warn500, const Color(0xFFF59E0B));
      expect(WebPalette.danger500, const Color(0xFFDC2626));
      expect(WebPalette.successDark, const Color(0xFF6EE7B7));
      expect(WebPalette.warnDark, const Color(0xFFFCD34D));
      expect(WebPalette.dangerDark, const Color(0xFFF87171));
    });
  });

  group('WCAG AA contrast (P7)', () {
    // Sanity check the helper against known reference pairs.
    test('contrastRatio matches known WCAG reference values', () {
      expect(
        contrastRatio(const Color(0xFF000000), const Color(0xFFFFFFFF)),
        closeTo(21.0, 0.01),
      );
      expect(
        contrastRatio(const Color(0xFFFFFFFF), const Color(0xFFFFFFFF)),
        closeTo(1.0, 0.001),
      );
    });

    for (final brightness in Brightness.values) {
      test('scheme on-colors clear AA for $brightness', () {
        final ColorScheme scheme = webColorScheme(brightness);

        expect(
          contrastRatio(scheme.onSurface, scheme.surface),
          greaterThanOrEqualTo(4.5),
          reason: 'onSurface vs surface ($brightness)',
        );
        expect(
          contrastRatio(scheme.onSurfaceVariant, scheme.surface),
          greaterThanOrEqualTo(4.5),
          reason: 'onSurfaceVariant vs surface ($brightness)',
        );
        expect(
          contrastRatio(
            scheme.onSurfaceVariant,
            scheme.surfaceContainerHighest,
          ),
          greaterThanOrEqualTo(4.5),
          reason: 'onSurfaceVariant vs surfaceContainerHighest ($brightness)',
        );
        expect(
          contrastRatio(scheme.onPrimary, scheme.primary),
          greaterThanOrEqualTo(4.5),
          reason: 'onPrimary vs primary ($brightness)',
        );
        expect(
          contrastRatio(scheme.onPrimaryContainer, scheme.primaryContainer),
          greaterThanOrEqualTo(4.5),
          reason: 'onPrimaryContainer vs primaryContainer ($brightness)',
        );
        expect(
          contrastRatio(scheme.onError, scheme.error),
          greaterThanOrEqualTo(4.5),
          reason: 'onError vs error ($brightness)',
        );
        expect(
          contrastRatio(scheme.onSecondary, scheme.secondary),
          greaterThanOrEqualTo(4.5),
          reason: 'onSecondary vs secondary ($brightness)',
        );
      });
    }

    test('status colors clear the >=3:1 non-text threshold', () {
      for (final status in <ClaraStatusColors>[
        ClaraStatusColors.light,
        ClaraStatusColors.dark,
      ]) {
        expect(
          contrastRatio(status.onSuccess, status.success),
          greaterThanOrEqualTo(3.0),
          reason: 'onSuccess vs success',
        );
        expect(
          contrastRatio(status.onWarning, status.warning),
          greaterThanOrEqualTo(3.0),
          reason: 'onWarning vs warning',
        );
      }
    });
  });
}

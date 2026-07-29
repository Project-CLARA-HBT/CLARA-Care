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
      expect(WebPalette.lightCanvas, const Color(0xFFF4F6FB));
      expect(WebPalette.lightSurface, const Color(0xFFFFFFFF));
      expect(WebPalette.lightSurfaceMuted, const Color(0xFFF6F8FC));
      expect(WebPalette.lightBrandSoft, const Color(0xFFE8EFFE));
      expect(WebPalette.lightTextPrimary, const Color(0xFF172033));
      expect(WebPalette.lightTextSecondary, const Color(0xFF46556A));
      expect(WebPalette.lightTextMuted, const Color(0xFF5B6A80));
      expect(WebPalette.lightTextBrand, const Color(0xFF1D4ED8));
      expect(WebPalette.lightOutline, const Color(0xFF94A3BD));
      expect(WebPalette.lightOutlineVariant, const Color(0xFFDFE5EF));
    });

    test('dark values exactly preserve documented web tokens', () {
      expect(WebPalette.darkCanvas, const Color(0xFF1B1A19));
      expect(WebPalette.darkSurface, const Color(0xFF292929));
      expect(WebPalette.darkSurfaceMuted, const Color(0xFF333333));
      expect(WebPalette.darkBrandSoft, const Color(0xFF0F3B5F));
      expect(WebPalette.darkTextPrimary, const Color(0xFFFFFFFF));
      expect(WebPalette.darkTextSecondary, const Color(0xFFD6D6D6));
      expect(WebPalette.darkTextMuted, const Color(0xFFB3B3B3));
      expect(WebPalette.darkTextBrand, const Color(0xFF75B6E7));
      expect(WebPalette.darkOutline, const Color(0xFF8A8886));
      expect(WebPalette.darkOutlineVariant, const Color(0xFF484848));
    });

    test('brand + status values exactly preserve documented web tokens', () {
      expect(WebPalette.brand500, const Color(0xFF3B7BF0));
      expect(WebPalette.brand600, const Color(0xFF2563EB));
      expect(WebPalette.brand700, const Color(0xFF1D4ED8));
      expect(WebPalette.accent500, const Color(0xFF6366F1));
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

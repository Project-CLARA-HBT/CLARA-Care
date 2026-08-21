// Unit and widget tests for ClaraTheme and theme configurations.

import 'package:clara_mobile/theme/clara_theme.dart';
import 'package:clara_mobile/theme/tokens.dart';
import 'package:clara_mobile/theme/web_palette.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('ClaraTheme builders', () {
    test('ClaraTheme.light() defaults to unpolished M3 light theme', () {
      final theme = ClaraTheme.light();

      expect(theme.useMaterial3, isTrue);
      expect(theme.brightness, Brightness.light);
      expect(theme.colorScheme.brightness, Brightness.light);
      expect(theme.extensions.values.whereType<ClaraStatusColors>(), isEmpty);
    });

    test('ClaraTheme.dark() defaults to unpolished M3 dark theme', () {
      final theme = ClaraTheme.dark();

      expect(theme.useMaterial3, isTrue);
      expect(theme.brightness, Brightness.dark);
      expect(theme.colorScheme.brightness, Brightness.dark);
      expect(theme.extensions.values.whereType<ClaraStatusColors>(), isEmpty);
    });

    test('ClaraTheme.light(polished: true) attaches WebPalette and status colors', () {
      final theme = ClaraTheme.light(polished: true);

      expect(theme.useMaterial3, isTrue);
      expect(theme.colorScheme.brightness, Brightness.light);
      expect(theme.scaffoldBackgroundColor, WebPalette.lightCanvas);
      expect(theme.extension<ClaraStatusColors>(), isNotNull);
      expect(
        theme.extension<ClaraStatusColors>()?.success,
        WebPalette.success500,
      );
    });

    test('ClaraTheme.dark(polished: true) attaches WebPalette and dark status colors', () {
      final theme = ClaraTheme.dark(polished: true);

      expect(theme.useMaterial3, isTrue);
      expect(theme.colorScheme.brightness, Brightness.dark);
      expect(theme.scaffoldBackgroundColor, WebPalette.darkCanvas);
      expect(theme.extension<ClaraStatusColors>(), isNotNull);
      expect(
        theme.extension<ClaraStatusColors>()?.success,
        WebPalette.successDark,
      );
    });

    test('Theme shapes follow ClaraTokens radius constants', () {
      final theme = ClaraTheme.light();

      final cardShape = theme.cardTheme.shape as RoundedRectangleBorder;
      expect(
        cardShape.borderRadius,
        BorderRadius.circular(ClaraTokens.radiusLg),
      );

      final chipShape = theme.chipTheme.shape as RoundedRectangleBorder;
      expect(
        chipShape.borderRadius,
        BorderRadius.circular(ClaraTokens.radiusSm),
      );

      final inputBorder = theme.inputDecorationTheme.border as OutlineInputBorder;
      expect(
        inputBorder.borderRadius,
        BorderRadius.circular(ClaraTokens.radiusSm),
      );

      final dialogShape = theme.dialogTheme.shape as RoundedRectangleBorder;
      expect(
        dialogShape.borderRadius,
        BorderRadius.circular(ClaraTokens.radiusLg),
      );

      final sheetShape = theme.bottomSheetTheme.shape as RoundedRectangleBorder;
      expect(
        sheetShape.borderRadius,
        BorderRadius.vertical(top: Radius.circular(ClaraTokens.radiusLg)),
      );
    });

    test('Button themes have medium radius and 48px minimum height', () {
      final theme = ClaraTheme.light();

      final buttonStyle = theme.filledButtonTheme.style;
      final shape = buttonStyle?.shape?.resolve(<WidgetState>{});
      expect(shape, isA<RoundedRectangleBorder>());
      expect(
        (shape as RoundedRectangleBorder).borderRadius,
        BorderRadius.circular(ClaraTokens.radiusMd),
      );

      final minSize = buttonStyle?.minimumSize?.resolve(<WidgetState>{});
      expect(minSize?.height, 48.0);
    });
  });
}

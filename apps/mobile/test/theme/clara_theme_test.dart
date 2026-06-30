// Widget tests for the CLARA_Mobile Experience_V2 design system (task 2.6).
//
// Covers Requirement 2 acceptance criteria exercised by the theme + reusable
// components:
//   * 2.1 — A Material 3 `ThemeData` is built from the brand seed and provides
//     both light and dark themes; light/dark follow the OS brightness when the
//     root uses `MaterialApp(theme, darkTheme, themeMode: system)`.
//   * 2.2 — Component shapes/radii read the design tokens (`ClaraTokens`)
//     rather than hard-coded values (cards, buttons, inputs, chips).
//   * 2.3 — Reusable components honor the OS dynamic text-scaling preference
//     without clipping or overflowing (no layout exceptions) under a large
//     text scaler.
//
// Pure widget tests: no platform channels, no live network (Requirement 10.5).
// They lean on the shared `pumpExperience` harness for width / brightness /
// text-scaler control.

import 'package:clara_mobile/theme/clara_theme.dart';
import 'package:clara_mobile/theme/components/clara_button.dart';
import 'package:clara_mobile/theme/components/clara_card.dart';
import 'package:clara_mobile/theme/components/clara_chip.dart';
import 'package:clara_mobile/theme/components/clara_input.dart';
import 'package:clara_mobile/theme/components/section_header.dart';
import 'package:clara_mobile/theme/tokens.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/experience_pump.dart';

/// Resolves the [RoundedRectangleBorder] radius from a [WidgetStateProperty]
/// shape (as used by the M3 button themes), in the default (unpressed) state.
BorderRadius _resolvedButtonRadius(ButtonStyle? style) {
  final shape = style?.shape?.resolve(<WidgetState>{});
  expect(shape, isA<RoundedRectangleBorder>());
  return (shape as RoundedRectangleBorder).borderRadius as BorderRadius;
}

/// A column of every reusable component, used to verify nothing clips or
/// overflows under a large text scaler. Each interactive component is wired so
/// it renders in its active (non-disabled) form.
class _AllComponents extends StatelessWidget {
  const _AllComponents();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SectionHeader(title: 'Công cụ của bạn', emphasize: true),
              ClaraButton.primary(
                label: 'Bắt đầu ghi âm cuộc khám',
                icon: Icons.mic,
                onPressed: () {},
              ),
              ClaraButton.secondary(
                label: 'Huỷ',
                onPressed: () {},
              ),
              const ClaraInput(
                label: 'Tên đăng nhập',
                hint: 'Nhập tên đăng nhập của bạn',
              ),
              ClaraCard(
                onTap: () {},
                semanticLabel: 'Mở hồ sơ sức khoẻ cá nhân',
                child: const Text('Hồ sơ sức khoẻ điện tử đầy đủ của bạn'),
              ),
              Wrap(
                children: [
                  const ClaraChip(label: 'Tiếng Việt', icon: Icons.translate),
                  ClaraChip(
                    label: 'Bộ lọc đang bật',
                    selected: true,
                    onTap: () {},
                    selectedSemanticsValue: 'Đã chọn',
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

void main() {
  group('ClaraTheme — Material 3 from tokens (Req 2.1, 2.2)', () {
    test('light() is a Material 3 theme whose scheme brightness is light', () {
      final theme = ClaraTheme.light();

      expect(theme.useMaterial3, isTrue);
      expect(theme.colorScheme.brightness, Brightness.light);
      // Scheme is generated (every essential role resolves to a real color).
      expect(theme.colorScheme.primary, isNotNull);
      expect(theme.colorScheme.onPrimary, isNotNull);
    });

    test('dark() is a Material 3 theme whose scheme brightness is dark', () {
      final theme = ClaraTheme.dark();

      expect(theme.useMaterial3, isTrue);
      expect(theme.colorScheme.brightness, Brightness.dark);
      expect(theme.colorScheme.primary, isNotNull);
      expect(theme.colorScheme.onPrimary, isNotNull);
    });

    test('light and dark derive distinct schemes from the same brand seed', () {
      final light = ClaraTheme.light().colorScheme;
      final dark = ClaraTheme.dark().colorScheme;

      // Different brightnesses ⇒ different surface tones from one seed.
      expect(light.brightness, isNot(dark.brightness));
      expect(light.surface, isNot(dark.surface));
    });

    test('card shape uses the large radius token', () {
      final theme = ClaraTheme.light();
      final shape = theme.cardTheme.shape;

      expect(shape, isA<RoundedRectangleBorder>());
      expect(
        (shape as RoundedRectangleBorder).borderRadius,
        BorderRadius.circular(ClaraTokens.radiusLg),
      );
    });

    test('buttons use the medium radius token across M3 button kinds', () {
      final theme = ClaraTheme.light();
      final expected = BorderRadius.circular(ClaraTokens.radiusMd);

      expect(_resolvedButtonRadius(theme.filledButtonTheme.style), expected);
      expect(_resolvedButtonRadius(theme.elevatedButtonTheme.style), expected);
      expect(_resolvedButtonRadius(theme.outlinedButtonTheme.style), expected);
      expect(_resolvedButtonRadius(theme.textButtonTheme.style), expected);
    });

    test('inputs use the small radius token', () {
      final theme = ClaraTheme.light();
      final border = theme.inputDecorationTheme.border;

      expect(border, isA<OutlineInputBorder>());
      expect(
        (border as OutlineInputBorder).borderRadius,
        BorderRadius.circular(ClaraTokens.radiusSm),
      );
    });

    test('chips use the small radius token', () {
      final theme = ClaraTheme.light();
      final shape = theme.chipTheme.shape;

      expect(shape, isA<RoundedRectangleBorder>());
      expect(
        (shape as RoundedRectangleBorder).borderRadius,
        BorderRadius.circular(ClaraTokens.radiusSm),
      );
    });

    testWidgets('ClaraCard renders with the large radius token applied',
        (tester) async {
      await pumpExperience(
        tester,
        Scaffold(
          body: ClaraCard(
            onTap: () {},
            semanticLabel: 'Thẻ ví dụ',
            child: const Text('Nội dung thẻ'),
          ),
        ),
        theme: ClaraTheme.light(),
      );

      final card = tester.widget<Card>(find.byType(Card));
      expect(card.shape, isA<RoundedRectangleBorder>());
      expect(
        (card.shape as RoundedRectangleBorder).borderRadius,
        BorderRadius.circular(ClaraTokens.radiusLg),
      );
    });
  });

  group('Dynamic text scaling honored without clipping (Req 2.3)', () {
    for (final scaler in const [
      TextScaler.linear(1.6),
      TextScaler.linear(2.0),
    ]) {
      testWidgets('components render at $scaler on a phone width', (tester) async {
        await pumpAtPhoneWidth(
          tester,
          const _AllComponents(),
          textScaler: scaler,
          theme: ClaraTheme.light(),
        );
        await tester.pumpAndSettle();

        // No overflow / layout exception was thrown while laying out.
        expect(tester.takeException(), isNull);
        // The scaled content still renders.
        expect(find.byType(_AllComponents), findsOneWidget);
      });

      testWidgets('components render at $scaler on a tablet width',
          (tester) async {
        await pumpAtTabletWidth(
          tester,
          const _AllComponents(),
          textScaler: scaler,
          theme: ClaraTheme.light(),
        );
        await tester.pumpAndSettle();

        expect(tester.takeException(), isNull);
        expect(find.byType(_AllComponents), findsOneWidget);
      });
    }

    testWidgets('dark theme also renders cleanly under a large text scaler',
        (tester) async {
      await pumpAtPhoneWidth(
        tester,
        const _AllComponents(),
        textScaler: const TextScaler.linear(2.0),
        platformBrightness: Brightness.dark,
        theme: ClaraTheme.dark(),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
    });
  });

  group('Light/dark resolve from OS brightness (Req 2.1, 2.5)', () {
    /// Pumps a `MaterialApp(theme, darkTheme, themeMode: system)` (the modern
    /// root's wiring) under the given OS [brightness] and returns the
    /// brightness of the resolved theme's color scheme.
    Future<Brightness> resolvedSchemeBrightness(
      WidgetTester tester,
      Brightness brightness,
    ) async {
      // System theme mode resolves from the platform brightness the MaterialApp
      // reads off the view, so drive it at the platform-dispatcher level.
      tester.platformDispatcher.platformBrightnessTestValue = brightness;
      addTearDown(tester.platformDispatcher.clearPlatformBrightnessTestValue);

      late Brightness resolved;
      await pumpExperience(
        tester,
        Builder(
          builder: (context) {
            resolved = Theme.of(context).colorScheme.brightness;
            return const SizedBox.shrink();
          },
        ),
        platformBrightness: brightness,
        theme: ClaraTheme.light(),
        darkTheme: ClaraTheme.dark(),
      );
      return resolved;
    }

    testWidgets('light OS brightness resolves the light scheme', (tester) async {
      expect(
        await resolvedSchemeBrightness(tester, Brightness.light),
        Brightness.light,
      );
    });

    testWidgets('dark OS brightness resolves the dark scheme', (tester) async {
      expect(
        await resolvedSchemeBrightness(tester, Brightness.dark),
        Brightness.dark,
      );
    });
  });
}

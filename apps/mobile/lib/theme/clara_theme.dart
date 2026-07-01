// Material 3 theme builders for CLARA_Mobile Experience_V2 (Req 2.1, 2.5).
//
// `ClaraTheme.light()` / `ClaraTheme.dark()` return the modern `ThemeData` the
// Experience_V2 root applies (the legacy theme is untouched when the flag is
// off). Both are **pure factory functions** — no global mutable state, no I/O,
// no analytics — so they are trivially testable and produce a fresh `ThemeData`
// per call.
//
// Color (Requirement 2.1, 2.5): each theme is built from a single brand seed,
// `ClaraTokens.brandSeed`, via `ColorScheme.fromSeed(..., brightness: ...)`.
// Material 3's tonal-palette generation derives every on-color (onPrimary,
// onSurface, onSecondaryContainer, …) at tones chosen to clear the AA contrast
// ratio against their paired background in *both* light and dark. We therefore
// rely on the generated scheme for AA pairs and deliberately do **not**
// hand-pick foreground/background colors that could break that contrast; the
// typography and component themes only set geometry and read scheme colors.
//
// Tokens (Requirement 2.2): component shapes/elevations come from
// `ClaraTokens` (radius* / elevationLevel*), and the shared `ClaraTypography`
// text theme is applied so every surface uses the diacritic-friendly type
// scale.

import 'package:flutter/material.dart';

import 'tokens.dart';
import 'typography.dart';
import 'web_palette.dart';

/// Pure Material 3 `ThemeData` factory for CLARA_Mobile Experience_V2.
///
/// Non-instantiable namespace exposing [ClaraTheme.light] and
/// [ClaraTheme.dark]. Both build `ThemeData(useMaterial3: true)` from
/// `ColorScheme.fromSeed(seedColor: ClaraTokens.brandSeed)` for the requested
/// brightness, attach the [ClaraTypography] text theme, and wire component
/// themes to [ClaraTokens]. The OS brightness selects which builder the root
/// applies (light/dark follow the system — Requirement 2.1).
class ClaraTheme {
  const ClaraTheme._();

  /// The light Experience_V2 theme.
  ///
  /// When [polished] is true (clara-mobile-ux-polish), the `ColorScheme` is
  /// derived from the web palette (`WebPalette`) with explicit role mapping and
  /// the `ClaraStatusColors` extension is attached, so mobile matches the web
  /// app. When false, the legacy teal-seed scheme is used unchanged.
  static ThemeData light({bool polished = false}) =>
      _build(Brightness.light, polished: polished);

  /// The dark Experience_V2 theme. See [light] for the [polished] flag.
  static ThemeData dark({bool polished = false}) =>
      _build(Brightness.dark, polished: polished);

  /// Shared builder for both brightnesses. Generates an AA-correct
  /// `ColorScheme` from the brand seed, then layers the shared typography and
  /// token-driven component themes onto it.
  static ThemeData _build(Brightness brightness, {bool polished = false}) {
    // AA contrast note: when NOT polished, every on-color pairing is produced
    // by the tonal palette (generated, not hand-chosen), so pairs satisfy AA.
    // When polished, `webColorScheme` supplies an explicit, AA-verified web
    // palette (see `web_palette.dart`).
    final colorScheme = polished
        ? webColorScheme(brightness)
        : ColorScheme.fromSeed(
            seedColor: ClaraTokens.brandSeed,
            brightness: brightness,
          );
    final textTheme = ClaraTypography.textTheme();

    final base = ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      textTheme: textTheme,
      // Polished: paint the web canvas behind elevated surfaces; legacy keeps
      // scaffold tied to the generated surface so contrast holds.
      scaffoldBackgroundColor: polished
          ? (brightness == Brightness.dark
              ? WebPalette.darkCanvas
              : WebPalette.lightCanvas)
          : colorScheme.surface,
      extensions: <ThemeExtension<dynamic>>[
        if (polished) ClaraStatusColors.of(brightness),
      ],
    );

    return base.copyWith(
      // --- Cards: prominent radius, subtly raised resting elevation. ---------
      cardTheme: CardThemeData(
        elevation: ClaraTokens.elevationLevel1,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(ClaraTokens.radiusLg),
        ),
        margin: const EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceXs,
          vertical: ClaraTokens.spaceXs,
        ),
      ),

      // --- Buttons: shared medium radius across all three M3 button kinds. ---
      filledButtonTheme: FilledButtonThemeData(
        style: _buttonStyle(),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: _buttonStyle(elevation: ClaraTokens.elevationLevel1),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: _buttonStyle(),
      ),
      textButtonTheme: TextButtonThemeData(
        style: _buttonStyle(),
      ),

      // --- Inputs: small radius, filled, scheme-driven outline. --------------
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceMd,
          vertical: ClaraTokens.spaceSm,
        ),
        border: _inputBorder(),
        enabledBorder: _inputBorder(),
        focusedBorder: _inputBorder(
          color: colorScheme.primary,
          width: 2.0,
        ),
        errorBorder: _inputBorder(color: colorScheme.error),
        focusedErrorBorder: _inputBorder(
          color: colorScheme.error,
          width: 2.0,
        ),
      ),

      // --- Chips: small radius, consistent with inputs. ----------------------
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
        ),
        padding: const EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceSm,
          vertical: ClaraTokens.spaceXs,
        ),
      ),

      // --- Adaptive navigation surfaces (used by the app shell). -------------
      navigationBarTheme: NavigationBarThemeData(
        elevation: ClaraTokens.elevationLevel2,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        backgroundColor: colorScheme.surface,
        indicatorColor: colorScheme.secondaryContainer,
      ),
      navigationRailTheme: NavigationRailThemeData(
        elevation: ClaraTokens.elevationLevel0,
        labelType: NavigationRailLabelType.all,
        backgroundColor: colorScheme.surface,
        indicatorColor: colorScheme.secondaryContainer,
      ),

      // --- App bar: flat by default, scheme-driven. --------------------------
      appBarTheme: AppBarTheme(
        elevation: ClaraTokens.elevationLevel0,
        scrolledUnderElevation: ClaraTokens.elevationLevel2,
        centerTitle: false,
        backgroundColor: colorScheme.surface,
        foregroundColor: colorScheme.onSurface,
        titleTextStyle: textTheme.titleLarge?.copyWith(
          color: colorScheme.onSurface,
        ),
      ),

      // --- Dialogs / sheets: overlay elevation, large radius. ----------------
      dialogTheme: DialogThemeData(
        elevation: ClaraTokens.elevationLevel3,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(ClaraTokens.radiusLg),
        ),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        elevation: ClaraTokens.elevationLevel3,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(ClaraTokens.radiusLg),
          ),
        ),
      ),
    );
  }

  /// Shared button style: medium-radius shape and comfortable padding. The
  /// optional [elevation] lets the elevated button sit slightly raised while
  /// filled/outlined/text buttons stay flat.
  static ButtonStyle _buttonStyle({double? elevation}) {
    return ButtonStyle(
      elevation: elevation == null ? null : WidgetStatePropertyAll(elevation),
      padding: const WidgetStatePropertyAll(
        EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceLg,
          vertical: ClaraTokens.spaceSm,
        ),
      ),
      shape: WidgetStatePropertyAll(
        RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
        ),
      ),
      minimumSize: const WidgetStatePropertyAll(Size(0, 48)),
    );
  }

  /// Small-radius input border with the given [color]/[width]. A `null` color
  /// defers to the theme's default outline derived from the scheme.
  static OutlineInputBorder _inputBorder({Color? color, double width = 1.0}) {
    return OutlineInputBorder(
      borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
      borderSide: color == null
          ? const BorderSide()
          : BorderSide(color: color, width: width),
    );
  }
}

// Shared width-class pumping helper for Experience_V2 widget tests
// (CLARA mobile experience spec, task 1.1).
//
// Experience_V2 is adaptive: the app shell presents bottom navigation on
// compact (phone) widths and a navigation rail on medium/expanded
// (tablet/large) widths, switching at a 600dp breakpoint (design §"Adaptive
// shell breakpoints"). Widget tests therefore need to render a subtree at a
// chosen physical width and assert the right surface appears, and to flip the
// accessibility signals (reduced motion, dynamic text scaling) the design
// requires (Requirements 2.3, 2.4, 3.4).
//
// [pumpExperience] wraps `tester.pumpWidget` with:
//   * A configurable surface size applied to the test view, so BOTH
//     `MediaQuery.size` reads AND `LayoutBuilder` constraints reflect the
//     chosen width (the design notes the shell may use either).
//   * MediaQuery overrides for `disableAnimations` / `accessibleNavigation`
//     (reduced motion, Req 3.4/7.2), `textScaler` (dynamic text scaling, Req
//     2.3), and `platformBrightness` (light/dark resolution, Req 2.1).
//
// Everything runs under `flutter test` with no platform channels or live
// network (Requirement 10.5).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Width (in logical pixels) at/above which Experience_V2 uses the medium/
/// expanded layout (navigation rail); below it uses compact (bottom nav).
/// Mirrors the design's 600dp breakpoint.
const double kClaraTabletBreakpoint = 600.0;

/// Representative phone surface: compact width (< [kClaraTabletBreakpoint]) ⇒
/// bottom navigation.
const Size kPhoneSurfaceSize = Size(390, 844);

/// Representative tablet surface: expanded width (≥ [kClaraTabletBreakpoint]) ⇒
/// navigation rail.
const Size kTabletSurfaceSize = Size(834, 1112);

/// Adaptive width classes used by Experience_V2.
enum WidthClass {
  /// Phone widths (< [kClaraTabletBreakpoint]) — bottom navigation.
  compact,

  /// Tablet/large widths (≥ [kClaraTabletBreakpoint]) — navigation rail.
  expanded,
}

/// The [WidthClass] for a given logical [width], using the shell breakpoint.
WidthClass widthClassFor(double width) =>
    width >= kClaraTabletBreakpoint ? WidthClass.expanded : WidthClass.compact;

/// The [WidthClass] implied by a surface [size]'s width.
WidthClass widthClassForSize(Size size) => widthClassFor(size.width);

Widget _withMediaOverrides(
  Widget child, {
  required bool disableAnimations,
  required bool accessibleNavigation,
  required TextScaler textScaler,
  required Brightness platformBrightness,
}) {
  return Builder(
    builder: (context) {
      // Base off whatever MediaQuery the surrounding widget (MaterialApp) or
      // the test view provides, then override only the a11y-relevant fields so
      // the configured surface size flows through unchanged.
      final base = MediaQuery.maybeOf(context) ??
          MediaQueryData.fromView(View.of(context));
      return MediaQuery(
        data: base.copyWith(
          disableAnimations: disableAnimations,
          accessibleNavigation: accessibleNavigation,
          textScaler: textScaler,
          platformBrightness: platformBrightness,
        ),
        child: child,
      );
    },
  );
}

/// Pumps [child] at a configurable surface size and accessibility profile.
///
/// The [surfaceSize] is applied to the test view (at devicePixelRatio 1.0) and
/// reset on tear-down, so a test can render at phone vs. tablet widths and
/// assert which adaptive surface appears. By default the child is wrapped in a
/// [MaterialApp] (supply [theme]/[locale]); pass `wrapInMaterialApp: false` to
/// pump a bare subtree (the MediaQuery overrides still apply).
///
/// Reduced motion is requested via [reducedMotion] (sets `disableAnimations`)
/// and/or [accessibleNavigation]; dynamic text scaling via [textScaler];
/// light/dark resolution via [platformBrightness].
Future<void> pumpExperience(
  WidgetTester tester,
  Widget child, {
  Size surfaceSize = kPhoneSurfaceSize,
  bool reducedMotion = false,
  bool accessibleNavigation = false,
  TextScaler textScaler = TextScaler.noScaling,
  Brightness platformBrightness = Brightness.light,
  ThemeData? theme,
  ThemeData? darkTheme,
  Locale? locale,
  bool wrapInMaterialApp = true,
}) async {
  tester.view.devicePixelRatio = 1.0;
  tester.view.physicalSize = surfaceSize;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  final overridden = _withMediaOverrides(
    child,
    disableAnimations: reducedMotion,
    accessibleNavigation: accessibleNavigation,
    textScaler: textScaler,
    platformBrightness: platformBrightness,
  );

  final Widget root = wrapInMaterialApp
      ? MaterialApp(
          theme: theme,
          darkTheme: darkTheme,
          // MaterialApp selects its theme above the child MediaQuery, so a
          // MediaQuery.platformBrightness override alone cannot activate the
          // supplied dark theme. Pin the requested mode in this test harness;
          // production still follows its configured ThemeMode/controller.
          themeMode: platformBrightness == Brightness.dark
              ? ThemeMode.dark
              : ThemeMode.light,
          locale: locale,
          home: overridden,
        )
      : Directionality(
          textDirection: TextDirection.ltr,
          child: overridden,
        );

  await tester.pumpWidget(root);
}

/// Convenience: pump [child] at a phone width (compact ⇒ bottom navigation).
Future<void> pumpAtPhoneWidth(
  WidgetTester tester,
  Widget child, {
  bool reducedMotion = false,
  bool accessibleNavigation = false,
  TextScaler textScaler = TextScaler.noScaling,
  Brightness platformBrightness = Brightness.light,
  ThemeData? theme,
  ThemeData? darkTheme,
  Locale? locale,
  bool wrapInMaterialApp = true,
}) {
  return pumpExperience(
    tester,
    child,
    surfaceSize: kPhoneSurfaceSize,
    reducedMotion: reducedMotion,
    accessibleNavigation: accessibleNavigation,
    textScaler: textScaler,
    platformBrightness: platformBrightness,
    theme: theme,
    darkTheme: darkTheme,
    locale: locale,
    wrapInMaterialApp: wrapInMaterialApp,
  );
}

/// Convenience: pump [child] at a tablet width (expanded ⇒ navigation rail).
Future<void> pumpAtTabletWidth(
  WidgetTester tester,
  Widget child, {
  bool reducedMotion = false,
  bool accessibleNavigation = false,
  TextScaler textScaler = TextScaler.noScaling,
  Brightness platformBrightness = Brightness.light,
  ThemeData? theme,
  ThemeData? darkTheme,
  Locale? locale,
  bool wrapInMaterialApp = true,
}) {
  return pumpExperience(
    tester,
    child,
    surfaceSize: kTabletSurfaceSize,
    reducedMotion: reducedMotion,
    accessibleNavigation: accessibleNavigation,
    textScaler: textScaler,
    platformBrightness: platformBrightness,
    theme: theme,
    darkTheme: darkTheme,
    locale: locale,
    wrapInMaterialApp: wrapInMaterialApp,
  );
}

/// Resizes the test surface after an initial [pumpExperience] and settles a
/// frame, so a test can assert state is preserved across a width-class change
/// (e.g. selected navigation index across phone⇄tablet, Requirement 3.2).
Future<void> resizeSurface(WidgetTester tester, Size surfaceSize) async {
  tester.view.devicePixelRatio = 1.0;
  tester.view.physicalSize = surfaceSize;
  await tester.pump();
}

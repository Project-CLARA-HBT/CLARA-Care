// Accessibility invariant sweep for the CLARA_Mobile redesign (Experience_V3).
//
// clara-mobile-redesign, Task 11.2 (Requirement 1.4, 11). This widget test locks
// the a11y invariants across the *lightweight* redesigned surfaces:
//
//   * SettingsScreenV3 — theme radio tiles + account/sign-out.
//   * HomeScreenV3     — greeting header + always-present PHR quick-action card.
//
// Deliberately NOT mounted here: ChatScreen / ResearchScreen / cabinet surfaces.
// Those have brittle initState side-effects (they reassign `ErrorWidget.builder`
// and probe connectivity), which are out of scope for an a11y sweep.
//
// Adaptation note: the design's a11y helpers (`MinTapTarget`, `A11yLabeled`)
// are the *primitives*, but the redesigned surfaces enforce the ≥48dp tap-target
// invariant through the real controls they render — `ClaraButton`
// (token-driven min height), `RadioListTile` (wrapped in a 48dp `ConstrainedBox`)
// and `ClaraCard`'s `InkWell`. So this sweep asserts the effective tap-target
// guarantee on those rendered controls plus the stable Vietnamese semantics
// labels, rather than on `MinTapTarget` (which these surfaces do not use).

import 'package:clara_mobile/core/a11y.dart';
import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/experience/redesign/home_screen_v3.dart';
import 'package:clara_mobile/experience/redesign/settings_screen_v3.dart';
import 'package:clara_mobile/experience/theme_controller.dart';
import 'package:clara_mobile/theme/clara_theme.dart';
import 'package:clara_mobile/theme/components/clara_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fakes.dart';

void main() {
  // The redesigned Home fires a single coarse, no-PII screen-view in initState
  // through the shared analytics client; reset it so each case starts from a
  // known, unconfigured (non-networked) state.
  setUp(resetAnalyticsClientForTest);
  tearDown(resetAnalyticsClientForTest);

  /// Wraps [surface] in a MaterialApp using the polished light theme so the
  /// redesign tokens/theme extensions resolve exactly as in production.
  Widget wrap(Widget surface, {double? textScale}) {
    Widget home = surface;
    if (textScale != null) {
      home = MediaQuery(
        data: MediaQueryData(textScaler: TextScaler.linear(textScale)),
        child: surface,
      );
    }
    return MaterialApp(
      theme: ClaraTheme.light(polished: true),
      home: home,
    );
  }

  /// The rendered height of every element matched by [finder]; used to assert
  /// the ≥48dp minimum tap-target invariant on real controls.
  List<double> heightsOf(WidgetTester tester, Finder finder) => finder
      .evaluate()
      .map((element) => tester.getSize(find.byWidget(element.widget)).height)
      .toList(growable: false);

  group('Redesign a11y sweep (Requirement 1.4, 11)', () {
    testWidgets('Settings: every tappable control meets the >=48dp tap target',
        (tester) async {
      final semantics = tester.ensureSemantics();
      final apiClient = FakeApiClient();
      final sessionStore = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(
        wrap(
          SettingsScreenV3(
            apiClient: apiClient,
            sessionStore: sessionStore,
            themeController: ThemeController(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // The Appearance section header renders (as both a heading and its
      // ClaraCard region label), and the sign-out control is present.
      expect(find.text('Giao diện'), findsWidgets);
      expect(find.text('Đăng xuất'), findsOneWidget);

      // The sign-out control is a ClaraButton whose token-driven style enforces
      // the ≥48dp minimum tap target.
      final signOutButtons = find.byType(ClaraButton);
      expect(signOutButtons, findsWidgets);
      for (final height in heightsOf(tester, signOutButtons)) {
        expect(height, greaterThanOrEqualTo(A11y.minTapTargetDimension));
      }

      // The three theme rows are radio tiles wrapped in a 48dp ConstrainedBox;
      // every rendered tile meets the minimum tap-target height.
      final themeTiles = find.byType(RadioListTile<ThemeMode>);
      expect(themeTiles, findsWidgets);
      for (final height in heightsOf(tester, themeTiles)) {
        expect(height, greaterThanOrEqualTo(A11y.minTapTargetDimension));
      }

      // Key control semantics exist (selection/labels are spoken, not implied
      // by color alone) — the "Sáng" (light) theme tile is announced.
      expect(find.bySemanticsLabel(RegExp('Sáng')), findsOneWidget);

      semantics.dispose();
    });

    testWidgets(
        'Settings: theme options expose selected state via semantics, not color alone',
        (tester) async {
      final semantics = tester.ensureSemantics();
      final apiClient = FakeApiClient();
      final sessionStore = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(
        wrap(
          SettingsScreenV3(
            apiClient: apiClient,
            sessionStore: sessionStore,
            themeController: ThemeController(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // All three theme radio tiles are present, keyed by mode.
      expect(find.byKey(const Key('theme-option-light')), findsOneWidget);
      expect(find.byKey(const Key('theme-option-dark')), findsOneWidget);
      expect(find.byKey(const Key('theme-option-system')), findsOneWidget);

      // Selection is encoded in the spoken label ("đã chọn"/"chưa chọn"), so
      // screen-reader users perceive it without relying on color.
      expect(
        find.bySemanticsLabel(RegExp('đã chọn|chưa chọn')),
        findsWidgets,
      );
      // Light is the default selected mode, so exactly one tile reads "đã chọn".
      expect(find.bySemanticsLabel(RegExp('đã chọn')), findsOneWidget);

      semantics.dispose();
    });

    testWidgets(
        'Home: greeting + always-present Ask CLARA card render with tap targets',
        (tester) async {
      final apiClient = FakeApiClient()
        // Seeded from the passed summary; stub in case a refresh is triggered.
        ..stub('getHomeV2', response: const {'schedule': [], 'recent_changes': []})
        ..stub('getMobileSummary', response: const {'feature_flags': {}});
      final sessionStore = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(
        wrap(
          HomeScreenV3(
            apiClient: apiClient,
            sessionStore: sessionStore,
            resolver: MobileFeatureFlagResolver(
              summary: const {'feature_flags': {}},
            ),
            summary: const {'schedule': [], 'recent_changes': []},
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Time-of-day greeting header renders (always begins with "Chào ...").
      expect(find.textContaining('Chào'), findsWidgets);

      // The Ask CLARA entry card is ALWAYS present on Home.
      expect(find.text('Hỏi CLARA'), findsOneWidget);

      // Cards render (greeting header + Ask card), and the tappable
      // Ask card's InkWell hit area meets the ≥48dp minimum.
      final askInkWell = find.ancestor(
        of: find.text('Hỏi CLARA'),
        matching: find.byType(InkWell),
      );
      expect(askInkWell, findsWidgets);
      final askHeight = tester.getSize(askInkWell.first).height;
      expect(askHeight, greaterThanOrEqualTo(A11y.minTapTargetDimension));
    });

    testWidgets('Home: text scales without crashing at large text scale',
        (tester) async {
      final apiClient = FakeApiClient()
        ..stub('getHomeV2', response: const {'schedule': [], 'recent_changes': []})
        ..stub('getMobileSummary', response: const {'feature_flags': {}});
      final sessionStore = await FakeSessionStore.authenticated(role: 'normal');

      await tester.pumpWidget(
        wrap(
          HomeScreenV3(
            apiClient: apiClient,
            sessionStore: sessionStore,
            resolver: MobileFeatureFlagResolver(
              summary: const {'feature_flags': {}},
            ),
            summary: const {'schedule': [], 'recent_changes': []},
          ),
          // A11y clamps to 1.6, so this exercises the upper bound.
          textScale: 1.6,
        ),
      );
      await tester.pumpAndSettle();

      // Renders cleanly at the large text scale — no layout/build exception.
      expect(tester.takeException(), isNull);
      expect(find.text('Hỏi CLARA'), findsOneWidget);
    });
  });
}

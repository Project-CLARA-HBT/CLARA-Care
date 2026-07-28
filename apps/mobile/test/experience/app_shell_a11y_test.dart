// Accessibility + reduced-motion widget tests for the CLARA_Mobile
// Experience_V2 adaptive app shell (task 3.3).
//
// Covers two Correctness Properties against the shell's navigation chrome and
// body-swap transition:
//
//   * Property P3 (Accessibility invariants — Requirements 3.3): every
//     navigation control meets the ≥48dp minimum tap target (the shell wraps
//     each nav icon in `MinTapTarget`), the nav destinations expose non-empty
//     screen-reader labels, and the active body region exposes a header
//     semantics node carrying the destination's label.
//   * Property P2 (Reduced-motion collapse — Requirements 3.4): when reduced
//     motion is requested, the body-swap `AnimatedSwitcher` duration resolves
//     to `Duration.zero`, so selecting a different destination swaps the body
//     instantly (the new body is present after a single frame, with no settle),
//     versus a non-zero animated duration when motion is allowed.
//
// Pure widget tests: no platform channels, no live network (Requirement 10.5).
// Bodies are distinct keyed widgets so finding a body never collides with a
// `NavigationBar`/`NavigationRail` label of the same text.

import 'package:clara_mobile/core/a11y.dart';
import 'package:clara_mobile/experience/app_shell.dart';
import 'package:clara_mobile/theme/tokens.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/experience_pump.dart';

void main() {
  const homeBodyKey = Key('body-home');
  const toolsBodyKey = Key('body-tools');
  const settingsBodyKey = Key('body-settings');

  // Destination labels reused as the body region header labels by the shell.
  const homeLabel = 'Home';
  const toolsLabel = 'Tools';
  const settingsLabel = 'Settings';

  Widget buildShell({int initialIndex = 0}) {
    return AppShell(
      initialIndex: initialIndex,
      destinations: const [
        ShellDestination(
          icon: Icons.home_outlined,
          selectedIcon: Icons.home,
          label: homeLabel,
          body: Center(key: homeBodyKey, child: Text('Home body')),
        ),
        ShellDestination(
          icon: Icons.build_outlined,
          selectedIcon: Icons.build,
          label: toolsLabel,
          body: Center(key: toolsBodyKey, child: Text('Tools body')),
        ),
        ShellDestination(
          icon: Icons.settings_outlined,
          selectedIcon: Icons.settings,
          label: settingsLabel,
          body: Center(key: settingsBodyKey, child: Text('Settings body')),
        ),
      ],
    );
  }

  group('AppShell accessibility invariants (Property P3, Requirement 3.3)', () {
    testWidgets(
        'every navigation control meets the \u226548dp minimum tap target '
        '(bottom nav, phone width)', (tester) async {
      await pumpAtPhoneWidth(tester, buildShell());
      await tester.pumpAndSettle();

      // The shell guarantees ≥48dp by wrapping each nav icon in MinTapTarget.
      final targets = find.byType(MinTapTarget);
      expect(targets, findsAtLeastNWidgets(3),
          reason: 'expected one MinTapTarget per nav destination');

      final count = tester.widgetList(targets).length;
      for (var i = 0; i < count; i++) {
        final size = tester.getSize(targets.at(i));
        expect(size.width, greaterThanOrEqualTo(A11y.minTapTargetDimension),
            reason: 'nav control $i width must be \u226548dp');
        expect(size.height, greaterThanOrEqualTo(A11y.minTapTargetDimension),
            reason: 'nav control $i height must be \u226548dp');
      }
    });

    testWidgets(
        'every navigation control meets the \u226548dp minimum tap target '
        '(nav rail, tablet width)', (tester) async {
      await pumpAtTabletWidth(tester, buildShell());
      await tester.pumpAndSettle();

      final targets = find.byType(MinTapTarget);
      expect(targets, findsAtLeastNWidgets(3),
          reason: 'expected one MinTapTarget per nav destination');

      final count = tester.widgetList(targets).length;
      for (var i = 0; i < count; i++) {
        final size = tester.getSize(targets.at(i));
        expect(size.width, greaterThanOrEqualTo(A11y.minTapTargetDimension));
        expect(size.height, greaterThanOrEqualTo(A11y.minTapTargetDimension));
      }
    });

    testWidgets('navigation destinations expose non-empty screen-reader labels',
        (tester) async {
      final handle = tester.ensureSemantics();
      await pumpAtPhoneWidth(tester, buildShell());
      await tester.pumpAndSettle();

      // Each destination announces its own label via the nav control.
      expect(
        find.bySemanticsLabel(RegExp('^$homeLabel(?:\\n|\$)')),
        findsAtLeastNWidgets(1),
      );
      expect(
        find.bySemanticsLabel(RegExp('^$toolsLabel(?:\\n|\$)')),
        findsAtLeastNWidgets(1),
      );
      expect(
        find.bySemanticsLabel(RegExp('^$settingsLabel(?:\\n|\$)')),
        findsAtLeastNWidgets(1),
      );

      handle.dispose();
    });

    testWidgets(
        'active body region exposes a header semantics node labeled '
        'with the destination', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpAtPhoneWidth(tester, buildShell());
      await tester.pumpAndSettle();

      // The shell wraps the active body in A11yLabeled(isHeader: true) with the
      // destination label, so the body region is announced as a header.
      final homeSemantics = tester.getSemantics(find.byKey(homeBodyKey));
      expect(homeSemantics.label, startsWith(homeLabel));
      expect(
        homeSemantics.flagsCollection.isHeader,
        isTrue,
        reason: 'Home body region must expose a labeled header semantics node',
      );

      // Selecting another destination moves the header label with the body.
      await tester.tap(find.text(settingsLabel));
      await tester.pumpAndSettle();

      final settingsSemantics =
          tester.getSemantics(find.byKey(settingsBodyKey));
      expect(settingsSemantics.label, startsWith(settingsLabel));
      expect(
        settingsSemantics.flagsCollection.isHeader,
        isTrue,
        reason: 'Settings body region must expose a labeled header node',
      );

      handle.dispose();
    });
  });

  group('AppShell reduced-motion collapse (Property P2, Requirement 3.4)', () {
    testWidgets(
        'body-swap AnimatedSwitcher duration collapses to Duration.zero under '
        'reduced motion', (tester) async {
      await pumpAtPhoneWidth(tester, buildShell(), reducedMotion: true);
      await tester.pumpAndSettle();

      final switcher =
          tester.widget<AnimatedSwitcher>(find.byType(AnimatedSwitcher));
      expect(switcher.duration, Duration.zero,
          reason: 'reduced motion must resolve the body-swap to instant');
    });

    testWidgets(
        'body-swap AnimatedSwitcher keeps its animated duration when motion is '
        'allowed', (tester) async {
      await pumpAtPhoneWidth(tester, buildShell());
      await tester.pumpAndSettle();

      final switcher =
          tester.widget<AnimatedSwitcher>(find.byType(AnimatedSwitcher));
      expect(switcher.duration, ClaraTokens.motionMedium,
          reason: 'motion allowed must keep the standard transition duration');
    });

    testWidgets(
        'selecting a destination under reduced motion swaps the body instantly '
        '(single frame, no settle)', (tester) async {
      await pumpAtPhoneWidth(tester, buildShell(), reducedMotion: true);
      await tester.pumpAndSettle();
      expect(find.byKey(homeBodyKey), findsOneWidget);

      // Select Tools, then advance a SINGLE frame (not pumpAndSettle): with a
      // zero-duration switcher the new body is already present immediately.
      await tester.tap(find.text(toolsLabel));
      await tester.pump();

      expect(find.byKey(toolsBodyKey), findsOneWidget,
          reason: 'new body must appear immediately under reduced motion');

      // Settling changes nothing further (the swap was already instant).
      await tester.pumpAndSettle();
      expect(find.byKey(toolsBodyKey), findsOneWidget);
      expect(find.byKey(homeBodyKey), findsNothing);
    });
  });
}

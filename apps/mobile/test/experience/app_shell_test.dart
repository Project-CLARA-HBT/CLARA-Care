// Widget tests for the CLARA_Mobile Experience_V2 adaptive app shell (task 3.2).
//
// Covers the Requirement 3 acceptance criteria exercised by the shell's
// adaptive layout + selection persistence:
//   * 3.1 — The shell presents a bottom `NavigationBar` on compact (phone)
//     widths and a side `NavigationRail` on medium/expanded (tablet) widths,
//     switching at the 600dp breakpoint.
//   * 3.2 — The shell exposes the primary destinations and preserves the
//     selected destination across width changes (phone⇄tablet) and across an
//     orientation change (tablet portrait⇄landscape).
//
// Pure widget tests: no platform channels, no live network (Requirement 10.5).
// They lean on the shared `pumpExperience` harness for surface-size control and
// `resizeSurface` to flip the width class after an initial pump.

import 'package:clara_mobile/experience/app_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/experience_pump.dart';

void main() {
  // Body keys are distinct from the destination labels so finding a body never
  // collides with a `NavigationBar`/`NavigationRail` label of the same text.
  const homeBodyKey = Key('body-home');
  const toolsBodyKey = Key('body-tools');
  const settingsBodyKey = Key('body-settings');

  /// A small, self-contained shell with three destinations whose bodies are
  /// simple keyed widgets. Selection starts on Home (index 0).
  Widget buildShell({int initialIndex = 0}) {
    return AppShell(
      initialIndex: initialIndex,
      destinations: const [
        ShellDestination(
          icon: Icons.home_outlined,
          selectedIcon: Icons.home,
          label: 'Home',
          body: Center(key: homeBodyKey, child: Text('Home body')),
        ),
        ShellDestination(
          icon: Icons.build_outlined,
          selectedIcon: Icons.build,
          label: 'Tools',
          body: Center(key: toolsBodyKey, child: Text('Tools body')),
        ),
        ShellDestination(
          icon: Icons.settings_outlined,
          selectedIcon: Icons.settings,
          label: 'Settings',
          body: Center(key: settingsBodyKey, child: Text('Settings body')),
        ),
      ],
    );
  }

  group('AppShell adaptive layout (Requirement 3.1)', () {
    testWidgets('renders a bottom NavigationBar at phone width', (tester) async {
      await pumpAtPhoneWidth(tester, buildShell());
      await tester.pumpAndSettle();

      expect(find.byType(NavigationBar), findsOneWidget);
      expect(find.byType(NavigationRail), findsNothing);
      // The selected destination's body is shown.
      expect(find.byKey(homeBodyKey), findsOneWidget);
    });

    testWidgets('renders a NavigationRail at tablet width', (tester) async {
      await pumpAtTabletWidth(tester, buildShell());
      await tester.pumpAndSettle();

      expect(find.byType(NavigationRail), findsOneWidget);
      expect(find.byType(NavigationBar), findsNothing);
      expect(find.byKey(homeBodyKey), findsOneWidget);
    });
  });

  group('AppShell selection persistence (Requirement 3.2)', () {
    testWidgets(
        'preserves selected destination across phone\u2192tablet width change',
        (tester) async {
      await pumpAtPhoneWidth(tester, buildShell());
      await tester.pumpAndSettle();

      // Sanity: compact layout, Home selected.
      expect(find.byType(NavigationBar), findsOneWidget);
      expect(find.byKey(homeBodyKey), findsOneWidget);

      // Select the second destination (Tools) via the bottom nav.
      await tester.tap(find.text('Tools'));
      await tester.pumpAndSettle();
      expect(find.byKey(toolsBodyKey), findsOneWidget);
      expect(find.byKey(homeBodyKey), findsNothing);

      // Flip to a tablet width: the shell switches to the rail but must keep
      // the same selection (index lives in State, not derived from width).
      await resizeSurface(tester, kTabletSurfaceSize);
      await tester.pumpAndSettle();

      expect(find.byType(NavigationRail), findsOneWidget);
      expect(find.byType(NavigationBar), findsNothing);
      // Selection preserved: Tools body still shown, Home/Settings not.
      expect(find.byKey(toolsBodyKey), findsOneWidget);
      expect(find.byKey(homeBodyKey), findsNothing);
      expect(find.byKey(settingsBodyKey), findsNothing);
    });

    testWidgets(
        'preserves selected destination across tablet\u2192phone width change',
        (tester) async {
      await pumpAtTabletWidth(tester, buildShell());
      await tester.pumpAndSettle();

      expect(find.byType(NavigationRail), findsOneWidget);

      // Select the third destination (Settings) via the rail.
      await tester.tap(find.text('Settings'));
      await tester.pumpAndSettle();
      expect(find.byKey(settingsBodyKey), findsOneWidget);

      // Flip down to a phone width: switches to the bottom nav, selection kept.
      await resizeSurface(tester, kPhoneSurfaceSize);
      await tester.pumpAndSettle();

      expect(find.byType(NavigationBar), findsOneWidget);
      expect(find.byType(NavigationRail), findsNothing);
      expect(find.byKey(settingsBodyKey), findsOneWidget);
      expect(find.byKey(homeBodyKey), findsNothing);
    });

    testWidgets(
        'preserves selected destination across an orientation change '
        '(tablet portrait\u2192landscape)', (tester) async {
      const tabletPortrait = kTabletSurfaceSize; // 834 x 1112
      const tabletLandscape = Size(1112, 834); // same expanded width class

      await pumpExperience(tester, buildShell(), surfaceSize: tabletPortrait);
      await tester.pumpAndSettle();

      expect(find.byType(NavigationRail), findsOneWidget);

      // Select Tools, then rotate to landscape (still expanded ⇒ still a rail).
      await tester.tap(find.text('Tools'));
      await tester.pumpAndSettle();
      expect(find.byKey(toolsBodyKey), findsOneWidget);

      await resizeSurface(tester, tabletLandscape);
      await tester.pumpAndSettle();

      // Same width class: still a rail, and the Tools selection is preserved
      // across the orientation change.
      expect(find.byType(NavigationRail), findsOneWidget);
      expect(find.byType(NavigationBar), findsNothing);
      expect(find.byKey(toolsBodyKey), findsOneWidget);
      expect(find.byKey(homeBodyKey), findsNothing);
    });
  });
}

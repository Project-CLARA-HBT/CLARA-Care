// Tests for MorphingDock (Spec v4 Section 5 & 6, SEH-052, SEH-053, SEH-057).

import 'package:clara_mobile/experience/redesign_shell.dart';
import 'package:clara_mobile/experience/spatial/clara_orb.dart';
import 'package:clara_mobile/experience/spatial/morphing_dock.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

List<RedesignDestination> _sampleDestinations() => const [
      RedesignDestination(
        icon: Icons.today_outlined,
        selectedIcon: Icons.today,
        label: 'Hôm nay',
        body: Text('BODY_TODAY'),
      ),
      RedesignDestination(
        icon: Icons.route_outlined,
        selectedIcon: Icons.route,
        label: 'LifeMap',
        body: Text('BODY_LIFEMAP'),
      ),
      RedesignDestination(
        icon: Icons.medication_outlined,
        selectedIcon: Icons.medication,
        label: 'Thuốc',
        body: Text('BODY_MEDICINES'),
      ),
      RedesignDestination(
        icon: Icons.folder_shared_outlined,
        selectedIcon: Icons.folder_shared,
        label: 'Hồ sơ',
        body: Text('BODY_PROFILE'),
      ),
    ];

void main() {
  group('MorphingDock — 5 Morph States', () {
    testWidgets('expanded state renders all destinations and center CLARA Orb',
        (tester) async {
      int? selected;
      var orbTapped = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: const Text('CONTENT'),
            bottomNavigationBar: MorphingDock(
              destinations: _sampleDestinations(),
              selectedIndex: 0,
              morphState: DockMorphState.expanded,
              onDestinationSelected: (idx) => selected = idx,
              onOrbTap: () => orbTapped = true,
              orbLabel: 'Hỏi CLARA',
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Hôm nay'), findsOneWidget);
      expect(find.text('LifeMap'), findsOneWidget);
      expect(find.text('Thuốc'), findsOneWidget);
      expect(find.text('Hồ sơ'), findsOneWidget);
      expect(find.bySemanticsLabel('Hỏi CLARA'), findsOneWidget);

      await tester.tap(find.text('Thuốc'));
      await tester.pump();
      expect(selected, 2);

      await tester.tap(find.bySemanticsLabel('Hỏi CLARA'));
      await tester.pump();
      expect(orbTapped, isTrue);
    });

    testWidgets('compact state renders condensed icon destinations',
        (tester) async {
      int? selected;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: const Text('CONTENT'),
            bottomNavigationBar: MorphingDock(
              destinations: _sampleDestinations(),
              selectedIndex: 1,
              morphState: DockMorphState.compact,
              onDestinationSelected: (idx) => selected = idx,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // In compact state, text labels are hidden/icon tooltips
      expect(find.text('Hôm nay'), findsNothing);
      expect(find.byIcon(Icons.today_outlined), findsOneWidget);
      expect(find.byIcon(Icons.route), findsOneWidget);

      await tester.tap(find.byIcon(Icons.today_outlined));
      await tester.pump();
      expect(selected, 0);
    });

    testWidgets('orbOnly state renders only the floating CLARA Orb',
        (tester) async {
      var orbTapped = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: const Text('CONTENT'),
            bottomNavigationBar: MorphingDock(
              destinations: _sampleDestinations(),
              selectedIndex: 0,
              morphState: DockMorphState.orbOnly,
              onDestinationSelected: (_) {},
              onOrbTap: () => orbTapped = true,
              orbLabel: 'Hỏi CLARA',
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Hôm nay'), findsNothing);
      expect(find.byType(ClaraOrb), findsOneWidget);

      await tester.tap(find.byType(ClaraOrb));
      await tester.pump();
      expect(orbTapped, isTrue);
    });

    testWidgets('contextual state renders custom contextual controls',
        (tester) async {
      var closed = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: const Text('CONTENT'),
            bottomNavigationBar: MorphingDock(
              destinations: _sampleDestinations(),
              selectedIndex: 0,
              morphState: DockMorphState.contextual,
              onDestinationSelected: (_) {},
              onContextualClose: () => closed = true,
              contextualChild: const Text('SCRIBE_RECORDING_BAR'),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('SCRIBE_RECORDING_BAR'), findsOneWidget);
      expect(find.byIcon(Icons.close), findsOneWidget);

      await tester.tap(find.byIcon(Icons.close));
      await tester.pump();
      expect(closed, isTrue);
    });

    testWidgets('hidden state renders escape reveal affordance',
        (tester) async {
      DockMorphState? toggledState;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: const Text('CONTENT'),
            bottomNavigationBar: MorphingDock(
              destinations: _sampleDestinations(),
              selectedIndex: 0,
              morphState: DockMorphState.hidden,
              onDestinationSelected: (_) {},
              onToggleMorph: (state) => toggledState = state,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Hiện thanh điều hướng'), findsOneWidget);

      await tester.tap(find.text('Hiện thanh điều hướng'));
      await tester.pump();
      expect(toggledState, DockMorphState.expanded);
    });
  });
}

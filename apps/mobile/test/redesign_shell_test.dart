// Widget tests for the redesign navigation shell (Experience_V3).
//
// clara-mobile-redesign, Requirement 2 (restructured IA with a centered
// circular Chat action). These lock the structural invariants of
// `RedesignShell`:
//
//   * On compact (phone) widths the center Chat action is always present and,
//     when tapped, swaps the body to the Chat surface (Requirement 2.1, 2.2).
//   * The flanking destinations render and switch the body (Requirement 2.4).
//   * Tapping a flanking destination from Chat leaves Chat and selects it.
//   * The selected slot is preserved across a relayout (Requirement 2.3).
//
// The shell renders a compact bottom bar (with the docked circular Chat FAB)
// below the 600dp breakpoint and a NavigationRail at/above it. The default test
// surface is 800x600 (rail), so tests that assert the compact bar/FAB pin a
// narrow phone surface first.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/experience/redesign_shell.dart';

Widget _host(Widget child) => MaterialApp(home: child);

/// Pins a compact (phone) surface (<600dp wide) so the shell renders the bottom
/// bar + docked Chat FAB, and resets it after the test.
void _useCompactSurface(WidgetTester tester) {
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  tester.view.devicePixelRatio = 1.0;
  tester.view.physicalSize = const Size(390, 844);
}

RedesignShell _shell({int initialIndex = 0}) {
  return RedesignShell(
    initialIndex: initialIndex,
    chatLabel: 'Trò chuyện',
    chatBody: const Center(child: Text('CHAT_BODY')),
    destinations: const [
      RedesignDestination(
        icon: Icons.home_outlined,
        label: 'Trang chủ',
        body: Center(child: Text('HOME_BODY')),
      ),
      RedesignDestination(
        icon: Icons.medication_outlined,
        label: 'Tủ thuốc',
        body: Center(child: Text('CABINET_BODY')),
      ),
      RedesignDestination(
        icon: Icons.folder_shared_outlined,
        label: 'Hồ sơ',
        body: Center(child: Text('PHR_BODY')),
      ),
      RedesignDestination(
        icon: Icons.apps_outlined,
        label: 'Thêm',
        body: Center(child: Text('MORE_BODY')),
      ),
    ],
  );
}

void main() {
  group('RedesignShell — centered Chat action (Requirement 2)', () {
    testWidgets('starts on the initial flanking destination, not Chat',
        (tester) async {
      _useCompactSurface(tester);
      await tester.pumpWidget(_host(_shell(initialIndex: 0)));
      await tester.pumpAndSettle();

      expect(find.text('HOME_BODY'), findsOneWidget);
      expect(find.text('CHAT_BODY'), findsNothing);
    });

    testWidgets('the center Chat action is always present and opens Chat',
        (tester) async {
      _useCompactSurface(tester);
      await tester.pumpWidget(_host(_shell(initialIndex: 0)));
      await tester.pumpAndSettle();

      // The center Chat action carries the chat label semantics.
      final chatAction = find.bySemanticsLabel('Trò chuyện');
      expect(chatAction, findsOneWidget);

      await tester.tap(chatAction);
      await tester.pumpAndSettle();

      expect(find.text('CHAT_BODY'), findsOneWidget);
      expect(find.text('HOME_BODY'), findsNothing);
    });

    testWidgets('tapping a flanking destination switches the body',
        (tester) async {
      _useCompactSurface(tester);
      await tester.pumpWidget(_host(_shell(initialIndex: 0)));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Tủ thuốc'));
      await tester.pumpAndSettle();

      expect(find.text('CABINET_BODY'), findsOneWidget);
      expect(find.text('HOME_BODY'), findsNothing);
    });

    testWidgets('leaving Chat for a flanking destination works',
        (tester) async {
      _useCompactSurface(tester);
      await tester.pumpWidget(_host(_shell(initialIndex: 0)));
      await tester.pumpAndSettle();

      await tester.tap(find.bySemanticsLabel('Trò chuyện'));
      await tester.pumpAndSettle();
      expect(find.text('CHAT_BODY'), findsOneWidget);

      await tester.tap(find.text('Hồ sơ'));
      await tester.pumpAndSettle();
      expect(find.text('PHR_BODY'), findsOneWidget);
      expect(find.text('CHAT_BODY'), findsNothing);
    });

    testWidgets('selection is preserved across a relayout (metrics change)',
        (tester) async {
      // Keep the SAME shell instance mounted, then change the view metrics so
      // the shell relayouts. Selection lives in State (not derived from width),
      // so it must survive the relayout (Requirement 2.3).
      _useCompactSurface(tester);
      await tester.pumpWidget(_host(_shell(initialIndex: 0)));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Tủ thuốc'));
      await tester.pumpAndSettle();
      expect(find.text('CABINET_BODY'), findsOneWidget);

      // Relayout the same tree (no new widget instance): shrink the surface.
      tester.view.physicalSize = const Size(360, 720);
      await tester.pumpAndSettle();

      // The live instance keeps its selection across the relayout.
      expect(find.text('CABINET_BODY'), findsOneWidget);
      expect(find.text('HOME_BODY'), findsNothing);
    });
  });
}

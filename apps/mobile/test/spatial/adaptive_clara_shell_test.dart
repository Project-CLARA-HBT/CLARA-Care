// Tests for AdaptiveClaraShell and ContextBar (Spec v4 Section 40, SEH-050, SEH-051).

import 'package:clara_mobile/experience/presentation_mode.dart';
import 'package:clara_mobile/experience/redesign_shell.dart';
import 'package:clara_mobile/experience/spatial/adaptive_clara_shell.dart';
import 'package:clara_mobile/experience/spatial/clara_orb.dart';
import 'package:clara_mobile/experience/spatial/morphing_dock.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

List<RedesignDestination> _sampleDestinations() => const [
      RedesignDestination(
        icon: Icons.today_outlined,
        selectedIcon: Icons.today,
        label: 'Hôm nay',
        body: Center(child: Text('BODY_TODAY')),
      ),
      RedesignDestination(
        icon: Icons.route_outlined,
        selectedIcon: Icons.route,
        label: 'LifeMap',
        body: Center(child: Text('BODY_LIFEMAP')),
      ),
      RedesignDestination(
        icon: Icons.medication_outlined,
        selectedIcon: Icons.medication,
        label: 'Thuốc',
        body: Center(child: Text('BODY_MEDICINES')),
      ),
      RedesignDestination(
        icon: Icons.folder_shared_outlined,
        selectedIcon: Icons.folder_shared,
        label: 'Hồ sơ',
        body: Center(child: Text('BODY_PROFILE')),
      ),
    ];

void _useCompactSurface(WidgetTester tester) {
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  tester.view.devicePixelRatio = 1.0;
  tester.view.physicalSize = const Size(390, 844);
}

void _useExpandedSurface(WidgetTester tester) {
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  tester.view.devicePixelRatio = 1.0;
  tester.view.physicalSize = const Size(900, 700);
}

void main() {
  group('AdaptiveClaraShell — Compact mobile layout (<600dp)', () {
    testWidgets('renders ContextBar and MorphingDock with active body',
        (tester) async {
      _useCompactSurface(tester);

      await tester.pumpWidget(
        MaterialApp(
          home: AdaptiveClaraShell(
            destinations: _sampleDestinations(),
            chatBody: const Center(child: Text('BODY_CHAT')),
            chatLabel: 'Hỏi CLARA',
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byType(ContextBar), findsOneWidget);
      expect(find.byType(MorphingDock), findsOneWidget);
      expect(find.text('BODY_TODAY'), findsOneWidget);
      expect(find.text('BODY_CHAT'), findsNothing);
    });

    testWidgets('tapping center Orb opens Chat body', (tester) async {
      _useCompactSurface(tester);

      await tester.pumpWidget(
        MaterialApp(
          home: AdaptiveClaraShell(
            destinations: _sampleDestinations(),
            chatBody: const Center(child: Text('BODY_CHAT')),
            chatLabel: 'Hỏi CLARA',
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byType(ClaraOrb));
      await tester.pumpAndSettle();

      expect(find.text('BODY_CHAT'), findsOneWidget);
      expect(find.text('BODY_TODAY'), findsNothing);

      // Tapping a destination returns to that destination
      await tester.tap(find.text('Thuốc'));
      await tester.pumpAndSettle();

      expect(find.text('BODY_MEDICINES'), findsOneWidget);
      expect(find.text('BODY_CHAT'), findsNothing);
    });

    testWidgets('selection is preserved across relayout / orientation change',
        (tester) async {
      _useCompactSurface(tester);

      await tester.pumpWidget(
        MaterialApp(
          home: AdaptiveClaraShell(
            destinations: _sampleDestinations(),
            chatBody: const Center(child: Text('BODY_CHAT')),
            chatLabel: 'Hỏi CLARA',
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('LifeMap'));
      await tester.pumpAndSettle();
      expect(find.text('BODY_LIFEMAP'), findsOneWidget);

      // Resize to wider surface
      _useExpandedSurface(tester);
      await tester.pumpAndSettle();

      expect(find.text('BODY_LIFEMAP'), findsOneWidget);
      expect(find.text('BODY_TODAY'), findsNothing);
    });
  });

  group('AdaptiveClaraShell — Expanded tablet layout (>=600dp)', () {
    testWidgets('renders NavigationRail with Chat and destinations',
        (tester) async {
      _useExpandedSurface(tester);

      await tester.pumpWidget(
        MaterialApp(
          home: AdaptiveClaraShell(
            destinations: _sampleDestinations(),
            chatBody: const Center(child: Text('BODY_CHAT')),
            chatLabel: 'Hỏi CLARA',
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byType(NavigationRail), findsOneWidget);
      expect(find.byType(ContextBar), findsOneWidget);
      expect(find.text('BODY_TODAY'), findsOneWidget);

      // Tap Chat in rail (index 0)
      await tester.tap(find.text('Hỏi CLARA'));
      await tester.pumpAndSettle();

      expect(find.text('BODY_CHAT'), findsOneWidget);
    });
  });

  group('ContextBar — workspace mode switching', () {
    testWidgets('allows multi-mode role (doctor) to open mode selector sheet',
        (tester) async {
      final modeController =
          PresentationModeController(initialRole: 'doctor');

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: PreferredSize(
              preferredSize: const Size.fromHeight(56),
              child: ContextBar(
                mode: modeController.mode,
                modeController: modeController,
                languageCode: 'vi',
              ),
            ),
            body: const Text('CONTENT'),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Lâm sàng'), findsOneWidget);

      // Tap on the mode badge
      await tester.tap(find.text('Lâm sàng'));
      await tester.pumpAndSettle();

      expect(find.text('Chọn không gian làm việc'), findsOneWidget);
      expect(find.text('Cá nhân'), findsOneWidget);
      expect(find.text('Nghiên cứu'), findsOneWidget);

      // Pick Personal mode
      await tester.tap(find.text('Cá nhân'));
      await tester.pumpAndSettle();

      expect(modeController.mode, PresentationMode.personal);
    });
  });
}

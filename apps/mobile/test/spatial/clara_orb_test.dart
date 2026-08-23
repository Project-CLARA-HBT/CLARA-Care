// Tests for ClaraOrb (Spec v4 Section 9, SEH-054, SEH-055, SEH-056).

import 'package:clara_mobile/experience/spatial/clara_orb.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('ClaraOrb — 7 interaction states & localized labels', () {
    test('State labels in Vietnamese and English', () {
      expect(ClaraOrbState.idle.labelVi, 'CLARA Orb (Đang chờ)');
      expect(ClaraOrbState.idle.labelEn, 'CLARA Orb (Idle)');

      expect(ClaraOrbState.hoverFocus.labelVi, 'CLARA Orb (Tiêu điểm)');
      expect(ClaraOrbState.hoverFocus.labelEn, 'CLARA Orb (Focused)');

      expect(ClaraOrbState.listening.labelVi, 'CLARA Orb (Đang lắng nghe)');
      expect(ClaraOrbState.listening.labelEn, 'CLARA Orb (Listening)');

      expect(ClaraOrbState.processing.labelVi, 'CLARA Orb (Đang xử lý)');
      expect(ClaraOrbState.processing.labelEn, 'CLARA Orb (Processing)');

      expect(ClaraOrbState.ready.labelVi, 'CLARA Orb (Sẵn sàng)');
      expect(ClaraOrbState.ready.labelEn, 'CLARA Orb (Ready)');

      expect(ClaraOrbState.attention.labelVi, 'CLARA Orb (Cần chú ý)');
      expect(ClaraOrbState.attention.labelEn, 'CLARA Orb (Attention)');

      expect(ClaraOrbState.error.labelVi, 'CLARA Orb (Lỗi kết nối)');
      expect(ClaraOrbState.error.labelEn, 'CLARA Orb (Error)');
    });

    for (final state in ClaraOrbState.values) {
      testWidgets('renders state $state with accessible semantics',
          (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: Center(
                child: ClaraOrb(
                  state: state,
                  languageCode: 'vi',
                ),
              ),
            ),
          ),
        );
        await tester.pump();

        expect(find.byType(ClaraOrb), findsOneWidget);
        expect(
          find.bySemanticsLabel(state.labelVi),
          findsOneWidget,
        );
      });
    }
  });

  group('ClaraOrb — interactivity & touch targets', () {
    testWidgets('triggers onTap callback when pressed', (tester) async {
      var tapped = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: ClaraOrb(
                state: ClaraOrbState.idle,
                onTap: () => tapped = true,
              ),
            ),
          ),
        ),
      );
      await tester.pump();

      await tester.tap(find.byType(ClaraOrb));
      await tester.pump();

      expect(tapped, isTrue);
    });

    testWidgets('triggers onLongPress callback when held', (tester) async {
      var longPressed = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: ClaraOrb(
                state: ClaraOrbState.idle,
                onLongPress: () => longPressed = true,
              ),
            ),
          ),
        ),
      );
      await tester.pump();

      await tester.longPress(find.byType(ClaraOrb));
      await tester.pump();

      expect(longPressed, isTrue);
    });

    testWidgets('supports custom accessibility label and tooltip',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Center(
              child: ClaraOrb(
                customLabel: 'Trợ lý CLARA',
                tooltip: 'Hỏi CLARA điều gì đó',
              ),
            ),
          ),
        ),
      );
      await tester.pump();

      expect(find.bySemanticsLabel('Trợ lý CLARA'), findsOneWidget);
      expect(find.byTooltip('Hỏi CLARA điều gì đó'), findsOneWidget);
    });
  });

  group('ClaraOrb — reduced motion support', () {
    testWidgets('renders cleanly under reduced motion without animation errors',
        (tester) async {
      await tester.pumpWidget(
        const MediaQuery(
          data: MediaQueryData(disableAnimations: true),
          child: MaterialApp(
            home: Scaffold(
              body: Center(
                child: ClaraOrb(
                  state: ClaraOrbState.processing,
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pump();

      expect(find.byType(ClaraOrb), findsOneWidget);
      expect(
        find.bySemanticsLabel(ClaraOrbState.processing.labelVi),
        findsOneWidget,
      );
    });
  });
}

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/experience/presentation_mode.dart';

void main() {
  group('4-mode presentation architecture (Mobile parity)', () {
    test('defines all 4 canonical presentation modes', () {
      expect(PresentationMode.values, [
        PresentationMode.personal,
        PresentationMode.clinical,
        PresentationMode.research,
        PresentationMode.admin,
      ]);
    });

    test('default mappings by role match specification', () {
      expect(defaultModeForRole('normal'), PresentationMode.personal);
      expect(defaultModeForRole(''), PresentationMode.personal);
      expect(defaultModeForRole(null), PresentationMode.personal);
      expect(defaultModeForRole('unknown'), PresentationMode.personal);

      expect(defaultModeForRole('doctor'), PresentationMode.clinical);
      expect(defaultModeForRole('DOCTOR'), PresentationMode.clinical);

      expect(defaultModeForRole('researcher'), PresentationMode.research);
      expect(defaultModeForRole('RESEARCHER'), PresentationMode.research);

      expect(defaultModeForRole('admin'), PresentationMode.admin);
      expect(defaultModeForRole('ADMIN'), PresentationMode.admin);
    });

    test('permitted modes by role allow doctors, researchers, admins to switch to Personal view', () {
      // Normal role has only Personal mode
      expect(permittedModesForRole('normal'), [PresentationMode.personal]);
      expect(isModePermittedForRole(PresentationMode.personal, 'normal'), isTrue);
      expect(isModePermittedForRole(PresentationMode.clinical, 'normal'), isFalse);
      expect(isModePermittedForRole(PresentationMode.research, 'normal'), isFalse);
      expect(isModePermittedForRole(PresentationMode.admin, 'normal'), isFalse);

      // Doctor role has Personal, Clinical, and Research
      expect(permittedModesForRole('doctor'), [
        PresentationMode.personal,
        PresentationMode.clinical,
        PresentationMode.research,
      ]);
      expect(isModePermittedForRole(PresentationMode.personal, 'doctor'), isTrue);
      expect(isModePermittedForRole(PresentationMode.clinical, 'doctor'), isTrue);
      expect(isModePermittedForRole(PresentationMode.research, 'doctor'), isTrue);
      expect(isModePermittedForRole(PresentationMode.admin, 'doctor'), isFalse);

      // Researcher role has Personal and Research
      expect(permittedModesForRole('researcher'), [
        PresentationMode.personal,
        PresentationMode.research,
      ]);
      expect(isModePermittedForRole(PresentationMode.personal, 'researcher'), isTrue);
      expect(isModePermittedForRole(PresentationMode.clinical, 'researcher'), isFalse);
      expect(isModePermittedForRole(PresentationMode.research, 'researcher'), isTrue);
      expect(isModePermittedForRole(PresentationMode.admin, 'researcher'), isFalse);

      // Admin role has all 4 modes
      expect(permittedModesForRole('admin'), [
        PresentationMode.personal,
        PresentationMode.clinical,
        PresentationMode.research,
        PresentationMode.admin,
      ]);
      expect(isModePermittedForRole(PresentationMode.personal, 'admin'), isTrue);
      expect(isModePermittedForRole(PresentationMode.clinical, 'admin'), isTrue);
      expect(isModePermittedForRole(PresentationMode.research, 'admin'), isTrue);
      expect(isModePermittedForRole(PresentationMode.admin, 'admin'), isTrue);
    });

    test('PresentationModeController manages role-gated switching and locks out unauthorized modes', () {
      // Doctor starts in Clinical mode by default
      final doctorController = PresentationModeController(initialRole: 'doctor');
      expect(doctorController.mode, PresentationMode.clinical);
      expect(doctorController.canSwitchModes, isTrue);

      // Doctor explicitly switches to Personal view
      expect(doctorController.setMode(PresentationMode.personal), isTrue);
      expect(doctorController.mode, PresentationMode.personal);

      // Doctor switches to Research view
      expect(doctorController.setMode(PresentationMode.research), isTrue);
      expect(doctorController.mode, PresentationMode.research);

      // Doctor is blocked from Administration mode (fail-closed)
      expect(doctorController.setMode(PresentationMode.admin), isFalse);
      expect(doctorController.mode, PresentationMode.research); // unchanged

      // Normal consumer controller cannot switch modes
      final normalController = PresentationModeController(initialRole: 'normal');
      expect(normalController.mode, PresentationMode.personal);
      expect(normalController.canSwitchModes, isFalse);
      expect(normalController.setMode(PresentationMode.clinical), isFalse);
      expect(normalController.mode, PresentationMode.personal);
    });

    test('PresentationModeController safely falls back when role changes', () {
      final controller = PresentationModeController(initialRole: 'admin');
      expect(controller.mode, PresentationMode.admin);

      // Downgrade to researcher: admin mode is no longer permitted, falls back to research
      controller.updateRole('researcher');
      expect(controller.mode, PresentationMode.research);

      // Downgrade to normal: falls back to personal
      controller.updateRole('normal');
      expect(controller.mode, PresentationMode.personal);
    });

    test('PresentationModeMeta provides Vietnamese and English localization', () {
      final personal = kPresentationModeMeta[PresentationMode.personal]!;
      expect(personal.label('vi'), 'Cá nhân');
      expect(personal.label('en'), 'Personal');

      final clinical = kPresentationModeMeta[PresentationMode.clinical]!;
      expect(clinical.label('vi'), 'Lâm sàng');
      expect(clinical.label('en'), 'Clinical');

      final research = kPresentationModeMeta[PresentationMode.research]!;
      expect(research.label('vi'), 'Nghiên cứu');
      expect(research.label('en'), 'Research');

      final admin = kPresentationModeMeta[PresentationMode.admin]!;
      expect(admin.label('vi'), 'Quản trị');
      expect(admin.label('en'), 'Administration');
    });

    testWidgets('PresentationModeSelectorSheet renders permitted modes and triggers selection', (tester) async {
      final controller = PresentationModeController(initialRole: 'doctor');

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: PresentationModeSelectorSheet(
              controller: controller,
              languageCode: 'vi',
            ),
          ),
        ),
      );

      // Should render Personal, Clinical, Research for a doctor
      expect(find.text('Cá nhân'), findsOneWidget);
      expect(find.text('Lâm sàng'), findsOneWidget);
      expect(find.text('Nghiên cứu'), findsOneWidget);
      // Admin should NOT be rendered for a doctor
      expect(find.text('Quản trị'), findsNothing);

      // Tap on Personal
      await tester.tap(find.text('Cá nhân'));
      await tester.pump();

      expect(controller.mode, PresentationMode.personal);
    });
  });
}

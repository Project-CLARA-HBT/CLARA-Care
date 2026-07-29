import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  group('active mobile surfaces use semantic light-mode colors', () {
    final files = <String>[
      'lib/experience/redesign_shell.dart',
      'lib/experience/redesign/phr_completeness.dart',
      'lib/experience/redesign/cabinet_insights.dart',
      'lib/theme/glass/glass_surface.dart',
    ];

    test('does not restore fixed feature status shades or glass glow colors',
        () {
      for (final path in files) {
        final source = File(path).readAsStringSync();

        expect(
          source,
          isNot(contains('Colors.green.shade')),
          reason: '$path must resolve success from ClaraStatusColors.',
        );
        expect(
          source,
          isNot(contains('Colors.orange.shade')),
          reason: '$path must resolve warning from ClaraStatusColors.',
        );
      }

      final shell = File(files.first).readAsStringSync();
      expect(shell, isNot(contains('Color.lerp(')));
      expect(shell, isNot(contains('Colors.white.withValues')));
      expect(shell, isNot(contains('Colors.black.withValues')));
      expect(shell, isNot(contains('scheme.primary.withValues(alpha: 0.40)')));

      final glass = File(files.last).readAsStringSync();
      expect(glass, isNot(contains('const Color(')));
      expect(glass, isNot(contains('Colors.white')));
      expect(glass, contains('scheme.surface'));
      expect(glass, contains('scheme.outlineVariant'));
    });
  });
}

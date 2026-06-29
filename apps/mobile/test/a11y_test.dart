// Feature: clara-mobile-feature-parity — Task 12.3 (Req 10.1–10.5; Property P14).
//
// Focused tests for the accessibility helpers in `core/a11y.dart`:
//   * The reduced-motion resolver reads MediaQuery.disableAnimations /
//     accessibleNavigation and collapses non-essential animation to zero
//     (Req 10.4), mirroring the web `usePrefersReducedMotion` behavior.
//   * The ≥48dp minimum tap-target wrapper enforces the platform touch-target
//     minimum and exposes a semantics label (Req 10.1, 10.2).
//
// These run under `flutter test` with no platform channels or live network
// (Requirement 14.6).

import 'package:clara_mobile/core/a11y.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Pumps [child] under a [MaterialApp] with an overridden [MediaQueryData] so
/// the reduced-motion / text-scaling resolvers can be exercised deterministically.
Future<void> _pumpWithMedia(
  WidgetTester tester,
  MediaQueryData media,
  Widget child,
) async {
  await tester.pumpWidget(
    MaterialApp(
      home: MediaQuery(
        data: media,
        child: Scaffold(body: Center(child: child)),
      ),
    ),
  );
}

void main() {
  group('reduced-motion resolver (Req 10.4)', () {
    test('prefersReducedMotionData honours disableAnimations', () {
      const base = MediaQueryData();
      expect(A11y.prefersReducedMotionData(base), isFalse);
      expect(
        A11y.prefersReducedMotionData(
          base.copyWith(disableAnimations: true),
        ),
        isTrue,
      );
    });

    test('prefersReducedMotionData honours accessibleNavigation', () {
      const base = MediaQueryData();
      expect(
        A11y.prefersReducedMotionData(
          base.copyWith(accessibleNavigation: true),
        ),
        isTrue,
      );
    });

    testWidgets('prefersReducedMotion returns false without a MediaQuery',
        (tester) async {
      late bool resolved;
      await tester.pumpWidget(
        Builder(
          builder: (context) {
            resolved = A11y.prefersReducedMotion(context);
            return const SizedBox.shrink();
          },
        ),
      );
      expect(resolved, isFalse);
    });

    testWidgets('resolveMotionDuration collapses to zero under reduced motion',
        (tester) async {
      late Duration motionOn;
      late Duration motionOff;

      await _pumpWithMedia(
        tester,
        const MediaQueryData(disableAnimations: true),
        Builder(
          builder: (context) {
            motionOn = A11y.resolveMotionDuration(
              context,
              const Duration(milliseconds: 300),
            );
            return const SizedBox.shrink();
          },
        ),
      );
      expect(motionOn, Duration.zero);

      await _pumpWithMedia(
        tester,
        const MediaQueryData(),
        Builder(
          builder: (context) {
            motionOff = A11y.resolveMotionDuration(
              context,
              const Duration(milliseconds: 300),
            );
            return const SizedBox.shrink();
          },
        ),
      );
      expect(motionOff, const Duration(milliseconds: 300));
    });

    testWidgets('ReducedMotionBuilder exposes the resolved preference',
        (tester) async {
      await _pumpWithMedia(
        tester,
        const MediaQueryData(disableAnimations: true),
        ReducedMotionBuilder(
          builder: (context, reduced) =>
              Text(reduced ? 'reduced' : 'full', textDirection: TextDirection.ltr),
        ),
      );
      expect(find.text('reduced'), findsOneWidget);
    });
  });

  group('minimum tap-target wrapper (Req 10.1, 10.2)', () {
    testWidgets('enforces a >=48dp hit area around a smaller child',
        (tester) async {
      final key = GlobalKey();
      await _pumpWithMedia(
        tester,
        const MediaQueryData(),
        MinTapTarget(
          key: key,
          semanticsLabel: 'Gửi',
          child: const SizedBox(width: 12, height: 12),
        ),
      );

      final size = tester.getSize(find.byKey(key));
      expect(size.width, greaterThanOrEqualTo(A11y.minTapTargetDimension));
      expect(size.height, greaterThanOrEqualTo(A11y.minTapTargetDimension));
    });

    testWidgets('exposes the supplied semantics label as a button',
        (tester) async {
      final handle = tester.ensureSemantics();
      await _pumpWithMedia(
        tester,
        const MediaQueryData(),
        const MinTapTarget(
          semanticsLabel: 'Gửi',
          child: SizedBox(width: 12, height: 12),
        ),
      );

      expect(
        tester.getSemantics(find.bySemanticsLabel('Gửi')),
        matchesSemantics(label: 'Gửi', isButton: true),
      );
      handle.dispose();
    });
  });

  group('status-by-text helper (Req 10.5)', () {
    testWidgets('renders the status text and a screen-reader value',
        (tester) async {
      final handle = tester.ensureSemantics();
      await _pumpWithMedia(
        tester,
        const MediaQueryData(),
        const StatusByText(
          label: 'Cao',
          level: A11yStatusLevel.danger,
          semanticsPrefix: 'Nguy cơ',
        ),
      );

      // Status conveyed by visible text, not color alone.
      expect(find.text('Cao'), findsOneWidget);
      // ...and announced with its prefix to assistive technology.
      expect(find.bySemanticsLabel('Nguy cơ: Cao'), findsOneWidget);
      handle.dispose();
    });
  });
}

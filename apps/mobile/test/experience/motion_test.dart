// Reduced-motion widget tests for the CLARA_Mobile Experience_V2
// micro-interaction primitives in `lib/experience/states/motion.dart`
// (task 7.2).
//
// Covers Correctness Property P2 (reduced-motion collapse — Requirements 7.2,
// 7.3) across all three motion primitives: when reduced motion is requested
// every non-essential animation duration resolves to `Duration.zero` while the
// functional state change (the tap, the rendered list, the pushed page content)
// still happens; when motion is allowed the same primitives keep their
// `ClaraTokens` base durations / animated wrappers.
//
//   * [ClaraPressable]: under reduced motion the press `AnimatedScale` resolves
//     to `Duration.zero` and a tap still fires `onTap` (counter increments)
//     after a single pump (no settle). Under motion allowed the duration is
//     `ClaraTokens.motionFast`.
//   * [ClaraListReveal]: under reduced motion every child is present/visible
//     immediately (after a single pump) and no reveal animation wraps them (the
//     per-item duration collapsed to zero ⇒ children rendered directly). Under
//     motion allowed every child still eventually appears (after settle).
//   * [ClaraPageTransitionsBuilder]: under a reduced-motion `MediaQuery` the
//     builder returns the child widget unchanged (instant, no transition);
//     under motion allowed it returns an animated transition wrapper.
//
// Pure widget tests: no platform channels, no live network (Requirement 10.5).
// Children are distinct keyed widgets so finds never collide.

import 'package:clara_mobile/experience/states/motion.dart';
import 'package:clara_mobile/theme/tokens.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/experience_pump.dart';

void main() {
  group('ClaraPressable reduced-motion collapse (Property P2, Req 7.2, 7.3)',
      () {
    testWidgets(
        'under reduced motion the press AnimatedScale resolves to '
        'Duration.zero and a tap still fires onTap', (tester) async {
      var tapCount = 0;
      await pumpExperience(
        tester,
        Center(
          child: ClaraPressable(
            onTap: () => tapCount++,
            child: const SizedBox(
              key: Key('pressable-child'),
              width: 120,
              height: 48,
              child: Text('Hồ sơ'),
            ),
          ),
        ),
        reducedMotion: true,
      );
      await tester.pumpAndSettle();

      // The press feedback animation collapses to instant under reduced motion.
      final scale = tester.widget<AnimatedScale>(
        find.descendant(
          of: find.byType(ClaraPressable),
          matching: find.byType(AnimatedScale),
        ),
      );
      expect(scale.duration, Duration.zero,
          reason: 'reduced motion must resolve the press scale to instant');

      // Functional state change still happens: tapping fires onTap after a
      // single pump (no settle needed because the animation is instant).
      await tester.tap(find.byKey(const Key('pressable-child')));
      await tester.pump();
      expect(tapCount, 1,
          reason: 'tap must still fire onTap under reduced motion');
    });

    testWidgets(
        'under motion allowed the press AnimatedScale keeps '
        'ClaraTokens.motionFast and a tap still fires onTap', (tester) async {
      var tapCount = 0;
      await pumpExperience(
        tester,
        Center(
          child: ClaraPressable(
            onTap: () => tapCount++,
            child: const SizedBox(
              key: Key('pressable-child'),
              width: 120,
              height: 48,
              child: Text('Hồ sơ'),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      final scale = tester.widget<AnimatedScale>(
        find.descendant(
          of: find.byType(ClaraPressable),
          matching: find.byType(AnimatedScale),
        ),
      );
      expect(scale.duration, ClaraTokens.motionFast,
          reason: 'motion allowed must keep the fast press duration');

      await tester.tap(find.byKey(const Key('pressable-child')));
      await tester.pumpAndSettle();
      expect(tapCount, 1, reason: 'tap must fire onTap when motion is allowed');
    });
  });

  group('ClaraListReveal reduced-motion collapse (Property P2, Req 7.2, 7.3)',
      () {
    const itemKeys = <Key>[
      Key('reveal-item-0'),
      Key('reveal-item-1'),
      Key('reveal-item-2'),
    ];

    Widget buildList() {
      return Center(
        child: ClaraListReveal(
          children: [
            for (var i = 0; i < itemKeys.length; i++)
              SizedBox(
                key: itemKeys[i],
                height: 40,
                child: Text('Mục $i'),
              ),
          ],
        ),
      );
    }

    testWidgets(
        'under reduced motion every child is present immediately and no reveal '
        'animation wraps them (per-item duration collapsed to zero)',
        (tester) async {
      await pumpExperience(tester, buildList(), reducedMotion: true);

      // A SINGLE pump (no settle): with the per-item duration resolved to zero
      // the children are rendered directly, so all are present at once.
      await tester.pump();
      for (final key in itemKeys) {
        expect(find.byKey(key), findsOneWidget,
            reason: 'child $key must render immediately under reduced motion');
      }

      // No fade/slide reveal wrapper exists inside the list when collapsed to
      // instant — children are returned directly by claraListRevealItem.
      expect(
        find.descendant(
          of: find.byType(ClaraListReveal),
          matching: find.byType(FadeTransition),
        ),
        findsNothing,
        reason: 'reduced motion must not wrap items in a reveal animation',
      );
      expect(
        find.descendant(
          of: find.byType(ClaraListReveal),
          matching: find.byType(SlideTransition),
        ),
        findsNothing,
        reason: 'reduced motion must not wrap items in a reveal animation',
      );
    });

    testWidgets(
        'under motion allowed every child still eventually appears after '
        'settle (no item missing)', (tester) async {
      await pumpExperience(tester, buildList());

      // The staggered reveal animates the items in; after settling all delayed
      // reveals have completed and every item is present and visible.
      await tester.pumpAndSettle();
      for (final key in itemKeys) {
        expect(find.byKey(key), findsOneWidget,
            reason: 'child $key must appear after the reveal completes');
      }
    });
  });

  group(
      'ClaraPageTransitionsBuilder reduced-motion collapse '
      '(Property P2, Req 7.2, 7.3)', () {
    // Capture a BuildContext that sits under the harness MediaQuery overrides so
    // the builder reads the configured reduced-motion preference.
    Future<BuildContext> pumpAndCaptureContext(
      WidgetTester tester, {
      required bool reducedMotion,
    }) async {
      late BuildContext captured;
      await pumpExperience(
        tester,
        Builder(
          builder: (context) {
            captured = context;
            return const SizedBox.shrink();
          },
        ),
        reducedMotion: reducedMotion,
      );
      await tester.pumpAndSettle();
      return captured;
    }

    testWidgets(
        'under reduced motion buildTransitions returns the child unchanged '
        '(instant, no transition)', (tester) async {
      final context = await pumpAndCaptureContext(tester, reducedMotion: true);

      const child = SizedBox(key: Key('page-content'), width: 10, height: 10);
      const animation = AlwaysStoppedAnimation<double>(0.0);
      const builder = ClaraPageTransitionsBuilder();

      final result = builder.buildTransitions<void>(
        null,
        context,
        animation,
        animation,
        child,
      );

      expect(identical(result, child), isTrue,
          reason: 'reduced motion must show the page instantly, child as-is');
    });

    testWidgets(
        'under motion allowed buildTransitions wraps the child in an animated '
        'transition (not the child directly)', (tester) async {
      final context = await pumpAndCaptureContext(tester, reducedMotion: false);

      const child = SizedBox(key: Key('page-content'), width: 10, height: 10);
      const animation = AlwaysStoppedAnimation<double>(0.0);
      const builder = ClaraPageTransitionsBuilder();

      final result = builder.buildTransitions<void>(
        null,
        context,
        animation,
        animation,
        child,
      );

      expect(identical(result, child), isFalse,
          reason: 'motion allowed must animate the incoming page');
      expect(result, isA<FadeTransition>(),
          reason: 'motion allowed composes a fade-through transition');
    });
  });
}

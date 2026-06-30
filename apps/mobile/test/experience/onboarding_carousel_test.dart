// Widget test for the first-run onboarding carousel (CLARA mobile experience
// spec, task 5.4 — Properties P2 and P3).
//
// Property P2 (design §"Correctness Properties"): for any Experience_V2
// animated surface, when reduced motion is requested every non-essential
// animation duration resolves to `Duration.zero`; functional state changes
// still occur.
//   Validates: Requirements 5.4 (carousel/transition animation collapses to
//   instant under reduced motion).
//
// Property P3 (design §"Correctness Properties"): every interactive
// Experience_V2 control exposes a non-empty semantics label and meets the
// ≥48dp minimum tap target, and status is conveyed by text/semantics, not
// color alone.
//   Validates: Requirements 5.4 (screen-reader semantics, ≥48dp controls).
//
// These cases drive the real `OnboardingCarousel` directly (pure UI + callbacks,
// no persistence / analytics — task 5.2 wires those) under the shared
// `pumpExperience` harness, with no platform channels or live network
// (Requirement 10.5). `onComplete` / `onSkip` are recorded with simple counter
// spies so the functional outcomes are asserted alongside the a11y/motion
// invariants.

import 'package:clara_mobile/core/a11y.dart';
import 'package:clara_mobile/experience/onboarding/onboarding_carousel.dart';
import 'package:clara_mobile/theme/components/clara_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../support/experience_pump.dart';

// --- Test keys / labels (mirrors the widget under test) ----------------------

final Finder _skip = find.byKey(const Key('onboarding-skip'));
final Finder _primary = find.byKey(const Key('onboarding-primary'));

const String _skipLabel = 'Bỏ qua phần giới thiệu';
const String _nextLabel = 'Tiếp tục';
const String _finishLabel = 'Bắt đầu';
const String _indicatorLabel = 'Tiến trình giới thiệu';

/// Records how many times `onComplete` / `onSkip` fire so the functional
/// outcomes (skip / finish) are asserted alongside the a11y/motion invariants.
class _CallbackSpy {
  int completeCount = 0;
  int skipCount = 0;
}

/// Builds the carousel under test wired to a fresh [_CallbackSpy]. The default
/// `OnboardingCarousel.defaultPages` (4 Vietnamese-first pages) are used so the
/// page-indicator value reads "Trang X trên 4".
Widget _carousel(_CallbackSpy spy) {
  return OnboardingCarousel(
    onComplete: () => spy.completeCount++,
    onSkip: () => spy.skipCount++,
  );
}

void main() {
  group('OnboardingCarousel — Property P3 (accessibility invariants)', () {
    testWidgets('skip control and primary button both meet the ≥48dp minimum',
        (tester) async {
      final spy = _CallbackSpy();
      await pumpExperience(tester, _carousel(spy));

      // Skip control is wrapped in `MinTapTarget`, which enforces ≥48dp on
      // both axes regardless of the visible TextButton size.
      final skipSize = tester.getSize(find.byType(MinTapTarget));
      expect(skipSize.width,
          greaterThanOrEqualTo(A11y.minTapTargetDimension));
      expect(skipSize.height,
          greaterThanOrEqualTo(A11y.minTapTargetDimension));

      // Primary action is a `ClaraButton.primary` (token-driven ≥48dp min
      // height); it is laid out full-width inside the SizedBox.
      expect(find.byType(ClaraButton), findsOneWidget);
      final primarySize = tester.getSize(_primary);
      expect(primarySize.width,
          greaterThanOrEqualTo(A11y.minTapTargetDimension));
      expect(primarySize.height,
          greaterThanOrEqualTo(A11y.minTapTargetDimension));
    });

    testWidgets('skip and primary controls expose non-empty button semantics',
        (tester) async {
      final handle = tester.ensureSemantics();
      final spy = _CallbackSpy();
      await pumpExperience(tester, _carousel(spy));

      // Skip exposes its descriptive Vietnamese label (not the visible "Bỏ qua"
      // text, which is excluded from semantics).
      expect(find.bySemanticsLabel(_skipLabel), findsOneWidget);

      // Primary exposes the context-sensitive label; on the first page it is
      // "Tiếp tục" (Next).
      expect(find.bySemanticsLabel(_nextLabel), findsOneWidget);

      handle.dispose();
    });

    testWidgets(
        'page indicator exposes a semantics value (status not color-only)',
        (tester) async {
      final handle = tester.ensureSemantics();
      final spy = _CallbackSpy();
      await pumpExperience(tester, _carousel(spy));

      // The dot indicator conveys progress through a semantics value
      // ("Trang 1 trên 4"), so it does not rely on color alone (Req 9.5).
      final node = tester.getSemantics(find.bySemanticsLabel(_indicatorLabel));
      expect(node.value, 'Trang 1 trên 4');

      handle.dispose();
    });
  });

  group('OnboardingCarousel — Property P2 (reduced-motion collapse)', () {
    testWidgets(
        'page-indicator AnimatedContainers collapse to Duration.zero under '
        'reduced motion', (tester) async {
      final spy = _CallbackSpy();
      await pumpExperience(tester, _carousel(spy), reducedMotion: true);

      // One AnimatedContainer per dot; every one resolves its duration through
      // A11y, so all collapse to Duration.zero under reduced motion.
      final dots = tester.widgetList<AnimatedContainer>(
        find.byType(AnimatedContainer),
      );
      expect(dots, isNotEmpty);
      for (final dot in dots) {
        expect(dot.duration, Duration.zero);
      }
    });

    testWidgets(
        'tapping primary advances the page after a single pump (no settle)',
        (tester) async {
      final handle = tester.ensureSemantics();
      final spy = _CallbackSpy();
      await pumpExperience(tester, _carousel(spy), reducedMotion: true);

      // Page 1 of 4 before interacting.
      expect(
        tester.getSemantics(find.bySemanticsLabel(_indicatorLabel)).value,
        'Trang 1 trên 4',
      );

      // `animateToPage` uses Duration.zero under reduced motion, so the page
      // advances instantly: a single frame pump (NOT pumpAndSettle) is enough
      // for the functional state change to land.
      await tester.tap(_primary);
      await tester.pump();

      expect(
        tester.getSemantics(find.bySemanticsLabel(_indicatorLabel)).value,
        'Trang 2 trên 4',
      );
      // Advancing an intermediate page must not complete onboarding.
      expect(spy.completeCount, 0);

      handle.dispose();
    });

    testWidgets('skip invokes onSkip without finishing onboarding',
        (tester) async {
      final spy = _CallbackSpy();
      await pumpExperience(tester, _carousel(spy), reducedMotion: true);

      await tester.tap(_skip);
      await tester.pump();

      expect(spy.skipCount, 1);
      expect(spy.completeCount, 0);
    });

    testWidgets(
        'finishing on the last page invokes onComplete under reduced motion',
        (tester) async {
      final spy = _CallbackSpy();
      await pumpExperience(tester, _carousel(spy), reducedMotion: true);

      // Advance to the final page by tapping "Tiếp tục"; under reduced motion
      // each advance lands after a single pump (no pumpAndSettle needed).
      var guard = 0;
      while (find.text(_finishLabel).evaluate().isEmpty && guard < 10) {
        await tester.tap(_primary);
        await tester.pump();
        guard++;
      }
      expect(find.text(_finishLabel), findsOneWidget,
          reason: 'should reach the final onboarding page');
      expect(spy.completeCount, 0,
          reason: 'completion only fires on the final-page confirmation');

      // Confirm the final page ⇒ onComplete fires exactly once.
      await tester.tap(_primary);
      await tester.pump();
      expect(spy.completeCount, 1);
      expect(spy.skipCount, 0);
    });
  });
}

// Smoke tests for the Experience_V2 test harness additions (CLARA mobile
// experience spec, task 1.1): the general-purpose fake secure storage and the
// width-class pumping helper. These verify the harness itself so the shell /
// Home / onboarding / theme tests built on top can trust it. No platform
// channels, no live network (Requirement 10.5).

import 'package:clara_mobile/core/session_store.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../fakes/fakes.dart';
import 'experience_pump.dart';

void main() {
  group('FakeSecureStorage', () {
    test('is a drop-in SessionSecureStorage that round-trips values', () async {
      final FakeSecureStorage storage = FakeSecureStorage();

      expect(storage, isA<SessionSecureStorage>());
      expect(storage.isEmpty, isTrue);

      await storage.write('clara.onboarding.seen', 'true');

      expect(storage.containsKey('clara.onboarding.seen'), isTrue);
      expect(await storage.read('clara.onboarding.seen'), 'true');
      expect(storage.writeCount, 1);
      expect(storage.snapshot, {'clara.onboarding.seen': 'true'});

      await storage.delete('clara.onboarding.seen');
      expect(storage.isEmpty, isTrue);
      expect(storage.deleteCount, 1);
    });

    test('seed models a returning user precondition', () async {
      final storage = FakeSecureStorage({'clara.language': 'vi'});
      expect(await storage.read('clara.language'), 'vi');

      storage.seed('clara.language', 'en');
      expect(await storage.read('clara.language'), 'en');
    });

    test('fault injection simulates a secure-storage outage', () async {
      final storage = FakeSecureStorage()..throwOnRead = true;
      await expectLater(storage.read('any'), throwsStateError);

      storage
        ..throwOnRead = false
        ..throwOnWrite = true;
      await expectLater(storage.write('k', 'v'), throwsStateError);
      // Failed write did not persist and did not bump the success counter.
      expect(storage.containsKey('k'), isFalse);
      expect(storage.writeCount, 0);
    });

    test('reset clears values, counters, and fault switches', () async {
      final storage = FakeSecureStorage({'k': 'v'})..throwOnWrite = true;
      await storage.read('k');

      storage.reset();

      expect(storage.isEmpty, isTrue);
      expect(storage.readCount, 0);
      expect(storage.throwOnWrite, isFalse);
    });
  });

  group('widthClassFor', () {
    test('classifies around the 600dp breakpoint', () {
      expect(widthClassFor(599.9), WidthClass.compact);
      expect(widthClassFor(kClaraTabletBreakpoint), WidthClass.expanded);
      expect(widthClassForSize(kPhoneSurfaceSize), WidthClass.compact);
      expect(widthClassForSize(kTabletSurfaceSize), WidthClass.expanded);
    });
  });

  group('pumpExperience', () {
    testWidgets('renders at the configured phone width', (tester) async {
      late Size seenSize;
      await pumpAtPhoneWidth(
        tester,
        Builder(
          builder: (context) {
            seenSize = MediaQuery.of(context).size;
            return const SizedBox.shrink();
          },
        ),
      );

      expect(seenSize, kPhoneSurfaceSize);
      expect(widthClassForSize(seenSize), WidthClass.compact);
    });

    testWidgets('renders at the configured tablet width', (tester) async {
      late Size seenSize;
      await pumpAtTabletWidth(
        tester,
        Builder(
          builder: (context) {
            seenSize = MediaQuery.of(context).size;
            return const SizedBox.shrink();
          },
        ),
      );

      expect(seenSize, kTabletSurfaceSize);
      expect(widthClassForSize(seenSize), WidthClass.expanded);
    });

    testWidgets('applies reduced-motion, text-scaler and brightness overrides',
        (tester) async {
      late MediaQueryData media;
      await pumpExperience(
        tester,
        Builder(
          builder: (context) {
            media = MediaQuery.of(context);
            return const SizedBox.shrink();
          },
        ),
        reducedMotion: true,
        accessibleNavigation: true,
        textScaler: const TextScaler.linear(1.3),
        platformBrightness: Brightness.dark,
      );

      expect(media.disableAnimations, isTrue);
      expect(media.accessibleNavigation, isTrue);
      expect(media.textScaler, const TextScaler.linear(1.3));
      expect(media.platformBrightness, Brightness.dark);
    });

    testWidgets('resizeSurface flips the width class without rebuilding root',
        (tester) async {
      final sizes = <Size>[];
      await pumpExperience(
        tester,
        Builder(
          builder: (context) {
            sizes.add(MediaQuery.of(context).size);
            return const SizedBox.shrink();
          },
        ),
        surfaceSize: kPhoneSurfaceSize,
      );

      await resizeSurface(tester, kTabletSurfaceSize);

      expect(widthClassForSize(sizes.first), WidthClass.compact);
      expect(widthClassForSize(sizes.last), WidthClass.expanded);
    });

    testWidgets('can pump a bare subtree without MaterialApp', (tester) async {
      await pumpExperience(
        tester,
        const Text('hello'),
        wrapInMaterialApp: false,
      );

      expect(find.text('hello'), findsOneWidget);
    });
  });
}

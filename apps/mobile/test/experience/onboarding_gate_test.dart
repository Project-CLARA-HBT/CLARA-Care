// Widget test for the first-run onboarding gate (CLARA mobile experience spec,
// task 5.3 — Property P5: Onboarding persistence).
//
// Property P5 (design §"Correctness Properties"): after onboarding is completed
// or skipped once, `OnboardingStore.hasSeenOnboarding()` returns true and
// onboarding is NOT shown on subsequent launches.
//   Validates: Requirements 5.1, 5.3, 5.6.
//
// These cases exercise the real `OnboardingGate` + `OnboardingStore` against an
// in-memory `OnboardingSecureStorage` (no platform channels, Requirement 10.5),
// and assert the coarse, no-PII complete/skip analytics events are emitted
// through a configured + consented `Analytics` wired to the shared recording
// transport fake.
//
// Cases:
//   (a) First run (store empty) ⇒ after the splash settles, the carousel shows.
//   (b) Skip ⇒ child shows, "seen" persists, a fresh gate shows child directly.
//   (c) Completion ⇒ advance to "Bắt đầu", child shows, "seen" persists, a
//       fresh gate shows child directly.
//   (d) seen=true initially ⇒ child shows directly, no carousel.
// Plus: analytics events recorded on skip/complete.

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/experience/onboarding/onboarding_gate.dart';
import 'package:clara_mobile/experience/onboarding/onboarding_store.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../fakes/fakes.dart';
import '../support/experience_pump.dart';

/// In-memory [OnboardingSecureStorage] for the onboarding store under test.
///
/// `OnboardingStore` reads/writes through this two-method seam, so the gate's
/// real persistence is exercised deterministically without `flutter_secure_storage`.
class InMemoryOnboardingStorage implements OnboardingSecureStorage {
  InMemoryOnboardingStorage([Map<String, String>? seed])
      : _data = <String, String>{...?seed};

  final Map<String, String> _data;

  /// Whether [key] currently has a persisted value.
  bool containsKey(String key) => _data.containsKey(key);

  @override
  Future<String?> read(String key) async => _data[key];

  @override
  Future<void> write(String key, String value) async => _data[key] = value;
}

/// Post-onboarding surface stand-in (the app would supply the AppShell here).
const Widget _child = Scaffold(
  body: Center(child: Text('CHILD', key: Key('post-onboarding-child'))),
);

/// Builds a configured + consented [Analytics] over the shared recording
/// transport so the gate's complete/skip events are actually captured.
Analytics _recordingAnalytics(RecordingAnalyticsTransport transport) {
  return Analytics(transport: transport)
    ..init(
      const AnalyticsConfig(provider: 'test', apiKey: 'k'),
      consentGranted: true,
    );
}

final Finder _carousel = find.byKey(const Key('onboarding-pageview'));
final Finder _splash = find.byKey(const Key('onboarding-gate-splash'));
final Finder _child_ = find.byKey(const Key('post-onboarding-child'));
final Finder _skip = find.byKey(const Key('onboarding-skip'));
final Finder _primary = find.byKey(const Key('onboarding-primary'));

void main() {
  group('OnboardingGate (Property P5: onboarding persistence)', () {
    testWidgets('(a) first run shows the carousel after the splash settles',
        (tester) async {
      final storage = InMemoryOnboardingStorage();
      final store = OnboardingStore(storage: storage);

      await pumpExperience(
        tester,
        OnboardingGate(store: store, child: _child),
      );

      // First frame: persisted flag still being read ⇒ minimal splash.
      expect(_splash, findsOneWidget);
      expect(_carousel, findsNothing);

      // Once the async read resolves (store empty ⇒ not seen) the carousel shows.
      await tester.pumpAndSettle();
      expect(_carousel, findsOneWidget);
      expect(_child_, findsNothing);
    });

    testWidgets(
        '(b) skip shows child, persists "seen", and a fresh gate skips onboarding',
        (tester) async {
      final storage = InMemoryOnboardingStorage();
      final store = OnboardingStore(storage: storage);
      final transport = RecordingAnalyticsTransport();
      final analytics = _recordingAnalytics(transport);

      await pumpExperience(
        tester,
        OnboardingGate(store: store, analytics: analytics, child: _child),
      );
      await tester.pumpAndSettle();
      expect(_carousel, findsOneWidget);

      // Skip on the first page.
      await tester.tap(_skip);
      await tester.pumpAndSettle();

      // Child is shown and "seen" is persisted.
      expect(_child_, findsOneWidget);
      expect(_carousel, findsNothing);
      expect(await store.hasSeenOnboarding(), isTrue);
      expect(storage.containsKey(OnboardingStore.seenKey), isTrue);

      // Coarse, no-PII skip event recorded (name only, no properties).
      expect(transport.capturedNames, contains(kOnboardingSkippedEvent));
      expect(transport.lastEvent?.props, isEmpty);

      // Reappear check: a fresh gate over the SAME (now-seen) store renders
      // the child directly — onboarding does not reappear (Property P5).
      await pumpExperience(
        tester,
        OnboardingGate(store: store, child: _child),
      );
      await tester.pumpAndSettle();
      expect(_child_, findsOneWidget);
      expect(_carousel, findsNothing);
    });

    testWidgets(
        '(c) completion shows child, persists "seen", and does not reappear',
        (tester) async {
      final storage = InMemoryOnboardingStorage();
      final store = OnboardingStore(storage: storage);
      final transport = RecordingAnalyticsTransport();
      final analytics = _recordingAnalytics(transport);

      await pumpExperience(
        tester,
        OnboardingGate(store: store, analytics: analytics, child: _child),
      );
      await tester.pumpAndSettle();
      expect(_carousel, findsOneWidget);

      // Advance through the pages: tap "Tiếp tục" until the primary becomes
      // "Bắt đầu" (the final page), then tap it to complete.
      var guard = 0;
      while (find.text('Bắt đầu').evaluate().isEmpty && guard < 10) {
        await tester.tap(_primary);
        await tester.pumpAndSettle();
        guard++;
      }
      expect(find.text('Bắt đầu'), findsOneWidget,
          reason: 'should reach the final onboarding page');

      // Confirm the final page ⇒ completes onboarding.
      await tester.tap(_primary);
      await tester.pumpAndSettle();

      expect(_child_, findsOneWidget);
      expect(_carousel, findsNothing);
      expect(await store.hasSeenOnboarding(), isTrue);
      expect(storage.containsKey(OnboardingStore.seenKey), isTrue);

      // Coarse, no-PII completion event recorded.
      expect(transport.capturedNames, contains(kOnboardingCompletedEvent));
      expect(transport.lastEvent?.props, isEmpty);

      // Reappear check: a fresh gate over the same store shows child directly.
      await pumpExperience(
        tester,
        OnboardingGate(store: store, child: _child),
      );
      await tester.pumpAndSettle();
      expect(_child_, findsOneWidget);
      expect(_carousel, findsNothing);
    });

    testWidgets('(d) seen=true initially shows child directly, no carousel',
        (tester) async {
      // Pre-seed the persisted "seen" flag to model a returning user.
      final storage = InMemoryOnboardingStorage(
        <String, String>{OnboardingStore.seenKey: 'true'},
      );
      final store = OnboardingStore(storage: storage);

      await pumpExperience(
        tester,
        OnboardingGate(store: store, child: _child),
      );
      await tester.pumpAndSettle();

      expect(_child_, findsOneWidget);
      expect(_carousel, findsNothing);
    });

    testWidgets(
        '(e) professional role (doctor) presents professional orientation without PHR questions',
        (tester) async {
      final storage = InMemoryOnboardingStorage();
      final store = OnboardingStore(storage: storage);
      final transport = RecordingAnalyticsTransport();
      final analytics = _recordingAnalytics(transport);

      await pumpExperience(
        tester,
        OnboardingGate(
          store: store,
          analytics: analytics,
          role: 'doctor',
          child: _child,
        ),
      );
      await tester.pumpAndSettle();

      // Carousel displays professional orientation content
      expect(_carousel, findsOneWidget);
      expect(find.text('CLARA cho công việc lâm sàng'), findsOneWidget);
      expect(
        find.text('CLARA là trợ lý AI hỗ trợ ra quyết định lâm sàng và tra cứu y khoa có dẫn chứng. CLARA không thay thế đánh giá chuyên môn của bạn.'),
        findsOneWidget,
      );

      // Verify no personal biometric prompts exist in the professional track
      expect(find.text('Chiều cao'), findsNothing);
      expect(find.text('Cân nặng'), findsNothing);
      expect(find.text('Nhóm máu'), findsNothing);

      // Skip directly to child post-onboarding surface (Council/Scribe/AppShell)
      await tester.tap(_skip);
      await tester.pumpAndSettle();

      expect(_child_, findsOneWidget);
      expect(_carousel, findsNothing);
      expect(await store.hasSeenOnboarding(), isTrue);
      expect(transport.capturedNames, contains(kOnboardingSkippedEvent));
    });
  });
}

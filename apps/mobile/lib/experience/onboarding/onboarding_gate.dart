// First-run onboarding gate for CLARA_Mobile Experience_V2 (Req 5.3, 5.5).
//
// [OnboardingGate] decides, on first authenticated render, whether to show the
// [OnboardingCarousel] or the post-onboarding [child] (e.g. the AppShell). It
// wires the carousel's pure UI callbacks (task 5.1) to persistence + analytics:
//
//   * On init it asynchronously reads `OnboardingStore.hasSeenOnboarding()`.
//     While that read is in flight it shows a minimal splash (a centered
//     `CircularProgressIndicator`) so launch is never blank.
//   * If onboarding has been seen ⇒ render [child].
//   * If not ⇒ render the [OnboardingCarousel].
//   * On complete/skip it persists "seen" via `OnboardingStore.markSeen()`,
//     emits a coarse, **no-PII** analytics event through the shared client,
//     then swaps to [child].
//
// Persistence + analytics are injectable ([store], [analytics]) so widget
// tests can supply an in-memory store and a recording analytics transport
// without platform channels.
//
// Graceful degradation (design Error Handling): `OnboardingStore` already
// degrades to "not seen" on read failure and swallows write failures, and the
// shared `Analytics` client already swallows transport errors and no-ops
// without consent/credentials. This widget additionally guards every async
// continuation with `mounted` and emits analytics last so nothing can throw
// into the navigation flow.
//
// Scope (task 5.2): create ONLY this file. App wiring (choosing this gate as
// the authenticated root behind `kMobileExperienceV2Enabled`) is task 9.1.

import 'package:flutter/material.dart';

import '../../core/analytics.dart';
import 'onboarding_carousel.dart';
import 'onboarding_store.dart';

/// Coarse, no-PII analytics event emitted when the user finishes onboarding by
/// confirming the final page ("Bắt đầu"). Carries no properties — no
/// free-text, names, or medical content (Req 5.5).
const String kOnboardingCompletedEvent = 'mobile_onboarding_completed';

/// Coarse, no-PII analytics event emitted when the user skips onboarding
/// ("Bỏ qua"). Carries no properties (Req 5.5).
const String kOnboardingSkippedEvent = 'mobile_onboarding_skipped';

/// Decides between first-run onboarding and the post-onboarding [child], and
/// persists "onboarding seen" + emits coarse no-PII analytics on complete/skip
/// (Req 5.3, 5.5).
///
/// Place this around the authenticated app root: when onboarding has not been
/// seen it renders [OnboardingCarousel]; otherwise (and after the carousel is
/// completed or skipped) it renders [child].
class OnboardingGate extends StatefulWidget {
  const OnboardingGate({
    super.key,
    required this.child,
    OnboardingStore? store,
    Analytics? analytics,
  })  : _store = store,
        _analytics = analytics;

  /// The post-onboarding app surface to show once onboarding is seen
  /// (typically the adaptive `AppShell`).
  final Widget child;

  /// Persistence for the "onboarding seen" flag. Defaults to a production
  /// [OnboardingStore] (over `flutter_secure_storage`). Injectable for tests.
  final OnboardingStore? _store;

  /// Analytics client for the coarse no-PII complete/skip events. Defaults to
  /// the shared [getAnalyticsClient]. Injectable for tests.
  final Analytics? _analytics;

  @override
  State<OnboardingGate> createState() => _OnboardingGateState();
}

class _OnboardingGateState extends State<OnboardingGate> {
  late final OnboardingStore _store = widget._store ?? OnboardingStore();
  late final Analytics _analytics = widget._analytics ?? getAnalyticsClient();

  /// `null` while the persisted flag is being read (show splash); `true` once
  /// onboarding is seen (show [child]); `false` to show the carousel.
  bool? _seen;

  @override
  void initState() {
    super.initState();
    _loadSeen();
  }

  /// Reads the persisted "seen" flag. `OnboardingStore` already degrades to
  /// `false` ("not seen") on any storage failure, so this never throws.
  Future<void> _loadSeen() async {
    final seen = await _store.hasSeenOnboarding();
    if (!mounted) {
      return;
    }
    setState(() => _seen = seen);
  }

  /// Persists "seen", emits the coarse no-PII [eventName], then renders
  /// [child]. The store swallows write failures and the analytics client
  /// swallows transport errors; the analytics call is made last so it can
  /// never interrupt the navigation swap.
  Future<void> _finish(String eventName) async {
    await _store.markSeen();
    if (!mounted) {
      return;
    }
    setState(() => _seen = true);
    // Coarse, no-PII event: name only, no properties (Req 5.5). Emitted last;
    // the shared client no-ops without consent/credentials and never throws.
    _analytics.track(eventName);
  }

  @override
  Widget build(BuildContext context) {
    final seen = _seen;

    // Loading: minimal splash while the persisted flag is read.
    if (seen == null) {
      return const Scaffold(
        body: Center(
          key: Key('onboarding-gate-splash'),
          child: CircularProgressIndicator(),
        ),
      );
    }

    // Seen: straight through to the post-onboarding app.
    if (seen) {
      return widget.child;
    }

    // First run: present the skippable onboarding carousel.
    return OnboardingCarousel(
      onComplete: () => _finish(kOnboardingCompletedEvent),
      onSkip: () => _finish(kOnboardingSkippedEvent),
    );
  }
}

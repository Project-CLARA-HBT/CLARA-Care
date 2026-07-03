// Tests for the redesigned Chat surface (Experience_V3, Task 9).
//
// clara-mobile-redesign, Requirement 9 (Chat as the central surface; Research
// unified into Chat's deep modes). The safety-critical R9 invariant is the
// fail-closed gating decision — the deep-research ("Nghiên cứu") tab and the
// mode header appear ONLY when the `research_mobile_deep` capability is granted.
//
// That decision is exposed as a pure helper (`chatSurfaceResearchDeepEnabled`)
// and tested directly here, so the invariant is locked without mounting the
// heavy child screens (`ChatScreen`/`ResearchScreen`), which own their own
// invariants and are covered by their own tests.

import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/experience/redesign/chat_surface_v3.dart';

MobileFeatureFlagResolver _resolver({
  bool chat = true,
  bool deepResearch = false,
}) =>
    MobileFeatureFlagResolver(
      summary: {
        'feature_flags': {
          if (chat) 'chat_mobile_enabled': true,
          if (deepResearch) 'research_mobile_deep': true,
        },
      },
    );

void main() {
  group('ChatSurfaceV3 — Research unified into Chat (Requirement 9)', () {
    test('research deep OFF ⇒ gating decision is false (fail-closed)', () {
      // No summary at all ⇒ every gate off.
      expect(
        chatSurfaceResearchDeepEnabled(MobileFeatureFlagResolver()),
        isFalse,
      );
      // Chat on, but deep research not granted ⇒ still false.
      expect(
        chatSurfaceResearchDeepEnabled(_resolver(deepResearch: false)),
        isFalse,
      );
    });

    test('research deep ON ⇒ gating decision is true', () {
      expect(
        chatSurfaceResearchDeepEnabled(_resolver(deepResearch: true)),
        isTrue,
      );
    });

    test('the gate key is the shared research_mobile_deep capability', () {
      expect(kChatSurfaceResearchDeepFlag, 'research_mobile_deep');
    });
  });
}

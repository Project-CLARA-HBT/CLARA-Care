// Typed registry and step-order guard for implemented CLARA mobile flows.
//
// This layer is intentionally navigation-framework-light. Existing screens
// may continue to use local state and MaterialPageRoute while attaching the
// stable [MobileFlowStep.routeName] to RouteSettings. Registering a step does
// not make it externally deep-linkable or grant authority to mutate data.

import 'package:flutter/widgets.dart';

/// Stable identifiers for mobile guided flows that exist today.
abstract final class MobileFlowIds {
  static const String unifiedOnboarding = 'unified_onboarding';
}

/// Stable identifiers for the currently implemented unified-onboarding steps.
abstract final class UnifiedOnboardingStepIds {
  static const String welcome = 'welcome';
  static const String basics = 'basics';
  static const String personalization = 'personalization';
}

/// A Vietnamese-first label with an English translation.
@immutable
class MobileFlowLabel {
  const MobileFlowLabel({required this.vi, required this.en});

  final String vi;
  final String en;

  String resolve(String languageCode) =>
      languageCode.toLowerCase().startsWith('en') ? en : vi;

  String resolveLocale(Locale locale) => resolve(locale.languageCode);
}

/// Authority carried by a step.
///
/// This is descriptive metadata, not an authorization decision. Domain APIs,
/// consent, RBAC, revisions, and idempotency remain authoritative.
enum MobileFlowStepAuthority {
  draft,
  review,
  commit,
}

/// One implemented step in a mobile flow.
@immutable
class MobileFlowStepDefinition {
  const MobileFlowStepDefinition({
    required this.id,
    required this.routeName,
    required this.legacyIndex,
    required this.title,
    required this.nextOutcome,
    required this.authority,
    this.optional = false,
  });

  final String id;

  /// Stable internal name suitable for Material [RouteSettings].
  ///
  /// It is not automatically exposed as a deep link.
  final String routeName;

  /// Index used by the current local-state implementation.
  final int legacyIndex;

  final MobileFlowLabel title;
  final MobileFlowLabel nextOutcome;
  final MobileFlowStepAuthority authority;
  final bool optional;

  RouteSettings get routeSettings => RouteSettings(name: routeName);
}

/// Definition of one actually implemented mobile flow.
@immutable
class MobileFlowDefinition {
  const MobileFlowDefinition({
    required this.id,
    required this.title,
    required this.steps,
  });

  final String id;
  final MobileFlowLabel title;
  final List<MobileFlowStepDefinition> steps;

  MobileFlowStepDefinition? step(String stepId) {
    for (final candidate in steps) {
      if (candidate.id == stepId) return candidate;
    }
    return null;
  }

  MobileFlowStepDefinition? stepAtLegacyIndex(int index) {
    for (final candidate in steps) {
      if (candidate.legacyIndex == index) return candidate;
    }
    return null;
  }
}

/// Content-free progress used by [MobileFlowStepGuard].
///
/// It stores step identifiers only. Health facts, form values, errors, user
/// identity, and free text do not belong in this object.
@immutable
class MobileFlowProgress {
  const MobileFlowProgress({
    this.completedStepIds = const <String>{},
    this.skippedStepIds = const <String>{},
  });

  final Set<String> completedStepIds;
  final Set<String> skippedStepIds;
}

enum MobileFlowAccessDecision {
  allowed,
  unknownFlow,
  unknownStep,
  invalidProgress,
  prerequisitesIncomplete,
}

/// Result of a fail-closed step-order decision.
@immutable
class MobileFlowAccessResult {
  const MobileFlowAccessResult({
    required this.decision,
    this.firstIncompleteStep,
  });

  final MobileFlowAccessDecision decision;

  /// Safe recovery target when known; contains registry metadata only.
  final MobileFlowStepDefinition? firstIncompleteStep;

  bool get allowed => decision == MobileFlowAccessDecision.allowed;
}

/// Sequential-order guard for guided-flow navigation.
///
/// Completed and explicitly skipped steps are reviewable. The first unfinished
/// step is reachable. Later steps fail closed. An optional step is skippable
/// only after the owning flow explicitly records it in [skippedStepIds];
/// optional metadata never authorizes a direct URL jump.
class MobileFlowStepGuard {
  const MobileFlowStepGuard(this.registry);

  final MobileFlowRegistry registry;

  MobileFlowAccessResult canOpen({
    required String flowId,
    required String stepId,
    required MobileFlowProgress progress,
  }) {
    final flow = registry.flow(flowId);
    if (flow == null) {
      return const MobileFlowAccessResult(
        decision: MobileFlowAccessDecision.unknownFlow,
      );
    }
    final requested = flow.step(stepId);
    if (requested == null) {
      return const MobileFlowAccessResult(
        decision: MobileFlowAccessDecision.unknownStep,
      );
    }

    final known = flow.steps.map((step) => step.id).toSet();
    final completed = Set<String>.of(progress.completedStepIds);
    final skipped = Set<String>.of(progress.skippedStepIds);
    if (!known.containsAll(completed) ||
        !known.containsAll(skipped) ||
        completed.intersection(skipped).isNotEmpty ||
        flow.steps.any(
          (step) => skipped.contains(step.id) && !step.optional,
        )) {
      return const MobileFlowAccessResult(
        decision: MobileFlowAccessDecision.invalidProgress,
      );
    }

    MobileFlowStepDefinition? firstIncomplete;
    for (final step in flow.steps) {
      final terminal = completed.contains(step.id) || skipped.contains(step.id);
      if (!terminal && firstIncomplete == null) {
        firstIncomplete = step;
      } else if (terminal && firstIncomplete != null) {
        // A later terminal step with an unfinished prerequisite indicates
        // corrupt or forged progress. Fail closed instead of treating a
        // caller-provided set as authority to jump the sequence.
        return MobileFlowAccessResult(
          decision: MobileFlowAccessDecision.invalidProgress,
          firstIncompleteStep: firstIncomplete,
        );
      }
    }

    final requestedIndex = flow.steps.indexOf(requested);
    final frontierIndex = firstIncomplete == null
        ? flow.steps.length
        : flow.steps.indexOf(firstIncomplete);
    if (requestedIndex <= frontierIndex) {
      return MobileFlowAccessResult(
        decision: MobileFlowAccessDecision.allowed,
        firstIncompleteStep: firstIncomplete,
      );
    }
    return MobileFlowAccessResult(
      decision: MobileFlowAccessDecision.prerequisitesIncomplete,
      firstIncompleteStep: firstIncomplete,
    );
  }
}

/// Immutable registry for implemented mobile guided flows.
class MobileFlowRegistry {
  MobileFlowRegistry._(this.flows) {
    final flowIds = <String>{};
    final routeNames = <String>{};
    for (final flow in flows) {
      if (!flowIds.add(flow.id)) {
        throw ArgumentError('Duplicate mobile flow id: ${flow.id}');
      }
      if (flow.steps.isEmpty) {
        throw ArgumentError('Mobile flow must contain a step: ${flow.id}');
      }
      final stepIds = <String>{};
      final legacyIndexes = <int>{};
      for (final step in flow.steps) {
        if (!stepIds.add(step.id)) {
          throw ArgumentError('Duplicate step id in ${flow.id}: ${step.id}');
        }
        if (!legacyIndexes.add(step.legacyIndex)) {
          throw ArgumentError(
            'Duplicate legacy index in ${flow.id}: ${step.legacyIndex}',
          );
        }
        if (!routeNames.add(step.routeName)) {
          throw ArgumentError('Duplicate mobile flow route: ${step.routeName}');
        }
      }
    }
  }

  /// Registry used by the current UnifiedRoot.
  ///
  /// Only the three views actually implemented by `OnboardingFlow` are
  /// present. Planned medicine, LifeMap, Visit, Family, and other routes are
  /// intentionally absent until their focused mobile screens exist.
  factory MobileFlowRegistry.current() =>
      MobileFlowRegistry._(_implementedFlows);

  final List<MobileFlowDefinition> flows;

  MobileFlowDefinition? flow(String flowId) {
    for (final candidate in flows) {
      if (candidate.id == flowId) return candidate;
    }
    return null;
  }

  MobileFlowStepDefinition? stepForRoute(String routeName) {
    for (final flow in flows) {
      for (final step in flow.steps) {
        if (step.routeName == routeName) return step;
      }
    }
    return null;
  }
}

const List<MobileFlowDefinition> _implementedFlows = <MobileFlowDefinition>[
  MobileFlowDefinition(
    id: MobileFlowIds.unifiedOnboarding,
    title: MobileFlowLabel(vi: 'Thiết lập CLARA', en: 'Set up CLARA'),
    steps: <MobileFlowStepDefinition>[
      MobileFlowStepDefinition(
        id: UnifiedOnboardingStepIds.welcome,
        routeName: '/mobile-flow/onboarding/welcome',
        legacyIndex: 0,
        title: MobileFlowLabel(vi: 'Chào mừng', en: 'Welcome'),
        nextOutcome: MobileFlowLabel(
          vi: 'Tiếp tục đến thông tin cơ bản',
          en: 'Continue to basic information',
        ),
        authority: MobileFlowStepAuthority.draft,
      ),
      MobileFlowStepDefinition(
        id: UnifiedOnboardingStepIds.basics,
        routeName: '/mobile-flow/onboarding/basics',
        legacyIndex: 1,
        title: MobileFlowLabel(
          vi: 'Thông tin cơ bản',
          en: 'Basic information',
        ),
        nextOutcome: MobileFlowLabel(
          vi: 'Tiếp tục đến lựa chọn cá nhân hóa',
          en: 'Continue to personalization choices',
        ),
        authority: MobileFlowStepAuthority.draft,
        optional: true,
      ),
      MobileFlowStepDefinition(
        id: UnifiedOnboardingStepIds.personalization,
        routeName: '/mobile-flow/onboarding/personalization',
        legacyIndex: 2,
        title: MobileFlowLabel(vi: 'Cá nhân hóa', en: 'Personalization'),
        nextOutcome: MobileFlowLabel(
          vi: 'Hoàn tất thiết lập',
          en: 'Finish setup',
        ),
        authority: MobileFlowStepAuthority.commit,
        optional: true,
      ),
    ],
  ),
];

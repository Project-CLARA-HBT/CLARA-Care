import 'dart:math';

import 'package:clara_mobile/experience/guided_flow/mobile_flow_analytics_schema.dart';
import 'package:clara_mobile/experience/guided_flow/mobile_flow_registry.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late MobileFlowRegistry registry;
  late MobileFlowStepGuard guard;

  setUp(() {
    registry = MobileFlowRegistry.current();
    guard = MobileFlowStepGuard(registry);
  });

  group('current mobile flow registry', () {
    test('registers only the three onboarding views implemented today', () {
      expect(registry.flows, hasLength(1));
      final flow = registry.flow(MobileFlowIds.unifiedOnboarding)!;
      expect(
        flow.steps.map((step) => step.id),
        <String>[
          UnifiedOnboardingStepIds.welcome,
          UnifiedOnboardingStepIds.basics,
          UnifiedOnboardingStepIds.personalization,
        ],
      );
      expect(flow.steps.map((step) => step.legacyIndex), <int>[0, 1, 2]);

      for (final planned in <String>[
        'medicine_add',
        'lifemap_capture',
        'visit_create',
        'family_invite',
      ]) {
        expect(registry.flow(planned), isNull);
      }
    });

    test('resolves Vietnamese first, English explicitly, and unknown to VI',
        () {
      final flow = registry.flow(MobileFlowIds.unifiedOnboarding)!;
      expect(flow.title.resolve('vi'), 'Thiết lập CLARA');
      expect(flow.title.resolve('en'), 'Set up CLARA');
      expect(flow.title.resolve('EN-us'), 'Set up CLARA');
      expect(flow.title.resolve('fr'), 'Thiết lập CLARA');
      expect(flow.title.resolveLocale(const Locale('en')), 'Set up CLARA');
    });

    test('maps current local indices and internal RouteSettings without data',
        () {
      final flow = registry.flow(MobileFlowIds.unifiedOnboarding)!;
      for (var index = 0; index < flow.steps.length; index++) {
        final step = flow.stepAtLegacyIndex(index)!;
        expect(step, same(flow.steps[index]));
        expect(registry.stepForRoute(step.routeName), same(step));
        expect(step.routeSettings.name, step.routeName);
        expect(step.routeSettings.arguments, isNull);
      }
      expect(flow.stepAtLegacyIndex(99), isNull);
      expect(registry.stepForRoute('/planned/not-implemented'), isNull);
    });
  });

  group('step-order guard', () {
    MobileFlowAccessDecision decision(
      String stepId, {
      Set<String> completed = const <String>{},
      Set<String> skipped = const <String>{},
    }) =>
        guard
            .canOpen(
              flowId: MobileFlowIds.unifiedOnboarding,
              stepId: stepId,
              progress: MobileFlowProgress(
                completedStepIds: completed,
                skippedStepIds: skipped,
              ),
            )
            .decision;

    test('allows review/back and the first unfinished step, blocks later steps',
        () {
      expect(
        decision(UnifiedOnboardingStepIds.welcome),
        MobileFlowAccessDecision.allowed,
      );
      expect(
        decision(UnifiedOnboardingStepIds.basics),
        MobileFlowAccessDecision.prerequisitesIncomplete,
      );
      expect(
        decision(
          UnifiedOnboardingStepIds.basics,
          completed: <String>{UnifiedOnboardingStepIds.welcome},
        ),
        MobileFlowAccessDecision.allowed,
      );
      expect(
        decision(
          UnifiedOnboardingStepIds.personalization,
          completed: <String>{UnifiedOnboardingStepIds.welcome},
        ),
        MobileFlowAccessDecision.prerequisitesIncomplete,
      );
      expect(
        decision(
          UnifiedOnboardingStepIds.personalization,
          completed: <String>{UnifiedOnboardingStepIds.welcome},
          skipped: <String>{UnifiedOnboardingStepIds.basics},
        ),
        MobileFlowAccessDecision.allowed,
      );
      expect(
        decision(
          UnifiedOnboardingStepIds.welcome,
          completed: <String>{
            UnifiedOnboardingStepIds.welcome,
            UnifiedOnboardingStepIds.basics,
          },
        ),
        MobileFlowAccessDecision.allowed,
      );
    });

    test('fails closed for unknown definitions and invalid progress', () {
      expect(
        guard
            .canOpen(
              flowId: 'unknown',
              stepId: UnifiedOnboardingStepIds.welcome,
              progress: const MobileFlowProgress(),
            )
            .decision,
        MobileFlowAccessDecision.unknownFlow,
      );
      expect(
        decision('unknown'),
        MobileFlowAccessDecision.unknownStep,
      );
      expect(
        decision(
          UnifiedOnboardingStepIds.welcome,
          completed: <String>{'not_registered'},
        ),
        MobileFlowAccessDecision.invalidProgress,
      );
      expect(
        decision(
          UnifiedOnboardingStepIds.welcome,
          completed: <String>{UnifiedOnboardingStepIds.welcome},
          skipped: <String>{UnifiedOnboardingStepIds.welcome},
        ),
        MobileFlowAccessDecision.invalidProgress,
      );
      expect(
        decision(
          UnifiedOnboardingStepIds.welcome,
          completed: <String>{UnifiedOnboardingStepIds.basics},
        ),
        MobileFlowAccessDecision.invalidProgress,
      );
      expect(
        decision(
          UnifiedOnboardingStepIds.welcome,
          skipped: <String>{UnifiedOnboardingStepIds.welcome},
        ),
        MobileFlowAccessDecision.invalidProgress,
      );
    });

    test('property: reachable steps equal the contiguous terminal frontier',
        () {
      final random = Random(20260729);
      final steps = registry.flow(MobileFlowIds.unifiedOnboarding)!.steps;

      for (var run = 0; run < 500; run++) {
        final completed = <String>{};
        final skipped = <String>{};
        final frontier = random.nextInt(steps.length + 1);
        for (var index = 0; index < frontier; index++) {
          final step = steps[index];
          if (step.optional && random.nextBool()) {
            skipped.add(step.id);
          } else {
            completed.add(step.id);
          }
        }

        for (var index = 0; index < steps.length; index++) {
          final result = guard.canOpen(
            flowId: MobileFlowIds.unifiedOnboarding,
            stepId: steps[index].id,
            progress: MobileFlowProgress(
              completedStepIds: completed,
              skippedStepIds: skipped,
            ),
          );
          expect(
            result.allowed,
            index <= frontier,
            reason: 'run=$run index=$index frontier=$frontier',
          );
        }
      }
    });
  });

  group('content-free analytics schema', () {
    test('has a fixed allowlisted shape and does not accept arbitrary payload',
        () {
      final record = MobileFlowAnalyticsRecord.forStep(
        registry: registry,
        flowId: MobileFlowIds.unifiedOnboarding,
        stepId: UnifiedOnboardingStepIds.basics,
        outcome: MobileFlowAnalyticsOutcome.completed,
      );

      expect(record.eventName, kMobileGuidedFlowStepEvent);
      expect(record.dimensions.keys, <String>[
        'schema_version',
        'flow_id',
        'step_id',
        'outcome',
      ]);
      expect(record.dimensions, <String, Object>{
        'schema_version': 1,
        'flow_id': MobileFlowIds.unifiedOnboarding,
        'step_id': UnifiedOnboardingStepIds.basics,
        'outcome': 'completed',
      });
      expect(
        () => record.dimensions['free_text'] = 'not allowed',
        throwsUnsupportedError,
      );
    });

    test('rejects unregistered flow and step dimensions', () {
      expect(
        () => MobileFlowAnalyticsRecord.forStep(
          registry: registry,
          flowId: 'planned_flow',
          stepId: 'planned_step',
          outcome: MobileFlowAnalyticsOutcome.viewed,
        ),
        throwsArgumentError,
      );
      expect(
        () => MobileFlowAnalyticsRecord.forStep(
          registry: registry,
          flowId: MobileFlowIds.unifiedOnboarding,
          stepId: 'free-text-step',
          outcome: MobileFlowAnalyticsOutcome.failed,
        ),
        throwsArgumentError,
      );
    });

    test('property: every event contains only finite registry vocabulary', () {
      final flow = registry.flow(MobileFlowIds.unifiedOnboarding)!;
      for (final step in flow.steps) {
        for (final outcome in MobileFlowAnalyticsOutcome.values) {
          final dimensions = MobileFlowAnalyticsRecord.forStep(
            registry: registry,
            flowId: flow.id,
            stepId: step.id,
            outcome: outcome,
          ).dimensions;
          expect(dimensions['flow_id'], flow.id);
          expect(dimensions['step_id'], step.id);
          expect(dimensions['outcome'], outcome.wireValue);
          expect(
            dimensions.keys.toSet(),
            <String>{'schema_version', 'flow_id', 'step_id', 'outcome'},
          );
        }
      }
    });
  });
}

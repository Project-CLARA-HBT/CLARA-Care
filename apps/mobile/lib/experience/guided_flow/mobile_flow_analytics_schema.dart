// Content-free analytics vocabulary for mobile guided flows.
//
// This file defines data only. It imports no analytics client, emits nothing,
// and accepts no arbitrary payload, free text, health content, user identity,
// exception, or upstream error.

import 'package:flutter/foundation.dart';

import 'mobile_flow_registry.dart';

/// Stable event name reserved for a future consent-gated integration.
const String kMobileGuidedFlowStepEvent = 'mobile_guided_flow_step';

const int kMobileGuidedFlowAnalyticsSchemaVersion = 1;

enum MobileFlowAnalyticsOutcome {
  viewed('viewed'),
  completed('completed'),
  skipped('skipped'),
  blocked('blocked'),
  abandoned('abandoned'),
  failed('failed');

  const MobileFlowAnalyticsOutcome(this.wireValue);

  final String wireValue;
}

/// Validated, content-free dimensions for one guided-flow lifecycle event.
///
/// Construction succeeds only for a flow/step pair present in the supplied
/// registry. [dimensions] is a fixed projection; callers cannot attach an
/// arbitrary properties map.
@immutable
class MobileFlowAnalyticsRecord {
  const MobileFlowAnalyticsRecord._({
    required this.flowId,
    required this.stepId,
    required this.outcome,
  });

  factory MobileFlowAnalyticsRecord.forStep({
    required MobileFlowRegistry registry,
    required String flowId,
    required String stepId,
    required MobileFlowAnalyticsOutcome outcome,
  }) {
    final flow = registry.flow(flowId);
    if (flow == null || flow.step(stepId) == null) {
      throw ArgumentError('Analytics dimensions must reference a known step');
    }
    return MobileFlowAnalyticsRecord._(
      flowId: flowId,
      stepId: stepId,
      outcome: outcome,
    );
  }

  final String flowId;
  final String stepId;
  final MobileFlowAnalyticsOutcome outcome;

  String get eventName => kMobileGuidedFlowStepEvent;

  Map<String, Object> get dimensions => Map<String, Object>.unmodifiable(
        <String, Object>{
          'schema_version': kMobileGuidedFlowAnalyticsSchemaVersion,
          'flow_id': flowId,
          'step_id': stepId,
          'outcome': outcome.wireValue,
        },
      );
}

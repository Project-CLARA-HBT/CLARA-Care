// Unit tests for the enhanced DdiUserView: per-alert severity + medications,
// severity-first sorting, and cache round-trip fidelity.

import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/ddi_user_view.dart';

void main() {
  group('DdiUserView per-alert severity + medications', () {
    test('fromPayload extracts severity + medications per alert', () {
      final view = DdiUserView.fromPayload({
        'risk': {'level': 'high'},
        'ddi_alerts': [
          {
            'message': 'Tăng nguy cơ chảy máu',
            'severity': 'critical',
            'medications': ['warfarin', 'ibuprofen'],
          },
          {
            'message': 'Theo dõi đường huyết',
            'severity': 'low',
            'medications': ['metformin', 'aspirin'],
          },
        ],
      });

      expect(view.alerts.length, 2);
      // Sorted most-severe-first.
      expect(view.alerts.first.severity, 'critical');
      expect(view.alerts.first.medications, ['warfarin', 'ibuprofen']);
      expect(view.alerts.last.severity, 'low');
    });

    test('severityRank orders bands correctly', () {
      const critical = DdiAlert(message: 'x', severity: 'critical');
      const high = DdiAlert(message: 'x', severity: 'high');
      const medium = DdiAlert(message: 'x', severity: 'medium');
      const low = DdiAlert(message: 'x', severity: 'low');
      const unknown = DdiAlert(message: 'x', severity: 'zzz');
      expect(critical.severityRank, greaterThan(high.severityRank));
      expect(high.severityRank, greaterThan(medium.severityRank));
      expect(medium.severityRank, greaterThan(low.severityRank));
      expect(low.severityRank, greaterThan(unknown.severityRank));
    });

    test('severityLabel is Vietnamese-first', () {
      expect(const DdiAlert(message: 'x', severity: 'critical').severityLabel,
          'Nghiêm trọng');
      expect(
          const DdiAlert(message: 'x', severity: 'high').severityLabel, 'Cao');
      expect(const DdiAlert(message: 'x', severity: 'medium').severityLabel,
          'Trung bình');
      expect(
          const DdiAlert(message: 'x', severity: 'low').severityLabel, 'Thấp');
    });

    test('cache round-trip preserves severity + medications', () {
      final original = DdiUserView.fromPayload({
        'risk': {'level': 'high'},
        'ddi_alerts': [
          {
            'message': 'Tăng nguy cơ chảy máu',
            'severity': 'critical',
            'medications': ['warfarin', 'ibuprofen'],
          },
        ],
        'attribution': {
          'sources': [
            {'name': 'DrugBank'},
          ],
        },
      });

      final restored = DdiUserView.fromCacheJson(original.toCacheJson());
      expect(restored.alerts.length, 1);
      expect(restored.alerts.first.severity, 'critical');
      expect(restored.alerts.first.medications, ['warfarin', 'ibuprofen']);
      expect(restored.sources, contains('DrugBank'));
    });
  });

  group('CareGuard medication clarification terminal state', () {
    test('parses only an explicit, source-backed clarification selection', () {
      final clarifications = medicationClarificationsFromPayload({
        'status': 'requires_medication_clarification',
        'clarifications': [
          {
            'cabinet_item_id': 7,
            'input_alias': 'panadol xanh',
            'candidates': [
              {
                'drugbank_id': 'DB00316',
                'normalized_name': 'Acetaminophen',
                'active_ingredients': ['Acetaminophen'],
                'source_version': 'drugbank-2026-07',
              },
              // Missing source version: never turn this into a selectable
              // local/LLM identity.
              {
                'drugbank_id': 'DB-bad',
                'normalized_name': 'Unknown',
              },
            ],
          },
        ],
      });

      expect(clarifications, hasLength(1));
      expect(clarifications!.single.cabinetItemId, 7);
      expect(clarifications.single.candidates, hasLength(1));
      expect(clarifications.single.candidates.single.drugbankId, 'DB00316');
      expect(
        clarifications.single.candidates.single.sourceVersion,
        'drugbank-2026-07',
      );
    });

    test('does not reinterpret non-terminal data as a clarification', () {
      expect(
        medicationClarificationsFromPayload({'risk_tier': 'low'}),
        isNull,
      );
      expect(
        medicationClarificationsFromPayload({
          'status': 'requires_medication_clarification',
          'clarifications': 'not-a-list',
        }),
        isEmpty,
      );
    });
  });
}

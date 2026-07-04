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
}

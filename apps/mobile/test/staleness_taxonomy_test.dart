import 'package:clara_mobile/core/staleness_taxonomy.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('StalenessFeedback Taxonomy Parsing', () {
    test('maps 409 stale version to concurrentEdit with autoRefresh enabled', () {
      final fb = StalenessFeedback.fromServerCode('glhs_stale_dependency_version', 409);
      expect(fb.reason, equals(StalenessReason.concurrentEdit));
      expect(fb.canAutoRefresh, isTrue);
      expect(fb.messageVi, contains('bác sĩ khác'));
    });

    test('maps 403 to consentWithdrawn with autoRefresh disabled', () {
      final fb = StalenessFeedback.fromServerCode('consent_required', 403);
      expect(fb.reason, equals(StalenessReason.consentWithdrawn));
      expect(fb.canAutoRefresh, isFalse);
    });

    test('maps lease error to consultationLeaseExpired', () {
      final fb = StalenessFeedback.fromServerCode('lease_expired', 409);
      expect(fb.reason, equals(StalenessReason.consultationLeaseExpired));
      expect(fb.canAutoRefresh, isFalse);
    });
  });
}

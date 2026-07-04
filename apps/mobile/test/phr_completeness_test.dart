// Unit tests for the pure PHR profile-completeness logic (Experience_V3).

import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/experience/redesign/phr_completeness.dart';

void main() {
  group('PhrCompleteness.compute', () {
    test('empty record ⇒ 0% and all dimensions missing', () {
      final c = PhrCompleteness.compute(
        fullName: '',
        dateOfBirth: '',
        gender: '',
        bloodType: '',
        heightCm: '',
        weightKg: '',
        phone: '',
        emergencyContactName: '',
        emergencyContactPhone: '',
        allergyCount: 0,
        conditionCount: 0,
        medicationCount: 0,
      );
      expect(c.percent, 0);
      expect(c.filledCount, 0);
      expect(c.missing.length, c.totalCount);
    });

    test('fully filled record ⇒ 100% and nothing missing', () {
      final c = PhrCompleteness.compute(
        fullName: 'Nguyen Van A',
        dateOfBirth: '1990-01-01',
        gender: 'Nam',
        bloodType: 'O+',
        heightCm: '170',
        weightKg: '65',
        phone: '0900000000',
        emergencyContactName: 'Nguyen Van B',
        emergencyContactPhone: '0900000001',
        allergyCount: 1,
        conditionCount: 1,
        medicationCount: 1,
      );
      expect(c.percent, 100);
      expect(c.missing, isEmpty);
    });

    test('whitespace-only values do not count as filled', () {
      final c = PhrCompleteness.compute(
        fullName: '   ',
        dateOfBirth: '',
        gender: '',
        bloodType: '',
        heightCm: '',
        weightKg: '',
        phone: '',
        emergencyContactName: '',
        emergencyContactPhone: '',
        allergyCount: 0,
        conditionCount: 0,
        medicationCount: 0,
      );
      expect(c.filledCount, 0);
    });

    test('partial fill ⇒ fraction between 0 and 1, missing listed', () {
      final c = PhrCompleteness.compute(
        fullName: 'A',
        dateOfBirth: '',
        gender: '',
        bloodType: '',
        heightCm: '',
        weightKg: '',
        phone: '',
        emergencyContactName: '',
        emergencyContactPhone: '',
        allergyCount: 0,
        conditionCount: 0,
        medicationCount: 0,
      );
      expect(c.fraction, greaterThan(0.0));
      expect(c.fraction, lessThan(1.0));
      expect(c.missing, isNotEmpty);
    });
  });
}

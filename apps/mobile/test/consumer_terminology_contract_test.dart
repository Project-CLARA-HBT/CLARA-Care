import 'package:clara_mobile/core/consumer_terminology.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('consumer terminology contract v1', () {
    test('is Vietnamese-first for missing and unsupported locales', () {
      expect(ConsumerTerminology.forLocale(null).locale, 'vi');
      expect(ConsumerTerminology.forLocale('fr').locale, 'vi');
      expect(
        ConsumerTerminology.forLocale('fr')[ConsumerTerm.todayTitle],
        'Hôm nay',
      );
    });

    test('keeps every versioned core term available in both locales', () {
      final vi = ConsumerTerminology.forLocale('vi');
      final en = ConsumerTerminology.forLocale('en-US');

      for (final term in ConsumerTerm.values) {
        expect(vi[term], isNotEmpty, reason: 'missing Vietnamese $term');
        expect(en[term], isNotEmpty, reason: 'missing English $term');
      }
    });

    test('retains the web-aligned LifeMap agency wording', () {
      final vi = ConsumerTerminology.forLocale('vi');
      expect(kConsumerTerminologyVersion, '2026-07-30.v1');
      expect(vi[ConsumerTerm.navigationLifeMap], 'Hành trình sức khỏe');
      expect(
        ConsumerTerminology.forLocale('en')[ConsumerTerm.navigationProfile],
        'Profile',
      );
      expect(vi[ConsumerTerm.todayOpenLifeMap], 'Mở hành trình sức khỏe');
      expect(
        vi[ConsumerTerm.todayEmptyDescription],
        contains('CLARA không tự thêm việc thay bạn'),
      );
    });

    test('formats only declared static placeholders', () {
      final terms = ConsumerTerminology.forLocale('en');
      expect(
        terms.format(ConsumerTerm.todayDueDate, {'date': 'Jul 30, 2026'}),
        'Due: Jul 30, 2026',
      );
    });
  });
}

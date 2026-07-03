// Unit tests for the pure cabinet insights layer (Experience_V3).
//
// These lock the deterministic aggregation logic that drives the cabinet
// "health" summary — expiry bucketing, distinct-ingredient counting, needs-
// review and low-stock counts — without mounting any widget. The logic must
// never fabricate data: an item with no expiry is "unknown", not "valid".

import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/experience/redesign/cabinet_insights.dart';

CabinetInsightItem _item({
  String key = '',
  String expiresOn = '',
  bool needsReview = false,
  num quantity = 0,
}) =>
    (
      distinctKey: key,
      expiresOn: expiresOn,
      needsReview: needsReview,
      quantity: quantity,
    );

void main() {
  // A fixed reference date so expiry math is deterministic.
  final now = DateTime(2026, 6, 1);

  group('classifyExpiry', () {
    test('empty/unparseable ⇒ unknown (never fabricated as valid)', () {
      expect(classifyExpiry('', now: now), CabinetExpiryBucket.unknown);
      expect(
          classifyExpiry('not-a-date', now: now), CabinetExpiryBucket.unknown);
    });

    test('past date ⇒ expired', () {
      expect(
          classifyExpiry('2026-05-01', now: now), CabinetExpiryBucket.expired);
    });

    test('within 30 days ⇒ expiringSoon', () {
      expect(classifyExpiry('2026-06-20', now: now),
          CabinetExpiryBucket.expiringSoon);
    });

    test('far future ⇒ valid', () {
      expect(classifyExpiry('2027-01-01', now: now), CabinetExpiryBucket.valid);
    });
  });

  group('CabinetInsights.fromItems', () {
    test('empty cabinet ⇒ all zero, no attention items', () {
      final insights = CabinetInsights.fromItems(const [], now: now);
      expect(insights.total, 0);
      expect(insights.distinctIngredients, 0);
      expect(insights.hasAttentionItems, isFalse);
      expect(insights.canCheckInteractions, isFalse);
    });

    test('aggregates buckets, distinct ingredients, review and low stock', () {
      final insights = CabinetInsights.fromItems(
        [
          _item(key: 'paracetamol', expiresOn: '2026-05-01'), // expired
          _item(key: 'ibuprofen', expiresOn: '2026-06-20'), // expiring soon
          _item(key: 'amoxicillin', expiresOn: '2027-01-01', quantity: 3),
          _item(key: 'paracetamol', expiresOn: ''), // dup ingredient, unknown
          _item(key: 'vitamin c', needsReview: true, quantity: 20),
        ],
        now: now,
      );

      expect(insights.total, 5);
      // paracetamol counted once despite two entries.
      expect(insights.distinctIngredients, 4);
      expect(insights.expired, 1);
      expect(insights.expiringSoon, 1);
      expect(insights.valid, 1);
      expect(insights.unknownExpiry, 2);
      expect(insights.needsReview, 1);
      // amoxicillin qty 3 is at/below the low-stock threshold; vitamin c (20) is not.
      expect(insights.lowStock, 1);
      expect(insights.hasAttentionItems, isTrue);
      expect(insights.canCheckInteractions, isTrue);
    });
  });
}

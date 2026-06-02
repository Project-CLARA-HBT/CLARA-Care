// Feature: product-polish-analytics, Property 16/17/18 (mobile facade)
//
// Dart tests for the mobile analytics facade (`Analytics` in
// `lib/core/analytics.dart`).
//
// Task 8.8 / 7.7 — mobile analytics:
//   * No transmission without credentials (Requirements 9.2, 9.5).
//   * No transmission without consent (Requirements 9.2, 9.3).
//   * PII keys are stripped from every event payload (Requirement 9.4).
//
// These map to design Properties 16 (consent suppression), 17 (safe no-op
// without credentials), 18 (pseudonymous identity) and 13 (PII-free payloads),
// scoped to the mobile facade contract.
//
// A recording [AnalyticsTransport] double captures every init/identify/capture
// call so the tests can assert that the transport receives ZERO calls when the
// facade is unconfigured or un-consented, and that captured payloads never
// contain PII. Each privacy invariant is exercised across many generated
// inputs (>=200 iterations) to approximate property-based testing in Dart,
// complemented by example-based unit tests for important edge cases.

import 'dart:math';

import 'package:clara_mobile/core/analytics.dart';
import 'package:flutter_test/flutter_test.dart';

/// Records every transport interaction so tests can assert on transmission.
class RecordingAnalyticsTransport implements AnalyticsTransport {
  int initCalls = 0;
  final List<String> identified = <String>[];
  final List<AnalyticsEvent> captured = <AnalyticsEvent>[];

  /// Total outbound interactions (identify + capture) — i.e. transmissions.
  int get transmissions => identified.length + captured.length;

  @override
  void init(AnalyticsConfig config) {
    initCalls++;
  }

  @override
  void identify(String distinctId) {
    identified.add(distinctId);
  }

  @override
  void capture(AnalyticsEvent event) {
    captured.add(event);
  }
}

const AnalyticsConfig _configured =
    AnalyticsConfig(provider: 'posthog', apiKey: 'phc_test_key');

/// All PII / free-text keys that must never reach the transport.
const List<String> _piiKeys = <String>[
  'name',
  'fullName',
  'first_name',
  'last_name',
  'email',
  'emailAddress',
  'patient_email',
  'phone',
  'phoneNumber',
  'address',
  'dob',
  'ssn',
  'query',
  'question',
  'prompt',
  'message',
  'userInput',
  'search_query',
  'drug',
  'drugs',
  'drug_names',
  'medication',
  'medicines',
  'symptom',
  'allergy',
  'diagnosis',
  'prescription',
  'password',
];

/// Keys that are safe, non-PII analytics metadata and should be preserved.
const List<String> _safeKeys = <String>[
  'screen',
  'count',
  'durationMs',
  'tier',
  'mode',
  'severity',
  'success',
  'index',
];

bool _containsPiiKey(Map<String, Object?> map) {
  for (final entry in map.entries) {
    final normalized =
        entry.key.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
    for (final pii in _piiKeys) {
      final p = pii.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
      if (normalized == p) {
        return true;
      }
    }
    final value = entry.value;
    if (value is Map<String, Object?> && _containsPiiKey(value)) {
      return true;
    }
    if (value is Map && _containsPiiKey(value.cast<String, Object?>())) {
      return true;
    }
  }
  return false;
}

String _randomString(Random rng, int length) {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  return String.fromCharCodes(
    List.generate(length, (_) => chars.codeUnitAt(rng.nextInt(chars.length))),
  );
}

void main() {
  group('Property 17: safe no-op without credentials (9.2, 9.5)', () {
    test('no transmission when unconfigured, even with consent (generated)',
        () {
      final rng = Random(13579);
      const iterations = 250;

      for (var i = 0; i < iterations; i++) {
        final transport = RecordingAnalyticsTransport();
        final analytics = Analytics(transport: transport);
        // Disabled config (no provider/key) but consent granted — should still
        // be a complete no-op because credentials are absent (9.5).
        analytics.init(AnalyticsConfig.disabled, consentGranted: true);

        expect(analytics.isConfigured, isFalse);

        analytics.identify(_randomString(rng, 1 + rng.nextInt(12)));
        analytics.capture(
          AnalyticsEvent('event_$i', {'screen': _randomString(rng, 5)}),
        );
        analytics.track('track_$i', props: {'count': rng.nextInt(100)});

        expect(transport.initCalls, 0,
            reason: 'transport must not init without credentials');
        expect(transport.transmissions, 0,
            reason: 'no transmission without credentials on iteration $i');
      }
    });

    test('example: provider present but empty key stays a no-op', () {
      final transport = RecordingAnalyticsTransport();
      final analytics = Analytics(transport: transport);
      analytics.init(
        const AnalyticsConfig(provider: 'posthog', apiKey: '   '),
        consentGranted: true,
      );

      analytics.capture(const AnalyticsEvent('mobile_login_viewed'));

      expect(analytics.isConfigured, isFalse);
      expect(transport.transmissions, 0);
    });

    test('analytics never throws into product flow when unconfigured', () {
      final analytics = createAnalyticsClient(
        config: AnalyticsConfig.disabled,
        consentGranted: true,
      );
      expect(
        () => analytics.capture(const AnalyticsEvent('mobile_dashboard_viewed')),
        returnsNormally,
      );
    });
  });

  group('Property 16: transmission suppressed without consent (9.2, 9.3)', () {
    test('no transmission while consent is not granted (generated)', () {
      final rng = Random(24680);
      const iterations = 250;

      for (var i = 0; i < iterations; i++) {
        final transport = RecordingAnalyticsTransport();
        final analytics = Analytics(transport: transport);
        // Configured with valid credentials but consent withheld.
        analytics.init(_configured, consentGranted: false);

        expect(analytics.isConfigured, isTrue);
        expect(analytics.consentGranted, isFalse);

        analytics.identify('user_${rng.nextInt(1 << 30)}');
        analytics.capture(
          AnalyticsEvent('event_$i', {'screen': _randomString(rng, 5)}),
        );
        analytics.captureScreenView(MobileAnalyticsEvents.researchViewed);

        expect(transport.initCalls, 0,
            reason: 'transport must not init before consent (lazy load)');
        expect(transport.transmissions, 0,
            reason: 'no transmission without consent on iteration $i');
      }
    });

    test('granting consent at runtime begins transmission', () {
      final transport = RecordingAnalyticsTransport();
      final analytics = Analytics(transport: transport);
      analytics.init(_configured, consentGranted: false);

      analytics.capture(const AnalyticsEvent('mobile_login_viewed'));
      expect(transport.transmissions, 0);

      analytics.setConsent(granted: true);
      analytics.capture(const AnalyticsEvent('mobile_login_succeeded'));

      expect(transport.initCalls, 1);
      expect(transport.captured.length, 1);
      expect(transport.captured.single.name, 'mobile_login_succeeded');
    });

    test('revoking consent stops further transmission', () {
      final transport = RecordingAnalyticsTransport();
      final analytics = Analytics(transport: transport);
      analytics.init(_configured, consentGranted: true);

      analytics.capture(const AnalyticsEvent('mobile_dashboard_viewed'));
      expect(transport.captured.length, 1);

      analytics.setConsent(granted: false);
      analytics.capture(const AnalyticsEvent('mobile_research_viewed'));

      expect(transport.captured.length, 1,
          reason: 'no new transmission after consent revoked');
    });
  });

  group('Property 13: PII keys stripped from payloads (9.4)', () {
    test('captured events never contain PII keys (generated)', () {
      final rng = Random(112233);
      const iterations = 250;

      for (var i = 0; i < iterations; i++) {
        final transport = RecordingAnalyticsTransport();
        final analytics = Analytics(transport: transport);
        analytics.init(_configured, consentGranted: true);

        // Build a payload mixing safe keys with PII keys, optionally nested.
        final props = <String, Object?>{};
        final piiCount = 1 + rng.nextInt(4);
        for (var j = 0; j < piiCount; j++) {
          props[_piiKeys[rng.nextInt(_piiKeys.length)]] =
              _randomString(rng, 1 + rng.nextInt(20));
        }
        final safeCount = rng.nextInt(4);
        final expectedSafe = <String>{};
        for (var j = 0; j < safeCount; j++) {
          final key = _safeKeys[rng.nextInt(_safeKeys.length)];
          props[key] = rng.nextInt(1000);
          expectedSafe.add(key);
        }
        // Sometimes nest a PII key one level deep.
        if (rng.nextBool()) {
          props['details'] = <String, Object?>{
            _piiKeys[rng.nextInt(_piiKeys.length)]: _randomString(rng, 8),
            'nestedCount': rng.nextInt(10),
          };
        }

        analytics.capture(AnalyticsEvent('event_$i', props));

        expect(transport.captured.length, 1);
        final sent = transport.captured.single;
        expect(_containsPiiKey(sent.props), isFalse,
            reason: 'PII leaked on iteration $i: ${sent.props}');
        // Safe keys survive stripping.
        for (final key in expectedSafe) {
          expect(sent.props.containsKey(key), isTrue,
              reason: 'safe key "$key" should be preserved');
        }
      }
    });

    test('stripPii drops names, emails, queries, and drug lists', () {
      final stripped = stripPii(
        const AnalyticsEvent('careguard_analyzed', {
          'name': 'Nguyen Van A',
          'email': 'a@example.com',
          'query': 'tuong tac thuoc',
          'drugs': ['aspirin', 'warfarin'],
          'severity': 'high',
          'count': 2,
        }),
      );

      expect(stripped.props.containsKey('name'), isFalse);
      expect(stripped.props.containsKey('email'), isFalse);
      expect(stripped.props.containsKey('query'), isFalse);
      expect(stripped.props.containsKey('drugs'), isFalse);
      // Non-PII analytics metadata is preserved.
      expect(stripped.props['severity'], 'high');
      expect(stripped.props['count'], 2);
    });

    test('stripPii removes nested and compound PII keys', () {
      final stripped = stripPii(
        const AnalyticsEvent('event', {
          'patient_email': 'p@example.com',
          'drug_names': ['x'],
          'meta': {
            'userInput': 'free text',
            'tier': 'tier1',
          },
          'tier': 'tier2',
        }),
      );

      expect(stripped.props.containsKey('patient_email'), isFalse);
      expect(stripped.props.containsKey('drug_names'), isFalse);
      final meta = stripped.props['meta'] as Map<String, Object?>;
      expect(meta.containsKey('userInput'), isFalse);
      expect(meta['tier'], 'tier1');
      expect(stripped.props['tier'], 'tier2');
    });
  });

  group('Property 18: pseudonymous identity (9.6)', () {
    test('identify transmits an opaque id, never the raw key (generated)', () {
      final rng = Random(778899);
      const iterations = 250;

      for (var i = 0; i < iterations; i++) {
        final transport = RecordingAnalyticsTransport();
        final analytics = Analytics(transport: transport);
        analytics.init(_configured, consentGranted: true);

        final rawKey =
            '${_randomString(rng, 4)}@example.com';
        analytics.identify(rawKey);

        expect(transport.identified.length, 1);
        final sentId = transport.identified.single;
        expect(sentId, isNot(equals(rawKey)),
            reason: 'distinct id must not equal the raw key');
        expect(sentId.contains(rawKey), isFalse,
            reason: 'distinct id must not contain the raw key');
        // Deterministic: same key hashes to the same id.
        expect(sentId, equals(pseudonymousId(rawKey)));
      }
    });

    test('pseudonymousId is deterministic and one-way', () {
      const key = 'nguyen@example.com';
      expect(pseudonymousId(key), equals(pseudonymousId(key)));
      expect(pseudonymousId(key), isNot(contains('nguyen')));
      expect(pseudonymousId(key), isNot(contains('@')));
      expect(pseudonymousId(''), isEmpty);
    });
  });
}

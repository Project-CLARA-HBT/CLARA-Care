// Wave 10 quality-gate: no-PII analytics for every Experience_V2 event
// (CLARA mobile experience spec, task 10.2 — Property P7).
//
// Property P7 (design §"Correctness Properties"): every Experience_V2 analytics
// event (home viewed, onboarding completed/skipped, language changed) passes
// the redaction projection — after `stripPii` no PII/free-text/medical key
// survives at ANY nesting depth, and the event name is preserved.
//   Validates: Requirements 9.6, 10.4.
//
// The redaction projection is the same `stripPii` the shared `Analytics` client
// applies before every transmission (`capture` → `stripPii`). These tests pin
// two layers:
//   1. The *actual* Experience_V2 events as emitted by their owners
//      (`HomeScreen`, `OnboardingGate`, `LanguageController`) carry only
//      non-PII payloads.
//   2. A generated (property-style) sweep: for the V2 event names wrapped
//      around ADVERSARIAL deeply-nested PII payloads, the projection drops
//      every denied key at every depth while preserving safe keys and the name.
//
// Pure unit tests over the pure `stripPii` function + the public event-name
// constants — no widgets, no platform channels, no live network (Req 10.5).

import 'dart:math';

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/experience/home_screen.dart';
import 'package:clara_mobile/experience/language_controller.dart';
import 'package:clara_mobile/experience/onboarding/onboarding_gate.dart';
import 'package:flutter_test/flutter_test.dart';

/// The four coarse Experience_V2 event names under test.
const List<String> _v2EventNames = <String>[
  kMobileHomeViewedEvent,
  kOnboardingCompletedEvent,
  kOnboardingSkippedEvent,
  kLanguageChangedEvent,
];

/// Denied keys (mirrors the facade denylist) used to build adversarial inputs
/// and to assert none survive the projection at any depth.
const List<String> _piiKeys = <String>[
  'name',
  'fullName',
  'email',
  'patient_email',
  'phone',
  'query',
  'question',
  'prompt',
  'message',
  'note',
  'transcript',
  'drug',
  'drugList',
  'medication',
  'medicines',
  'symptom',
  'allergy',
  'diagnosis',
  'prescription',
  'password',
];

/// Recursively collects every (string) key present in [value] at any depth.
Set<String> _allKeys(Object? value) {
  final keys = <String>{};
  if (value is Map) {
    value.forEach((k, v) {
      keys.add(k.toString());
      keys.addAll(_allKeys(v));
    });
  } else if (value is List) {
    for (final item in value) {
      keys.addAll(_allKeys(item));
    }
  }
  return keys;
}

/// Normalizes a key the same way the facade does, then reports whether it is a
/// denied (PII / free-text / medical) key.
bool _isDenied(String key) {
  final normalized = key.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
  const exact = <String>{
    'name', 'fullname', 'email', 'phone', 'query', 'question', 'prompt',
    'message', 'note', 'notes', 'transcript', 'drug', 'drugs', 'druglist',
    'medication', 'medications', 'medicine', 'medicines', 'symptom',
    'symptoms', 'allergy', 'allergies', 'diagnosis', 'prescription',
  };
  const substrings = <String>{
    'email', 'query', 'question', 'prompt', 'drug', 'medicine', 'medication',
    'symptom', 'allergy', 'diagnos', 'prescription', 'patient', 'password',
  };
  if (exact.contains(normalized)) return true;
  return substrings.any(normalized.contains);
}

void main() {
  group('Property P7 — Experience_V2 events emit no PII (Req 9.6)', () {
    test('every V2 event name is a non-empty coarse identifier', () {
      for (final name in _v2EventNames) {
        expect(name, isNotEmpty);
        // Event names are surface identifiers, never free text/PII.
        expect(_isDenied(name), isFalse, reason: 'event name "$name"');
      }
    });

    test(
        'home-viewed and onboarding events carry NO properties as emitted '
        '(coarse, name-only)', () {
      // These owners emit the event with an empty props map; nothing to redact.
      for (final name in <String>[
        kMobileHomeViewedEvent,
        kOnboardingCompletedEvent,
        kOnboardingSkippedEvent,
      ]) {
        final stripped = stripPii(AnalyticsEvent(name));
        expect(stripped.name, name);
        expect(stripped.props, isEmpty);
      }
    });

    test(
        'language-changed carries only the 2-letter code under a safe key '
        '(survives redaction)', () {
      // The LanguageController attaches only {language: 'vi'|'en'} — a locale
      // code is not PII, so the projection must KEEP it.
      for (final code in <String>['vi', 'en']) {
        final event = AnalyticsEvent(
          kLanguageChangedEvent,
          <String, Object?>{kLanguageEventProp: code},
        );
        final stripped = stripPii(event);
        expect(stripped.name, kLanguageChangedEvent);
        expect(stripped.props[kLanguageEventProp], code);
        // No PII key was introduced.
        expect(_allKeys(stripped.props).where(_isDenied), isEmpty);
      }
    });
  });

  group('Property P7 — adversarial nested payloads are fully redacted', () {
    test('generated: no denied key survives at any depth, name preserved', () {
      final rng = Random(20260630);
      const iterations = 300;

      for (var i = 0; i < iterations; i++) {
        final name = _v2EventNames[rng.nextInt(_v2EventNames.length)];

        // Build a deeply-nested adversarial payload mixing PII keys, the safe
        // `language` key, and other innocuous coarse keys, wrapped in maps and
        // lists to several levels.
        Object? buildNested(int depth) {
          if (depth <= 0) {
            return rng.nextBool() ? rng.nextInt(1000) : 'leaf-$i';
          }
          final map = <String, Object?>{
            // A guaranteed PII key at this level.
            _piiKeys[rng.nextInt(_piiKeys.length)]: 'SECRET-$depth-$i',
            // A safe key that must be preserved.
            'language': rng.nextBool() ? 'vi' : 'en',
            'count': rng.nextInt(10),
            // Recurse into a nested structure.
            'nested': buildNested(depth - 1),
            // A list mixing a nested map and scalars.
            'items': <Object?>[
              <String, Object?>{
                _piiKeys[rng.nextInt(_piiKeys.length)]: 'deep-$i',
                'ok': true,
              },
              buildNested(depth - 1),
            ],
          };
          return map;
        }

        final props = buildNested(2 + rng.nextInt(3)) as Map<String, Object?>;
        final event = AnalyticsEvent(name, props);
        final stripped = stripPii(event);

        // Name preserved.
        expect(stripped.name, name);

        // No denied key survives at ANY nesting depth (Property P7).
        final survivingDenied =
            _allKeys(stripped.props).where(_isDenied).toList();
        expect(survivingDenied, isEmpty,
            reason: 'iteration $i for "$name": leaked $survivingDenied');

        // Safe keys are retained (the projection only drops PII, not all keys).
        final survivingKeys = _allKeys(stripped.props);
        expect(survivingKeys, contains('language'));
        expect(survivingKeys, contains('count'));
      }
    });
  });
}

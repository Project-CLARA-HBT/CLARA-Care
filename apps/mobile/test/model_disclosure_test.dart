// Feature: clara-mobile-feature-parity — Task 9.1 (Requirement 7; Property P11).
//
// Unit + widget tests for `lib/core/model_disclosure.dart`:
//   * ModelDisclosure.fromModelUsed mirrors the backend `model_disclosure`
//     split (family/version on first hyphen, `unknown` when blank/hyphen-less)
//     and `isFallback` is true IFF the identity is `local-synth-*`.
//   * ModelDisclosure.fromResponse parses the `ai_disclosure` envelope block,
//     returns null when the block is absent/not-a-map (omit affordance, 7.5),
//     honours an explicit `is_fallback`, and derives it otherwise.
//   * ModelDisclosureChip.maybe is gated behind `model_disclosure_mobile_enabled`
//     (default OFF) and the chip renders status by text (10.5).

import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/core/model_disclosure.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

MobileFeatureFlagResolver _resolver({required bool modelDisclosureOn}) {
  return MobileFeatureFlagResolver(
    summary: <String, dynamic>{
      'feature_flags': <String, dynamic>{
        MobileFeatureFlags.modelDisclosureMobileEnabled: modelDisclosureOn,
      },
    },
  );
}

void main() {
  group('ModelDisclosure.fromModelUsed — backend parity (Property P11)', () {
    test('local-synth-* is a fallback (case-insensitive)', () {
      for (final id in ['local-synth-v1', 'local-synth-v2', 'LOCAL-SYNTH-X',
          'local-synth']) {
        expect(ModelDisclosure.fromModelUsed(id).isFallback, isTrue,
            reason: id);
      }
    });

    test('non local-synth identities are not fallbacks', () {
      for (final id in ['deepseek-v3.2', 'deepseek-v4-pro',
          'api-safe-fallback-v1', 'gpt-5.3', '', null]) {
        expect(ModelDisclosure.fromModelUsed(id).isFallback, isFalse,
            reason: '$id');
      }
    });

    test('family/version split on first hyphen', () {
      final d = ModelDisclosure.fromModelUsed('deepseek-v4-pro');
      expect(d.modelFamily, 'deepseek');
      expect(d.modelVersion, 'v4-pro');
    });

    test('blank identity yields unknown/unknown', () {
      final d = ModelDisclosure.fromModelUsed('');
      expect(d.modelFamily, kModelDisclosureUnknown);
      expect(d.modelVersion, kModelDisclosureUnknown);
      expect(d.isFallback, isFalse);
    });

    test('hyphen-less identity yields family + unknown version', () {
      final d = ModelDisclosure.fromModelUsed('mymodel');
      expect(d.modelFamily, 'mymodel');
      expect(d.modelVersion, kModelDisclosureUnknown);
    });
  });

  group('ModelDisclosure.fromResponse — omit affordance when absent (7.5)', () {
    test('null / non-map response returns null', () {
      expect(ModelDisclosure.fromResponse(null), isNull);
      expect(ModelDisclosure.fromResponse('nope'), isNull);
      expect(ModelDisclosure.fromResponse(42), isNull);
    });

    test('response without ai_disclosure block returns null', () {
      expect(
        ModelDisclosure.fromResponse(<String, dynamic>{'answer': 'hi'}),
        isNull,
      );
    });

    test('ai_disclosure that is not a map returns null', () {
      expect(
        ModelDisclosure.fromResponse(
            <String, dynamic>{'ai_disclosure': 'broken'}),
        isNull,
      );
    });

    test('parses explicit fields including is_fallback=true', () {
      final d = ModelDisclosure.fromResponse(<String, dynamic>{
        'ai_disclosure': <String, dynamic>{
          'model_family': 'local-synth',
          'model_version': 'v1',
          'is_fallback': true,
        },
      });
      expect(d, isNotNull);
      expect(d!.modelFamily, 'local-synth');
      expect(d.modelVersion, 'v1');
      expect(d.isFallback, isTrue);
    });

    test('parses non-fallback disclosure', () {
      final d = ModelDisclosure.fromResponse(<String, dynamic>{
        'ai_disclosure': <String, dynamic>{
          'model_family': 'deepseek',
          'model_version': 'v3.2',
          'is_fallback': false,
        },
      });
      expect(d!.isFallback, isFalse);
      expect(d.label, 'deepseek v3.2');
    });

    test('derives is_fallback from family-version when flag absent', () {
      final d = ModelDisclosure.fromResponse(<String, dynamic>{
        'ai_disclosure': <String, dynamic>{
          'model_family': 'local-synth',
          'model_version': 'v2',
        },
      });
      expect(d!.isFallback, isTrue);
    });

    test('missing family/version default to unknown', () {
      final d = ModelDisclosure.fromResponse(<String, dynamic>{
        'ai_disclosure': <String, dynamic>{'is_fallback': false},
      });
      expect(d!.modelFamily, kModelDisclosureUnknown);
      expect(d.modelVersion, kModelDisclosureUnknown);
      expect(d.label, kModelDisclosureUnknown);
    });
  });

  group('ModelDisclosure value semantics', () {
    test('equality is value-based', () {
      const a = ModelDisclosure(
          modelFamily: 'deepseek', modelVersion: 'v3.2', isFallback: false);
      const b = ModelDisclosure(
          modelFamily: 'deepseek', modelVersion: 'v3.2', isFallback: false);
      expect(a, equals(b));
      expect(a.hashCode, equals(b.hashCode));
    });
  });

  group('ModelDisclosureChip.maybe — gated behind flag (default OFF)', () {
    const disclosure = ModelDisclosure(
        modelFamily: 'deepseek', modelVersion: 'v3.2', isFallback: false);

    test('returns null when flag is off', () {
      final widget = ModelDisclosureChip.maybe(
        resolver: _resolver(modelDisclosureOn: false),
        disclosure: disclosure,
      );
      expect(widget, isNull);
    });

    test('returns null when disclosure is absent even if flag on', () {
      final widget = ModelDisclosureChip.maybe(
        resolver: _resolver(modelDisclosureOn: true),
        disclosure: null,
      );
      expect(widget, isNull);
    });

    test('returns a chip when flag on and disclosure present', () {
      final widget = ModelDisclosureChip.maybe(
        resolver: _resolver(modelDisclosureOn: true),
        disclosure: disclosure,
      );
      expect(widget, isA<ModelDisclosureChip>());
    });
  });

  group('ModelDisclosureChip — renders status by text (Req 10.5)', () {
    Future<void> pump(WidgetTester tester, ModelDisclosure d,
        {bool isEnglish = false}) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Center(
            child: ModelDisclosureChip(disclosure: d, isEnglish: isEnglish),
          ),
        ),
      ));
    }

    testWidgets('fallback shows degraded label (vi default)', (tester) async {
      await pump(
        tester,
        const ModelDisclosure(
            modelFamily: 'local-synth', modelVersion: 'v1', isFallback: true),
      );
      expect(find.textContaining('Suy giảm'), findsOneWidget);
    });

    testWidgets('fallback shows degraded label (en)', (tester) async {
      await pump(
        tester,
        const ModelDisclosure(
            modelFamily: 'local-synth', modelVersion: 'v1', isFallback: true),
        isEnglish: true,
      );
      expect(find.textContaining('Degraded'), findsOneWidget);
    });

    testWidgets('non-fallback shows model label', (tester) async {
      await pump(
        tester,
        const ModelDisclosure(
            modelFamily: 'deepseek', modelVersion: 'v3.2', isFallback: false),
      );
      expect(find.textContaining('deepseek v3.2'), findsOneWidget);
    });
  });
}

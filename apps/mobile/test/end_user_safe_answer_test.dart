// Tests for the End_User-safe answer projection + widget added in task 3.3 of
// the clara-mobile-feature-parity spec (Requirement 1.6; design Property P3/P4).
//
//   * `endUserSafeProjection` drops internal runtime fields (mode, retrieval,
//     source_errors, policy, fallback, …) at every nesting depth for non-admin
//     roles, while preserving user-facing content (reply, citations,
//     model_used).
//   * For an `admin` role the full envelope is preserved (deep-copied) so admins
//     may see complete runtime detail.
//   * The [EndUserSafeAnswer] widget never renders internal field values for a
//     non-admin role, and passes the answer text through `stripTelemetryLabels`.
//
// Pure-Dart projection tests + a widget test; no platform channels or live
// network (Requirement 14.6).

import 'package:clara_mobile/widgets/end_user_safe_answer.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// A representative chat answer envelope carrying both user-facing content and
/// internal runtime fields a non-admin must never see.
Map<String, dynamic> _envelope() => <String, dynamic>{
      'message': 'tôi nên uống thuốc này thế nào',
      'reply': 'Bạn nên uống theo chỉ định của bác sĩ.',
      'role': 'normal',
      'model_used': 'deepseek-v3.2',
      'citations': [
        {'title': 'Hướng dẫn sử dụng thuốc', 'url': 'https://example.org/a'},
        'Dược thư quốc gia',
      ],
      // --- internal runtime fields (must be dropped for non-admin) ---
      'mode': 'external_plus_local',
      'rag_mode': 'hybrid',
      'fallback': true,
      'fallback_reason': 'deepseek_unavailable',
      'retrieval': {'k': 8, 'route': 'dense'},
      'retrieved_ids': ['doc-1', 'doc-2'],
      'source_errors': {
        'openfda': ['openfda http_400']
      },
      'policy': {'verdict': 'warn'},
      'debug': {'pipeline': 'local-synth-v1'},
      'metadata': {
        'retrieval_errors': ['rxnav status=503'],
        'source_errors': {'rxnav': ['rxnav status=503']},
        'note': 'kept',
      },
    };

/// Internal field name/value fragments that must never appear in a non-admin
/// projection or render.
const _forbiddenKeys = <String>[
  'mode',
  'rag_mode',
  'fallback',
  'fallback_reason',
  'retrieval',
  'retrieved_ids',
  'source_errors',
  'policy',
  'debug',
  'retrieval_errors',
];

void main() {
  group('isInternalRuntimeKey', () {
    test('flags runtime/telemetry keys', () {
      for (final key in const <String>[
        'mode',
        'rag_mode',
        'research_mode',
        'fallback_mode',
        'fallback',
        'fallback_used',
        'retrieval',
        'retrieval_errors',
        'retrieved_ids',
        'source_errors',
        'sourceErrors',
        'policy',
        'policy_verdict',
        'debug',
        'telemetry',
        'reasoning_digest',
        'pipeline',
        'degraded_path',
        'router_confidence',
        'verification_matrix',
      ]) {
        expect(isInternalRuntimeKey(key), isTrue, reason: 'key "$key"');
      }
    });

    test('preserves genuine user-facing keys', () {
      for (final key in const <String>[
        'reply',
        'answer',
        'message',
        'role',
        'citations',
        'sources',
        'model_used',
        'model_family',
        'model_version',
        'emergency',
        'intent',
      ]) {
        expect(isInternalRuntimeKey(key), isFalse, reason: 'key "$key"');
      }
    });
  });

  group('endUserSafeProjection — non-admin', () {
    test('drops internal runtime fields at every nesting depth', () {
      final projected = endUserSafeProjection(_envelope(), isAdmin: false);

      // No internal key survives at the top level.
      for (final key in _forbiddenKeys) {
        expect(projected.containsKey(key), isFalse,
            reason: 'internal key "$key" must be dropped');
      }

      // Nested internal keys are dropped too, but benign siblings survive.
      final metadata = projected['metadata'] as Map<String, dynamic>;
      expect(metadata.containsKey('retrieval_errors'), isFalse);
      expect(metadata.containsKey('source_errors'), isFalse);
      expect(metadata['note'], 'kept');

      // User-facing content is preserved.
      expect(projected['reply'], 'Bạn nên uống theo chỉ định của bác sĩ.');
      expect(projected['model_used'], 'deepseek-v3.2');
      expect(projected['citations'], isA<List>());

      // No forbidden token leaks anywhere in the serialized projection.
      final serialized = projected.toString().toLowerCase();
      for (final leak in const <String>[
        'source_errors',
        'rag_mode',
        'retrieved_ids',
        'openfda',
        'rxnav',
        'local-synth',
      ]) {
        expect(serialized.contains(leak), isFalse,
            reason: 'token "$leak" must not leak to non-admin projection');
      }
    });

    test('does not mutate the source envelope', () {
      final source = _envelope();
      endUserSafeProjection(source, isAdmin: false);
      expect(source.containsKey('source_errors'), isTrue,
          reason: 'projection must not mutate its input');
    });
  });

  group('endUserSafeProjection — admin', () {
    test('preserves the full envelope including runtime detail', () {
      final projected = endUserSafeProjection(_envelope(), isAdmin: true);
      expect(projected['source_errors'], isNotNull);
      expect(projected['mode'], 'external_plus_local');
      expect(projected['reply'], isNotNull);
      // Deep-copied: mutating the result must not affect a fresh envelope.
      (projected['retrieval'] as Map)['k'] = 999;
      expect(_envelope()['retrieval'], {'k': 8, 'route': 'dense'});
    });
  });

  group('EndUserSafeAnswer widget', () {
    testWidgets('non-admin render contains no internal field values',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: EndUserSafeAnswer(envelope: _envelope(), role: 'normal'),
          ),
        ),
      ));
      await tester.pumpAndSettle();

      // Answer text + a citation are shown.
      expect(find.textContaining('uống theo chỉ định'), findsOneWidget);
      expect(find.textContaining('Hướng dẫn sử dụng thuốc'), findsOneWidget);

      // No internal runtime value is rendered anywhere in the tree.
      for (final leak in const <String>[
        'external_plus_local',
        'deepseek_unavailable',
        'http_400',
        'local-synth',
        'rxnav',
        'verdict',
      ]) {
        expect(find.textContaining(leak), findsNothing,
            reason: 'internal value "$leak" must not render for non-admin');
      }

      // The admin-only detail section is absent for a non-admin role.
      expect(find.byKey(const Key('end-user-safe-admin-detail')), findsNothing);
    });

    testWidgets('admin render exposes the full-detail section', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: EndUserSafeAnswer(envelope: _envelope(), role: 'admin'),
          ),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('end-user-safe-admin-detail')), findsOneWidget);
    });
  });
}

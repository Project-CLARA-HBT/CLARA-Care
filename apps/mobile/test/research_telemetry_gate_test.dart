// Feature: clara-research — role-gated research telemetry on mobile (R19.4).
//
// Unit + generated (property-style) tests for the pure role-gate helper in
// `lib/core/research_telemetry_gate.dart`, which mirrors the web Requirement 3
// gate:
//
//   * the detailed telemetry rail is exposed iff the role is `admin`;
//   * every recognized role still gets a sanitized summary;
//   * an unevaluable role fails closed (no telemetry) AND blocks the job
//     (Requirement 19.4).
//
// The gate is a pure function of the role, so it is exercised across many
// generated roles/payloads (>=200 iterations) without rendering widgets.

import 'dart:math';

import 'package:clara_mobile/core/research_telemetry_gate.dart';
import 'package:flutter_test/flutter_test.dart';

String _randomString(Random rng, int length) {
  const chars =
      'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_/:';
  return String.fromCharCodes(
    List.generate(length, (_) => chars.codeUnitAt(rng.nextInt(chars.length))),
  );
}

void main() {
  const knownRoles = <String>['normal', 'researcher', 'doctor', 'admin'];
  const nonAdminRoles = <String>['normal', 'researcher', 'doctor'];

  group('evaluateTelemetryGate — detail exposed iff admin (R3.1, R3.3)', () {
    test('admin role exposes the detailed rail and the summary', () {
      final decision = evaluateTelemetryGate('admin');
      expect(decision.canEvaluate, isTrue);
      expect(decision.showDetailed, isTrue);
      expect(decision.showSummary, isTrue);
      expect(decision.blockJob, isFalse);
    });

    test('non-admin recognized roles get summary only', () {
      for (final role in nonAdminRoles) {
        final decision = evaluateTelemetryGate(role);
        expect(decision.canEvaluate, isTrue, reason: 'role $role evaluable');
        expect(decision.showDetailed, isFalse,
            reason: 'role $role must not see detailed rail');
        expect(decision.showSummary, isTrue);
        expect(decision.blockJob, isFalse);
      }
    });

    test('detailed rail is shown iff role is admin (generated)', () {
      final rng = Random(13572468);
      const iterations = 250;
      for (var i = 0; i < iterations; i++) {
        final role = knownRoles[rng.nextInt(knownRoles.length)];
        // Randomly perturb case/whitespace; recognized roles stay evaluable.
        final perturbed = rng.nextBool()
            ? '  ${role.toUpperCase()} '
            : (rng.nextBool() ? role.toUpperCase() : ' $role');
        final decision = evaluateTelemetryGate(perturbed);
        expect(decision.canEvaluate, isTrue,
            reason: 'recognized role "$perturbed" should be evaluable');
        expect(decision.showDetailed, equals(role == 'admin'),
            reason: 'detailed iff admin for "$perturbed" on iteration $i');
        expect(decision.showSummary, isTrue);
        expect(decision.blockJob, isFalse);
      }
    });
  });

  group('evaluateTelemetryGate — fail-closed block (R3.6, R19.4)', () {
    test('null/empty roles fail closed and block the job', () {
      for (final role in <String?>[null, '', '   ']) {
        final decision = evaluateTelemetryGate(role);
        expect(decision.canEvaluate, isFalse, reason: 'role "$role"');
        expect(decision.showDetailed, isFalse);
        expect(decision.showSummary, isFalse,
            reason: 'no telemetry is exposed when role cannot be evaluated');
        expect(decision.blockJob, isTrue,
            reason: 'unevaluable role must block the research job');
      }
    });

    test('unrecognized roles fail closed and block the job (generated)', () {
      final rng = Random(987654321);
      const iterations = 250;
      for (var i = 0; i < iterations; i++) {
        final candidate = _randomString(rng, 1 + rng.nextInt(20));
        // Skip the rare case where a generated string normalizes to a known
        // role; those are covered by the evaluable-role tests above.
        if (knownRoles.contains(candidate.trim().toLowerCase())) {
          continue;
        }
        final decision = evaluateTelemetryGate(candidate);
        expect(decision.canEvaluate, isFalse,
            reason: 'unrecognized role "$candidate" must not be evaluable');
        expect(decision.showDetailed, isFalse);
        expect(decision.showSummary, isFalse);
        expect(decision.blockJob, isTrue,
            reason: 'unrecognized role "$candidate" must block the job');
      }
    });
  });

  group('stripTelemetryLabels — sanitized summary labels (R3.2, R3.5)', () {
    const internalLabels = <String>[
      'research mode',
      'RAG mode',
      'rag mode',
      'Fallback mode',
      'retrieval',
      'RETRIEVAL',
      'Policy: Warn',
      'policy: allow',
      'policy: warn / allow',
    ];

    bool containsInternalLabel(String text) {
      final lowered = text.toLowerCase();
      return lowered.contains('research mode') ||
          lowered.contains('rag mode') ||
          lowered.contains('fallback mode') ||
          lowered.contains('retrieval') ||
          lowered.contains('policy: warn') ||
          lowered.contains('policy: allow');
    }

    test('removes each known internal label', () {
      for (final label in internalLabels) {
        expect(containsInternalLabel(stripTelemetryLabels(label)), isFalse,
            reason: 'label "$label" should be stripped');
      }
    });

    test('preserves surrounding user-facing copy', () {
      final out = stripTelemetryLabels('Kết quả (retrieval) đã sẵn sàng');
      expect(out, contains('Kết quả'));
      expect(out, contains('đã sẵn sàng'));
      expect(containsInternalLabel(out), isFalse);
    });

    test('is idempotent: strip(strip(x)) == strip(x) (generated)', () {
      final rng = Random(2468013579);
      const iterations = 250;
      for (var i = 0; i < iterations; i++) {
        final parts = <String>[];
        final count = 1 + rng.nextInt(5);
        for (var j = 0; j < count; j++) {
          parts.add(rng.nextBool()
              ? internalLabels[rng.nextInt(internalLabels.length)]
              : _randomString(rng, rng.nextInt(8)));
        }
        final text = parts.join(' ');
        final once = stripTelemetryLabels(text);
        final twice = stripTelemetryLabels(once);
        expect(twice, equals(once), reason: 'idempotent for "$text"');
        expect(containsInternalLabel(once), isFalse,
            reason: 'no internal label remains in "$once"');
      }
    });

    test('returns an empty string for empty/null input', () {
      expect(stripTelemetryLabels(''), '');
      expect(stripTelemetryLabels(null), '');
    });
  });
}

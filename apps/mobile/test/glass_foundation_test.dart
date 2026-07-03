// Unit + widget tests for the liquid-glass foundation
// (clara-mobile-liquid-glass, R1/R6/R11).
//
// These lock the two safety-critical decision points of the glass system:
//
//   1. `GlassScope.resolveEnabled` — the PURE truth table that decides whether
//      the translucent material is affordable. It must fail closed: glass is on
//      ONLY when the build gate is on AND the device is fully capable
//      (no reduce-transparency, not low-end).
//   2. `GlassSurface` — must emit NO `BackdropFilter` (the expensive/opaque-
//      breaking translucent path) whenever the ambient scope is disabled OR the
//      surface is `clinical`, and MUST emit one only inside an enabled scope
//      with `clinical: false`. This is the regression lock that keeps clinical
//      content (dosages, DDI, FIDES verdicts) off translucent glass and keeps
//      the accessible/opaque path as the automatic default.
//
// No platform channels, no live network I/O.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clara_mobile/core/device_capability.dart';
import 'package:clara_mobile/theme/glass/glass_scope.dart';
import 'package:clara_mobile/theme/glass/glass_surface.dart';

/// A fully-capable device snapshot (glass affordable on the capability axis).
const _capable = DeviceCapabilitySnapshot(
  reduceTransparency: false,
  lowEnd: false,
);

void main() {
  group('GlassScope.resolveEnabled — pure truth table (R1/R6, fail-closed)',
      () {
    test('build gate OFF ⇒ always false, even on a fully-capable device', () {
      expect(
        GlassScope.resolveEnabled(buildGateOn: false, capability: _capable),
        isFalse,
      );
    });

    test('build gate OFF ⇒ false even when capability signals also degrade',
        () {
      expect(
        GlassScope.resolveEnabled(
          buildGateOn: false,
          capability: const DeviceCapabilitySnapshot(
            reduceTransparency: true,
            lowEnd: true,
          ),
        ),
        isFalse,
      );
    });

    test('build gate ON + reduceTransparency ⇒ false', () {
      expect(
        GlassScope.resolveEnabled(
          buildGateOn: true,
          capability: const DeviceCapabilitySnapshot(
            reduceTransparency: true,
            lowEnd: false,
          ),
        ),
        isFalse,
      );
    });

    test('build gate ON + lowEnd device ⇒ false', () {
      expect(
        GlassScope.resolveEnabled(
          buildGateOn: true,
          capability: const DeviceCapabilitySnapshot(
            reduceTransparency: false,
            lowEnd: true,
          ),
        ),
        isFalse,
      );
    });

    test('build gate ON + fully capable ⇒ true (the only true case)', () {
      expect(
        GlassScope.resolveEnabled(buildGateOn: true, capability: _capable),
        isTrue,
      );
    });
  });

  group('GlassScope.of — fail-closed when absent', () {
    testWidgets('returns false when no GlassScope is in the tree',
        (tester) async {
      late bool resolved;
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) {
              resolved = GlassScope.of(context);
              return const SizedBox.shrink();
            },
          ),
        ),
      );

      expect(resolved, isFalse);
    });
  });

  group('GlassSurface — BackdropFilter safety invariant (R6/R11)', () {
    testWidgets('scope disabled ⇒ NO BackdropFilter (opaque fallback)',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: GlassScope(
            enabled: false,
            child: GlassSurface(child: Text('surface')),
          ),
        ),
      );

      expect(find.byType(BackdropFilter), findsNothing);
    });

    testWidgets(
        'clinical: true inside an ENABLED scope ⇒ NO BackdropFilter '
        '(clinical content never on translucent glass)', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: GlassScope(
            enabled: true,
            child: GlassSurface(clinical: true, child: Text('dosage')),
          ),
        ),
      );

      expect(find.byType(BackdropFilter), findsNothing);
    });

    testWidgets('scope enabled + clinical: false ⇒ emits a BackdropFilter',
        (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: GlassScope(
            enabled: true,
            child: GlassSurface(child: Text('chrome')),
          ),
        ),
      );

      expect(find.byType(BackdropFilter), findsWidgets);
    });
  });
}

// Unit tests for the FHIR interoperability mobile feature flag (Phase PH11).
//
// Validates:
//   * Default value is false (fail-closed, dark by default).
//   * Server-scoped grant resolves to true.
//   * Build-time override resolves to true.
//   * Missing/empty/malformed summary resolves to false.

import 'package:clara_mobile/core/feature_flags.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FHIR Interoperability Feature Flag (PH11)', () {
    test('defaults to false when unconfigured (fail-closed)', () {
      final resolver = MobileFeatureFlagResolver();
      expect(resolver.fhirInteroperabilityEnabled, isFalse);
      expect(
        resolver.isEnabled(
          MobileFeatureFlags.fhirInteroperabilityMobileEnabled,
        ),
        isFalse,
      );
    });

    test('resolves to true when granted by server summary', () {
      final summary = <String, dynamic>{
        'feature_flags': <String, dynamic>{
          MobileFeatureFlags.fhirInteroperabilityMobileEnabled: true,
        },
      };
      final resolver = MobileFeatureFlagResolver(summary: summary);
      expect(resolver.fhirInteroperabilityEnabled, isTrue);
      expect(
        resolver.serverGranted(
          MobileFeatureFlags.fhirInteroperabilityMobileEnabled,
        ),
        isTrue,
      );
    });

    test('resolves to false when explicitly set to false by server', () {
      final summary = <String, dynamic>{
        'feature_flags': <String, dynamic>{
          MobileFeatureFlags.fhirInteroperabilityMobileEnabled: false,
        },
      };
      final resolver = MobileFeatureFlagResolver(summary: summary);
      expect(resolver.fhirInteroperabilityEnabled, isFalse);
    });

    test('resolves to true when enabled via build-time defaults', () {
      final customBuildDefaults = <String, bool>{
        MobileFeatureFlags.fhirInteroperabilityMobileEnabled: true,
      };
      final resolver = MobileFeatureFlagResolver(
        buildDefaults: customBuildDefaults,
      );
      expect(resolver.fhirInteroperabilityEnabled, isTrue);
      expect(
        resolver.buildDefault(
          MobileFeatureFlags.fhirInteroperabilityMobileEnabled,
        ),
        isTrue,
      );
    });

    test('all list includes fhirInteroperabilityMobileEnabled', () {
      expect(
        MobileFeatureFlags.all,
        contains(MobileFeatureFlags.fhirInteroperabilityMobileEnabled),
      );
    });

    test('resolved map contains entry for fhirInteroperabilityMobileEnabled', () {
      final resolver = MobileFeatureFlagResolver();
      final map = resolver.resolved;
      expect(
        map.containsKey(MobileFeatureFlags.fhirInteroperabilityMobileEnabled),
        isTrue,
      );
      expect(
        map[MobileFeatureFlags.fhirInteroperabilityMobileEnabled],
        isFalse,
      );
    });
  });
}

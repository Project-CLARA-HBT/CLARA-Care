// Feature: clara-mobile-feature-parity — mobile feature-flag resolver
// (Requirements 13.1, 15.1; supports Property 1 flags-off equivalence).
//
// Unit + generated (property-style) tests for the pure resolver in
// `lib/core/feature_flags.dart`, which combines the server `feature_flags`
// map from `mobile/summary` with compile-time `--dart-define` defaults:
//
//   * every new flag defaults to false;
//   * unknown/missing summary, non-map flags, missing keys, and non-`true`
//     values all resolve to false (fail-closed);
//   * a gate is open when the server grants it OR the build default enables it.
//
// The resolver is a pure function of the summary plus injectable build
// defaults, so it is exercised across many generated inputs without rendering
// widgets.

import 'dart:math';

import 'package:clara_mobile/core/feature_flags.dart';
import 'package:flutter_test/flutter_test.dart';

/// Build defaults that are all OFF, mirroring a normal (production) build.
const Map<String, bool> _allOffDefaults = <String, bool>{
  MobileFeatureFlags.chatMobileEnabled: false,
  MobileFeatureFlags.selfmedCabinetMobileEnabled: false,
  MobileFeatureFlags.scribeMobileEnabled: false,
  MobileFeatureFlags.phrEnhancedMobileEnabled: false,
  MobileFeatureFlags.modelDisclosureMobileEnabled: false,
  MobileFeatureFlags.transparencyNoticeMobileEnabled: false,
  MobileFeatureFlags.consentCenterMobileEnabled: false,
  MobileFeatureFlags.sharingMobileEnabled: false,
  MobileFeatureFlags.uxPolishEnabled: false,
  MobileFeatureFlags.lifeMapVietnameseDrafts: false,
};

void main() {
  group('MobileFeatureFlagResolver — defaults to false (Req 15.1)', () {
    test('null summary resolves every new flag to false', () {
      final resolver = MobileFeatureFlagResolver(
        summary: null,
        buildDefaults: _allOffDefaults,
      );
      for (final key in MobileFeatureFlags.all) {
        expect(resolver.isEnabled(key), isFalse, reason: 'flag "$key"');
      }
      // Convenience getters agree with isEnabled.
      expect(resolver.chatEnabled, isFalse);
      expect(resolver.selfMedCabinetEnabled, isFalse);
      expect(resolver.scribeEnabled, isFalse);
      expect(resolver.phrEnhancedEnabled, isFalse);
      expect(resolver.modelDisclosureEnabled, isFalse);
      expect(resolver.transparencyNoticeEnabled, isFalse);
      expect(resolver.consentCenterEnabled, isFalse);
      expect(resolver.sharingEnabled, isFalse);
      expect(resolver.uxPolishEnabled, isFalse);
      expect(resolver.lifeMapVietnameseDraftsEnabled, isFalse);
    });

    test('compile-time build defaults are all false (Req 15.1)', () {
      for (final key in MobileFeatureFlags.all) {
        expect(
          kMobileFeatureFlagBuildDefaults[key],
          isFalse,
          reason: 'compile-time default for "$key" must ship OFF',
        );
      }
    });
  });

  group('MobileFeatureFlagResolver — fail-closed (unknown/missing ⇒ false)',
      () {
    test('non-map feature_flags resolves to false', () {
      final resolver = MobileFeatureFlagResolver(
        summary: <String, dynamic>{'feature_flags': 'not-a-map'},
        buildDefaults: _allOffDefaults,
      );
      expect(resolver.chatEnabled, isFalse);
      expect(resolver.resolved.values.every((v) => v == false), isTrue);
    });

    test('missing feature_flags key resolves to false', () {
      final resolver = MobileFeatureFlagResolver(
        summary: <String, dynamic>{'role': 'admin'},
        buildDefaults: _allOffDefaults,
      );
      expect(resolver.chatEnabled, isFalse);
    });

    test('non-true server values (null/false/1/"true") resolve to false', () {
      final resolver = MobileFeatureFlagResolver(
        summary: <String, dynamic>{
          'feature_flags': <String, dynamic>{
            MobileFeatureFlags.chatMobileEnabled: false,
            MobileFeatureFlags.scribeMobileEnabled: null,
            MobileFeatureFlags.sharingMobileEnabled: 1,
            MobileFeatureFlags.consentCenterMobileEnabled: 'true',
          },
        },
        buildDefaults: _allOffDefaults,
      );
      expect(resolver.chatEnabled, isFalse);
      expect(resolver.scribeEnabled, isFalse);
      expect(resolver.sharingEnabled, isFalse);
      expect(resolver.consentCenterEnabled, isFalse);
    });

    test('unknown flag key resolves to false', () {
      final resolver = MobileFeatureFlagResolver(
        summary: <String, dynamic>{
          'feature_flags': <String, dynamic>{'totally_unknown_flag': true},
        },
        buildDefaults: _allOffDefaults,
      );
      expect(resolver.isEnabled('totally_unknown_flag'), isTrue,
          reason: 'explicit server-true on any key is honored');
      expect(resolver.isEnabled('never_defined_flag'), isFalse);
    });
  });

  group('MobileFeatureFlagResolver — combine semantics (Req 13.1, 15.1)', () {
    test('server true grants the gate even when build default is off', () {
      final resolver = MobileFeatureFlagResolver(
        summary: <String, dynamic>{
          'feature_flags': <String, dynamic>{
            MobileFeatureFlags.chatMobileEnabled: true,
          },
        },
        buildDefaults: _allOffDefaults,
      );
      expect(resolver.chatEnabled, isTrue);
      expect(resolver.serverGranted(MobileFeatureFlags.chatMobileEnabled),
          isTrue);
      // Other gates remain closed.
      expect(resolver.scribeEnabled, isFalse);
    });

    test('build default true grants the gate when server is silent', () {
      final resolver = MobileFeatureFlagResolver(
        summary: <String, dynamic>{'feature_flags': <String, dynamic>{}},
        buildDefaults: <String, bool>{
          ..._allOffDefaults,
          MobileFeatureFlags.scribeMobileEnabled: true,
        },
      );
      expect(resolver.scribeEnabled, isTrue);
      expect(resolver.buildDefault(MobileFeatureFlags.scribeMobileEnabled),
          isTrue);
      expect(resolver.serverGranted(MobileFeatureFlags.scribeMobileEnabled),
          isFalse);
      expect(resolver.chatEnabled, isFalse);
    });
  });

  group('MobileFeatureFlagResolver — property: isEnabled == server OR build',
      () {
    test('holds across 300 generated summary/default combinations', () {
      final rng = Random(20240517);
      for (var i = 0; i < 300; i++) {
        final serverFlags = <String, dynamic>{};
        final buildDefaults = <String, bool>{};
        final expected = <String, bool>{};
        for (final key in MobileFeatureFlags.all) {
          // Server value: randomly true / false / non-bool / absent.
          final serverRoll = rng.nextInt(4);
          bool serverTrue = false;
          switch (serverRoll) {
            case 0:
              serverFlags[key] = true;
              serverTrue = true;
              break;
            case 1:
              serverFlags[key] = false;
              break;
            case 2:
              serverFlags[key] = 'true'; // non-bool ⇒ not granted
              break;
            case 3:
              // absent
              break;
          }
          final buildTrue = rng.nextBool();
          buildDefaults[key] = buildTrue;
          expected[key] = serverTrue || buildTrue;
        }

        final resolver = MobileFeatureFlagResolver(
          summary: <String, dynamic>{'feature_flags': serverFlags},
          buildDefaults: buildDefaults,
        );

        for (final key in MobileFeatureFlags.all) {
          expect(resolver.isEnabled(key), expected[key],
              reason: 'iter $i, flag "$key"');
        }
      }
    });
  });
}

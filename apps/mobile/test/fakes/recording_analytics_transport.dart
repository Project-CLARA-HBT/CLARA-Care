// Reusable test fake for the CLARA mobile feature-parity spec (task 1.1).
//
// A recording [AnalyticsTransport] double (implements the production contract
// in `lib/core/analytics.dart`). It captures every `init`/`identify`/`capture`
// interaction so widget/property tests can assert:
//   * ZERO transmissions occur when the facade is unconfigured or un-consented
//     (Requirements 11.2; design Property 7 — consent suppression).
//   * Captured payloads never carry PII (design Property 5).
//   * `identify` only ever receives an opaque pseudonymous id (Property 6).
//
// This is the single shared implementation new screen tests should inject,
// replacing the per-file copies (see `analytics_test.dart`).

import 'package:clara_mobile/core/analytics.dart';

/// Records every transport interaction so tests can assert on transmission.
///
/// Drop-in for any `Analytics(transport: RecordingAnalyticsTransport())` call
/// site. Nothing is sent anywhere — the recorder only accumulates calls.
class RecordingAnalyticsTransport implements AnalyticsTransport {
  /// Number of times [init] was invoked (the SDK "load" signal).
  int initCalls = 0;

  /// The configs passed to [init], in order.
  final List<AnalyticsConfig> configs = <AnalyticsConfig>[];

  /// Opaque distinct ids passed to [identify], in order.
  final List<String> identified = <String>[];

  /// Events passed to [capture], in order (already PII-stripped by the facade).
  final List<AnalyticsEvent> captured = <AnalyticsEvent>[];

  /// Total outbound interactions (identify + capture) — i.e. transmissions.
  ///
  /// Use this to assert a screen produced zero analytics traffic.
  int get transmissions => identified.length + captured.length;

  /// The most recently captured event, or null if none captured yet.
  AnalyticsEvent? get lastEvent => captured.isEmpty ? null : captured.last;

  /// Names of all captured events, in order. Convenient for `contains` asserts.
  List<String> get capturedNames =>
      captured.map((event) => event.name).toList(growable: false);

  /// Clears all recorded interactions so a single transport can be reused
  /// across phases of a test.
  void reset() {
    initCalls = 0;
    configs.clear();
    identified.clear();
    captured.clear();
  }

  @override
  void init(AnalyticsConfig config) {
    initCalls++;
    configs.add(config);
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

// Feature: clara-mobile-feature-parity — Task 10.2 (Req 8.3, 8.5).
//
// Widget tests for the self-service DSAR surface:
//   * Submitting a request (export / delete) shows a PII-free acknowledgement
//     (Req 8.3).
//   * With the `consent_center_mobile_enabled` gate off, the surface is inert:
//     no controls and no submit is possible (Req 8.6 / 15.1).
//   * NO PII is collected client-side: the surface exposes no text input
//     fields, and only the coarse request *kind* crosses the submit seam and
//     reaches analytics (Req 8.5).
//
// A fake [DsarSubmitter] is injected directly, so the tests run without
// platform channels or a live server.

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/screens/dsar_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fakes.dart';

MobileFeatureFlagResolver _resolver({required bool dsarEnabled}) {
  return MobileFeatureFlagResolver(
    summary: <String, dynamic>{
      'feature_flags': <String, dynamic>{
        MobileFeatureFlags.consentCenterMobileEnabled: dsarEnabled,
      },
    },
    buildDefaults: const <String, bool>{},
  );
}

Analytics _analytics(RecordingAnalyticsTransport transport) {
  return Analytics(transport: transport)
    ..init(
      const AnalyticsConfig(provider: 'test', apiKey: 'k'),
      consentGranted: true,
    );
}

DsarAcknowledgement _ack(DsarRequestKind kind) => DsarAcknowledgement(
      requestId: 42,
      kind: kind.wireValue,
      status: 'received',
      createdAt: '2026-04-01T00:00:00Z',
      dueAt: '2026-05-01T00:00:00Z',
      statutoryWindowDays: 30,
    );

void main() {
  testWidgets('submitting an export request shows an acknowledgement (Req 8.3)',
      (tester) async {
    final kinds = <DsarRequestKind>[];
    Future<DsarAcknowledgement> submitter(DsarRequestKind kind) async {
      kinds.add(kind);
      return _ack(kind);
    }

    await tester.pumpWidget(MaterialApp(
      home: DsarScreen(
        resolver: _resolver(dsarEnabled: true),
        submitter: submitter,
      ),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('dsar-submit-export')));
    await tester.pumpAndSettle();

    expect(kinds, [DsarRequestKind.export]);
    // Acknowledgement is shown with non-PII fields only (Req 8.3).
    expect(find.byKey(const Key('dsar-acknowledgement')), findsOneWidget);
    expect(find.textContaining('Đã tiếp nhận yêu cầu'), findsOneWidget);
    expect(find.textContaining('#42'), findsOneWidget);
    expect(find.textContaining('export'), findsOneWidget);
  });

  testWidgets('deleting requires confirmation then acknowledges (Req 8.3)',
      (tester) async {
    final kinds = <DsarRequestKind>[];
    Future<DsarAcknowledgement> submitter(DsarRequestKind kind) async {
      kinds.add(kind);
      return _ack(kind);
    }

    await tester.pumpWidget(MaterialApp(
      home: DsarScreen(
        resolver: _resolver(dsarEnabled: true),
        submitter: submitter,
      ),
    ));
    await tester.pumpAndSettle();

    // Tapping delete opens a confirm dialog; nothing is submitted yet.
    await tester.tap(find.byKey(const Key('dsar-submit-delete')));
    await tester.pumpAndSettle();
    expect(kinds, isEmpty);
    expect(find.byKey(const Key('dsar-confirm-delete')), findsOneWidget);

    // Confirm → the delete request is submitted and acknowledged.
    await tester.tap(find.byKey(const Key('dsar-confirm-delete')));
    await tester.pumpAndSettle();
    expect(kinds, [DsarRequestKind.delete]);
    expect(find.byKey(const Key('dsar-acknowledgement')), findsOneWidget);
  });

  testWidgets('gate off: surface is inert with no controls (Req 8.6)',
      (tester) async {
    var called = 0;
    Future<DsarAcknowledgement> submitter(DsarRequestKind kind) async {
      called += 1;
      return _ack(kind);
    }

    await tester.pumpWidget(MaterialApp(
      home: DsarScreen(
        resolver: _resolver(dsarEnabled: false),
        submitter: submitter,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('dsar-disabled')), findsOneWidget);
    expect(find.byKey(const Key('dsar-submit-export')), findsNothing);
    expect(find.byType(FilledButton), findsNothing);
    expect(called, 0);
  });

  testWidgets(
      'collects NO PII: no text fields, only the kind is transmitted '
      '(Req 8.5)', (tester) async {
    final transport = RecordingAnalyticsTransport();
    final analytics = _analytics(transport);
    final kinds = <DsarRequestKind>[];
    Future<DsarAcknowledgement> submitter(DsarRequestKind kind) async {
      kinds.add(kind);
      return _ack(kind);
    }

    await tester.pumpWidget(MaterialApp(
      home: DsarScreen(
        resolver: _resolver(dsarEnabled: true),
        submitter: submitter,
        analytics: analytics,
      ),
    ));
    await tester.pumpAndSettle();

    // No free-text identifier inputs exist anywhere on the surface (Req 8.5).
    expect(find.byType(TextField), findsNothing);
    expect(find.byType(TextFormField), findsNothing);

    await tester.tap(find.byKey(const Key('dsar-submit-export')));
    await tester.pumpAndSettle();

    // The submit seam received only the coarse kind enum — no PII.
    expect(kinds, [DsarRequestKind.export]);

    // The single analytics event carries only the non-PII kind label.
    expect(transport.captured, isNotEmpty);
    final submitted =
        transport.captured.where((e) => e.name == 'mobile_dsar_submitted');
    expect(submitted.length, 1);
    expect(submitted.first.props, <String, Object?>{'kind': 'export'});
  });
}

// Feature: clara-mobile-feature-parity — canonical DSAR transport contract.
//
// The screen sends only a closed request kind through ApiClient. Deletion is a
// separate confirmed call to the server's transactional delete endpoint; it is
// never downgraded to a generic request.

import 'package:clara_mobile/core/analytics.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/screens/dsar_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes/fakes.dart';

Widget _host(Widget child) => MaterialApp(
      locale: const Locale('vi'),
      supportedLocales: const [Locale('vi'), Locale('en')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: child,
    );

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

Map<String, dynamic> _ack(DsarRequestKind kind) => <String, dynamic>{
      'enabled': true,
      'request_id': 42,
      'kind': kind.wireValue,
      'status': 'received',
      'created_at': '2026-04-01T00:00:00Z',
      'due_at': '2026-05-01T00:00:00Z',
      'statutory_window_days': 30,
    };

void main() {
  testWidgets('submitting export uses canonical API request and acknowledges',
      (tester) async {
    final api = FakeApiClient()
      ..stub('submitDsarRequest', response: _ack(DsarRequestKind.export));
    final session = await FakeSessionStore.authenticated();

    await tester.pumpWidget(_host(
      DsarScreen(
        apiClient: api,
        resolver: _resolver(dsarEnabled: true),
        sessionStore: session,
      ),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('dsar-submit-export')));
    await tester.pumpAndSettle();

    expect(api.callsTo('submitDsarRequest').single.args['kind'], 'export');
    expect(find.byKey(const Key('dsar-acknowledgement')), findsOneWidget);
    expect(find.textContaining('Đã tiếp nhận yêu cầu'), findsOneWidget);
    expect(find.textContaining('#42'), findsOneWidget);
  });

  testWidgets('deletion needs confirmation then calls transactional endpoint',
      (tester) async {
    final api = FakeApiClient()
      ..stub('deleteDsarData', response: _ack(DsarRequestKind.delete));
    final session = await FakeSessionStore.authenticated();

    await tester.pumpWidget(_host(
      DsarScreen(
        apiClient: api,
        resolver: _resolver(dsarEnabled: true),
        sessionStore: session,
      ),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('dsar-submit-delete')));
    await tester.pumpAndSettle();
    expect(api.wasCalled('deleteDsarData'), isFalse);
    expect(find.byKey(const Key('dsar-confirm-delete')), findsOneWidget);

    await tester.tap(find.byKey(const Key('dsar-confirm-delete')));
    await tester.pumpAndSettle();
    expect(api.wasCalled('deleteDsarData'), isTrue);
    expect(api.wasCalled('submitDsarRequest'), isFalse);
    expect(find.byKey(const Key('dsar-acknowledgement')), findsOneWidget);
  });

  testWidgets('gate off is inert with no DSAR request', (tester) async {
    final api = FakeApiClient();
    final session = await FakeSessionStore.authenticated();

    await tester.pumpWidget(_host(
      DsarScreen(
        apiClient: api,
        resolver: _resolver(dsarEnabled: false),
        sessionStore: session,
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('dsar-disabled')), findsOneWidget);
    expect(find.byKey(const Key('dsar-submit-export')), findsNothing);
    expect(api.invocations, isEmpty);
  });

  testWidgets('collects no PII: no text fields, only a closed request kind',
      (tester) async {
    final transport = RecordingAnalyticsTransport();
    final api = FakeApiClient()
      ..stub('submitDsarRequest', response: _ack(DsarRequestKind.export));
    final session = await FakeSessionStore.authenticated();

    await tester.pumpWidget(_host(
      DsarScreen(
        apiClient: api,
        resolver: _resolver(dsarEnabled: true),
        sessionStore: session,
        analytics: _analytics(transport),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.byType(TextField), findsNothing);
    expect(find.byType(TextFormField), findsNothing);

    await tester.tap(find.byKey(const Key('dsar-submit-export')));
    await tester.pumpAndSettle();

    expect(api.callsTo('submitDsarRequest').single.args, {'kind': 'export'});
    final submitted = transport.captured
        .where((event) => event.name == 'mobile_dsar_submitted');
    expect(submitted.length, 1);
    expect(submitted.single.props, <String, Object?>{'kind': 'export'});
  });
}

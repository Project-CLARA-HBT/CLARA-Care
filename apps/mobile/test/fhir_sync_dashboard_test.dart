// Widget tests for [FhirSyncDashboardScreen] (Phase PH11).
//
// Validates:
//   * Correct rendering of FHIR R4 conformance and capability statement.
//   * Non-accredited / summary-not-ips honest regulatory disclosure invariant.
//   * Connectors list and sync state display.
//   * Sync trigger invokes [ApiClient.syncConnector] and reflects feedback.
//   * Navigation to consented export view.
//   * Error and empty state handling.

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/experience/fhir/fhir_export_screen.dart';
import 'package:clara_mobile/experience/fhir/fhir_sync_dashboard_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class InMemorySessionSecureStorage implements SessionSecureStorage {
  final Map<String, String> data = {};

  @override
  Future<String?> read(String key) async => data[key];

  @override
  Future<void> write(String key, String value) async => data[key] = value;

  @override
  Future<void> delete(String key) async => data.remove(key);
}

void main() {
  const token = 'test-session-token';

  Future<SessionStore> makeSessionStore() async {
    final storage = InMemorySessionSecureStorage();
    final store = SessionStore(storage: storage);
    await store.setSession(
      email: 'patient@clara.vn',
      accessToken: token,
      refreshToken: 'test-refresh',
      role: 'consumer',
    );
    return store;
  }

  group('FhirSyncDashboardScreen Widget Tests', () {
    testWidgets('renders conformance statement and honest disclosure card', (tester) async {
      final sessionStore = await makeSessionStore();

      final mockHttp = MockClient((request) async {
        if (request.url.path == '/api/v1/lifemap/v2/fhir/conformance') {
          return http.Response(
            jsonEncode({
              'name': 'CLARA LifeMap FHIR R4 projection',
              'fhir_version': '4.0.1',
              'mapping_version': '1.0',
              'conformance': 'fhir-r4-summary-not-ips',
              'bundle_types': ['collection'],
              'operations': {
                'export': {'enabled': true, 'path': '/api/v1/lifemap/v2/export/fhir-r4'},
                'import': {'enabled': false, 'path': '/api/v1/lifemap/v2/import/fhir-r4'},
              },
              'general_fhir_server': false,
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        } else if (request.url.path == '/api/v1/connectors') {
          return http.Response(
            jsonEncode({
              'items': [
                {
                  'id': 'conn-apple',
                  'provider': 'apple_health',
                  'display_label': 'Apple Health',
                  'status': 'connected',
                  'last_synced_at': '2026-10-24 10:30',
                  'data_types': ['vitals', 'steps'],
                },
              ],
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        } else if (request.url.path == '/api/v1/connectors/status-adapter') {
          return http.Response(
            jsonEncode({
              'status': 'healthy',
              'total_connectors': 1,
              'active_connectors': 1,
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('Not Found', 404);
      });

      final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mockHttp);

      await tester.pumpWidget(
        MaterialApp(
          home: FhirSyncDashboardScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );

      // Loading state initial pump
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      await tester.pumpAndSettle();

      // Conformance & Gateway card
      expect(find.textContaining('FHIR v4.0.1'), findsOneWidget);
      expect(find.byKey(const Key('fhir-capability-export')), findsOneWidget);
      expect(find.byKey(const Key('fhir-capability-import')), findsOneWidget);

      // Connector card
      expect(find.text('Apple Health'), findsOneWidget);
      expect(find.textContaining('2026-10-24 10:30'), findsOneWidget);
      expect(find.byKey(const Key('sync-button-conn-apple')), findsOneWidget);

      // Consented export navigation banner
      expect(find.byKey(const Key('open-fhir-export-button')), findsOneWidget);

      // Honest disclosure invariant
      expect(find.textContaining('fhir-r4-summary-not-ips'), findsOneWidget);
    });

    testWidgets('triggers sync on connector and displays feedback', (tester) async {
      final sessionStore = await makeSessionStore();
      bool syncCalled = false;

      final mockHttp = MockClient((request) async {
        if (request.url.path == '/api/v1/lifemap/v2/fhir/conformance') {
          return http.Response(
            jsonEncode({
              'name': 'CLARA LifeMap FHIR R4 projection',
              'fhir_version': '4.0.1',
              'mapping_version': '1.0',
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        } else if (request.url.path == '/api/v1/connectors') {
          return http.Response(
            jsonEncode({
              'items': [
                {
                  'id': 'conn-ehr',
                  'provider': 'hospital_sandbox',
                  'display_label': 'Hospital EHR Sandbox',
                  'status': 'connected',
                  'last_synced_at': '2026-10-24 09:00',
                  'data_types': ['observations'],
                },
              ],
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        } else if (request.url.path == '/api/v1/connectors/conn-ehr/sync') {
          syncCalled = true;
          return http.Response(
            jsonEncode({
              'status': 'queued',
              'connector_id': 'conn-ehr',
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('{}', 200, headers: {'content-type': 'application/json'});
      });

      final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mockHttp);

      await tester.pumpWidget(
        MaterialApp(
          home: FhirSyncDashboardScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );

      await tester.pumpAndSettle();

      final syncButton = find.byKey(const Key('sync-button-conn-ehr'));
      expect(syncButton, findsOneWidget);

      await tester.tap(syncButton);
      await tester.pumpAndSettle();

      expect(syncCalled, isTrue);
      expect(find.byType(SnackBar), findsOneWidget);
      expect(find.text('Hospital EHR Sandbox'), findsOneWidget);
    });

    testWidgets('navigates to FhirExportScreen when export button is tapped', (tester) async {
      final sessionStore = await makeSessionStore();

      final mockHttp = MockClient((request) async {
        if (request.url.path == '/api/v1/lifemap/v2/fhir/conformance') {
          return http.Response(
            jsonEncode({
              'name': 'CLARA LifeMap FHIR R4 projection',
              'fhir_version': '4.0.1',
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        } else if (request.url.path == '/api/v1/connectors') {
          return http.Response(
            jsonEncode({'items': []}),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('{}', 200, headers: {'content-type': 'application/json'});
      });

      final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mockHttp);

      await tester.pumpWidget(
        MaterialApp(
          home: FhirSyncDashboardScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );

      await tester.pumpAndSettle();

      final exportButton = find.byKey(const Key('open-fhir-export-button'));
      expect(exportButton, findsOneWidget);

      await tester.tap(exportButton);
      await tester.pumpAndSettle();

      expect(find.byType(FhirExportScreen), findsOneWidget);
    });

    testWidgets('displays error card when API conformance call fails', (tester) async {
      final sessionStore = await makeSessionStore();

      final mockHttp = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Failed to connect to gateway'}),
          500,
          headers: {'content-type': 'application/json'},
        );
      });

      final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mockHttp);

      await tester.pumpWidget(
        MaterialApp(
          home: FhirSyncDashboardScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.textContaining('Failed to connect to gateway'), findsOneWidget);
    });
  });
}

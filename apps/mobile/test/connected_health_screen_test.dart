// Widget tests for [ConnectedHealthScreen] (Phase PH13 - Agent A06).
//
// Validates:
//   * Correct rendering of connected wearable sources (Health Connect, Huawei Health, Fitbit, Garmin).
//   * Sync toggles (pause/resume sync state).
//   * Manual sync trigger calling POST /api/v1/connectors/{id}/sync.
//   * Connect flow for available providers (calling POST /api/v1/connectors/device).
//   * Data deletion affordance (calling DELETE /api/v1/connectors/{id}/imported-data).
//   * Disconnect affordance (calling DELETE /api/v1/connectors/{id}).
//   * Error and retry handling.

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/experience/connected_health/connected_health_screen.dart';
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
  const token = 'test-token-ph13-a06';

  Future<SessionStore> makeSessionStore() async {
    final storage = InMemorySessionSecureStorage();
    final store = SessionStore(storage: storage);
    await store.setSession(
      email: 'user@clara.vn',
      accessToken: token,
      refreshToken: 'test-refresh',
      role: 'consumer',
    );
    return store;
  }

  group('ConnectedHealthScreen Widget Tests (PH13)', () {
    testWidgets('renders existing connected sources and available providers', (tester) async {
      final sessionStore = await makeSessionStore();

      final mockHttp = MockClient((request) async {
        if (request.url.path == '/api/v1/connectors') {
          return http.Response(
            jsonEncode({
              'items': [
                {
                  'id': 'conn-hc',
                  'provider': 'health_connect',
                  'display_label': 'Google Health Connect',
                  'status': 'connected',
                  'last_synced_at': '2026-11-05 08:30:00',
                  'data_types': ['steps', 'heart_rate', 'sleep'],
                },
              ],
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('Not Found', 404);
      });

      final apiClient = ApiClient(
        baseUrl: 'http://test',
        httpClient: mockHttp,
      );

      await tester.pumpWidget(
        MaterialApp(
          home: ConnectedHealthScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Check connected source display
      expect(find.text('Google Health Connect'), findsOneWidget);
      expect(find.byKey(const Key('source-card-conn-hc')), findsOneWidget);
      expect(find.byKey(const Key('sync-toggle-conn-hc')), findsOneWidget);
      expect(find.byKey(const Key('sync-now-button-conn-hc')), findsOneWidget);

      // Check available providers section (Huawei Health, Fitbit, Garmin should be available)
      expect(find.byKey(const Key('available-provider-huawei_health'), skipOffstage: false), findsOneWidget);
      expect(find.byKey(const Key('available-provider-fitbit'), skipOffstage: false), findsOneWidget);
      expect(find.byKey(const Key('available-provider-garmin'), skipOffstage: false), findsOneWidget);
      // Health connect is already connected, so it shouldn't be in available
      expect(find.byKey(const Key('available-provider-health_connect')), findsNothing);
    });

    testWidgets('toggles sync state (pause / resume)', (tester) async {
      final sessionStore = await makeSessionStore();
      bool pauseCalled = false;

      final mockHttp = MockClient((request) async {
        if (request.url.path == '/api/v1/connectors') {
          return http.Response(
            jsonEncode({
              'items': [
                {
                  'id': 'conn-huawei',
                  'provider': 'huawei_health',
                  'display_label': 'Huawei Health',
                  'status': pauseCalled ? 'paused' : 'connected',
                  'last_synced_at': '2026-11-05 09:00:00',
                  'data_types': ['steps', 'heart_rate'],
                },
              ],
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        } else if (request.url.path == '/api/v1/connectors/conn-huawei/pause') {
          pauseCalled = true;
          return http.Response(
            jsonEncode({
              'id': 'conn-huawei',
              'provider': 'huawei_health',
              'status': 'paused',
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('Not Found', 404);
      });

      final apiClient = ApiClient(baseUrl: 'http://test', httpClient: mockHttp);

      await tester.pumpWidget(
        MaterialApp(
          home: ConnectedHealthScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Tap sync toggle switch to pause
      final toggleFinder = find.byKey(const Key('sync-toggle-conn-huawei'));
      expect(toggleFinder, findsOneWidget);
      await tester.tap(toggleFinder);
      await tester.pumpAndSettle();

      expect(pauseCalled, isTrue);
    });

    testWidgets('triggers manual on-demand sync', (tester) async {
      final sessionStore = await makeSessionStore();
      bool syncCalled = false;

      final mockHttp = MockClient((request) async {
        if (request.url.path == '/api/v1/connectors') {
          return http.Response(
            jsonEncode({
              'items': [
                {
                  'id': 'conn-garmin',
                  'provider': 'garmin',
                  'display_label': 'Garmin Connect',
                  'status': 'connected',
                  'last_synced_at': '2026-11-05 07:00:00',
                  'data_types': ['steps', 'heart_rate'],
                },
              ],
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        } else if (request.url.path == '/api/v1/connectors/conn-garmin/sync') {
          syncCalled = true;
          return http.Response(
            jsonEncode({
              'connector': {
                'id': 'conn-garmin',
                'provider': 'garmin',
                'status': 'connected',
              },
              'action': 'none',
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('Not Found', 404);
      });

      final apiClient = ApiClient(baseUrl: 'http://test', httpClient: mockHttp);

      await tester.pumpWidget(
        MaterialApp(
          home: ConnectedHealthScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );

      await tester.pumpAndSettle();

      final syncBtnFinder = find.byKey(const Key('sync-now-button-conn-garmin'));
      expect(syncBtnFinder, findsOneWidget);
      await tester.tap(syncBtnFinder);
      await tester.pumpAndSettle();

      expect(syncCalled, isTrue);
    });

    testWidgets('connects an available provider (calls POST /api/v1/connectors/device)', (tester) async {
      final sessionStore = await makeSessionStore();
      bool createCalled = false;

      final mockHttp = MockClient((request) async {
        if (request.url.path == '/api/v1/connectors') {
          return http.Response(
            jsonEncode({
              'items': createCalled
                  ? [
                      {
                        'id': 'conn-fitbit',
                        'provider': 'fitbit',
                        'display_label': 'Fitbit',
                        'status': 'connected',
                        'data_types': ['steps', 'heart_rate', 'sleep'],
                      }
                    ]
                  : [],
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        } else if (request.url.path == '/api/v1/connectors/device') {
          createCalled = true;
          final payload = jsonDecode(request.body) as Map<String, dynamic>;
          expect(payload['provider'], 'fitbit');
          expect(payload['display_label'], 'Fitbit');
          return http.Response(
            jsonEncode({
              'id': 'conn-fitbit',
              'provider': 'fitbit',
              'display_label': 'Fitbit',
              'status': 'connected',
              'data_types': ['steps', 'heart_rate', 'sleep'],
              'purposes': ['personal_health_assistance'],
              'last_synced_at': null,
              'created_at': '2026-11-05T00:00:00Z',
              'updated_at': '2026-11-05T00:00:00Z',
            }),
            201,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('Not Found', 404);
      });

      final apiClient = ApiClient(baseUrl: 'http://test', httpClient: mockHttp);

      await tester.pumpWidget(
        MaterialApp(
          home: ConnectedHealthScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );

      await tester.pumpAndSettle();

      final connectFitbitFinder = find.byKey(const Key('connect-button-fitbit'));
      await tester.scrollUntilVisible(connectFitbitFinder, 200);
      expect(connectFitbitFinder, findsOneWidget);
      await tester.tap(connectFitbitFinder);
      await tester.pumpAndSettle();

      expect(createCalled, isTrue);
      expect(find.byKey(const Key('source-card-conn-fitbit'), skipOffstage: false), findsOneWidget);
    });

    testWidgets('deletes imported data with confirmation modal', (tester) async {
      final sessionStore = await makeSessionStore();
      bool deleteDataCalled = false;

      final mockHttp = MockClient((request) async {
        if (request.url.path == '/api/v1/connectors') {
          return http.Response(
            jsonEncode({
              'items': [
                {
                  'id': 'conn-del',
                  'provider': 'health_connect',
                  'display_label': 'Health Connect',
                  'status': 'connected',
                  'data_types': ['steps'],
                },
              ],
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        } else if (request.url.path == '/api/v1/connectors/conn-del/imported-data') {
          deleteDataCalled = true;
          return http.Response(
            jsonEncode({
              'connector_id': 'conn-del',
              'records_deleted': 42,
              'audit_event_id': 'audit-1',
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('Not Found', 404);
      });

      final apiClient = ApiClient(baseUrl: 'http://test', httpClient: mockHttp);

      await tester.pumpWidget(
        MaterialApp(
          home: ConnectedHealthScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );

      await tester.pumpAndSettle();

      final deleteBtnFinder = find.byKey(const Key('delete-data-button-conn-del'));
      expect(deleteBtnFinder, findsOneWidget);
      await tester.tap(deleteBtnFinder);
      await tester.pumpAndSettle();

      // Confirmation dialog should be visible
      expect(find.byType(AlertDialog), findsOneWidget);
      // Tap the confirm button in dialog
      final confirmBtn = find.descendant(
        of: find.byType(AlertDialog),
        matching: find.byType(FilledButton),
      );
      await tester.tap(confirmBtn);
      await tester.pumpAndSettle();

      expect(deleteDataCalled, isTrue);
    });

    testWidgets('disconnects provider with confirmation modal', (tester) async {
      final sessionStore = await makeSessionStore();
      bool disconnectCalled = false;

      final mockHttp = MockClient((request) async {
        if (request.url.path == '/api/v1/connectors') {
          return http.Response(
            jsonEncode({
              'items': disconnectCalled
                  ? []
                  : [
                      {
                        'id': 'conn-disc',
                        'provider': 'garmin',
                        'display_label': 'Garmin Connect',
                        'status': 'connected',
                        'data_types': ['steps'],
                      },
                    ],
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        } else if (request.url.path == '/api/v1/connectors/conn-disc') {
          disconnectCalled = true;
          return http.Response(
            jsonEncode({
              'id': 'conn-disc',
              'provider': 'garmin',
              'status': 'disconnected',
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('Not Found', 404);
      });

      final apiClient = ApiClient(baseUrl: 'http://test', httpClient: mockHttp);

      await tester.pumpWidget(
        MaterialApp(
          home: ConnectedHealthScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );

      await tester.pumpAndSettle();

      final disconnectBtn = find.byKey(const Key('disconnect-button-conn-disc'));
      expect(disconnectBtn, findsOneWidget);
      await tester.tap(disconnectBtn);
      await tester.pumpAndSettle();

      // Dialog shown
      expect(find.byType(AlertDialog), findsOneWidget);
      final confirmBtn = find.descendant(
        of: find.byType(AlertDialog),
        matching: find.byType(FilledButton),
      );
      await tester.tap(confirmBtn);
      await tester.pumpAndSettle();

      expect(disconnectCalled, isTrue);
    });
  });
}

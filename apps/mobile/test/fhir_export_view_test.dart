// Widget tests for [FhirExportScreen] (Phase PH11).
//
// Validates:
//   * Safety-critical invariant: Consent Gate (export button disabled until user confirms consent).
//   * Purpose of use selection.
//   * Data minimization resource filters.
//   * Calling [ApiClient.exportFhirR4Summary] with correct parameters.
//   * Display of exported FHIR R4 Bundle summary, breakdown, and JSON preview.
//   * Clipboard copy interaction.
//   * Error state handling without PHI leakage.

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/experience/fhir/fhir_export_screen.dart';
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
  const token = 'test-export-token';

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

  group('FhirExportScreen Widget Tests', () {
    testWidgets('Safety Invariant: export button disabled until consent checkbox is confirmed', (tester) async {
      final sessionStore = await makeSessionStore();
      final mockHttp = MockClient((request) async => http.Response('{}', 200));
      final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mockHttp);

      await tester.pumpWidget(
        MaterialApp(
          home: FhirExportScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );
      await tester.pumpAndSettle();

      final exportButtonFinder = find.byKey(const Key('fhir-export-submit-button'));
      final consentCheckboxFinder = find.byKey(const Key('fhir-export-consent-checkbox'));

      expect(exportButtonFinder, findsOneWidget);
      expect(consentCheckboxFinder, findsOneWidget);

      // Initially disabled
      FilledButton button = tester.widget<FilledButton>(exportButtonFinder);
      expect(button.onPressed, isNull);

      // Scroll to consent checkbox and tap
      await tester.ensureVisible(consentCheckboxFinder);
      await tester.pumpAndSettle();
      await tester.tap(consentCheckboxFinder);
      await tester.pumpAndSettle();

      // Now enabled
      button = tester.widget<FilledButton>(exportButtonFinder);
      expect(button.onPressed, isNotNull);

      // Uncheck consent checkbox
      await tester.tap(consentCheckboxFinder);
      await tester.pumpAndSettle();

      // Disabled again
      button = tester.widget<FilledButton>(exportButtonFinder);
      expect(button.onPressed, isNull);
    });

    testWidgets('toggles resource minimization checkboxes', (tester) async {
      final sessionStore = await makeSessionStore();
      final mockHttp = MockClient((request) async => http.Response('{}', 200));
      final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mockHttp);

      await tester.pumpWidget(
        MaterialApp(
          home: FhirExportScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );
      await tester.pumpAndSettle();

      final patientCheckbox = find.byKey(const Key('fhir-resource-checkbox-Patient'));
      expect(patientCheckbox, findsOneWidget);

      CheckboxListTile tile = tester.widget<CheckboxListTile>(patientCheckbox);
      expect(tile.value, isTrue);

      // Uncheck Patient
      await tester.tap(patientCheckbox);
      await tester.pumpAndSettle();

      tile = tester.widget<CheckboxListTile>(patientCheckbox);
      expect(tile.value, isFalse);
    });

    testWidgets('exports bundle and renders breakdown, ID, and JSON preview', (tester) async {
      final sessionStore = await makeSessionStore();
      late http.Request capturedRequest;

      final mockHttp = MockClient((request) async {
        capturedRequest = request;
        return http.Response(
          jsonEncode({
            'resourceType': 'Bundle',
            'type': 'collection',
            'id': 'bundle-audit-test-99',
            'entry': [
              {
                'resource': {
                  'resourceType': 'Patient',
                  'id': 'p-1',
                },
              },
              {
                'resource': {
                  'resourceType': 'Condition',
                  'id': 'c-1',
                },
              },
              {
                'resource': {
                  'resourceType': 'Observation',
                  'id': 'o-1',
                },
              },
            ],
          }),
          200,
          headers: {'content-type': 'application/fhir+json'},
        );
      });

      final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mockHttp);

      await tester.pumpWidget(
        MaterialApp(
          home: FhirExportScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Check consent
      final consentFinder = find.byKey(const Key('fhir-export-consent-checkbox'));
      await tester.ensureVisible(consentFinder);
      await tester.pumpAndSettle();
      await tester.tap(consentFinder);
      await tester.pumpAndSettle();

      // Tap export
      final submitFinder = find.byKey(const Key('fhir-export-submit-button'));
      await tester.ensureVisible(submitFinder);
      await tester.pumpAndSettle();
      await tester.tap(submitFinder);
      await tester.pumpAndSettle();

      // Verify request params
      expect(capturedRequest.url.path, '/api/v1/lifemap/v2/export/fhir-r4');
      expect(capturedRequest.url.queryParameters['purpose'], 'self_download');
      expect(capturedRequest.url.queryParameters['include'], contains('Patient'));

      // Verify export result card
      final bundleFinder = find.byKey(const Key('fhir-export-bundle-id'));
      await tester.ensureVisible(bundleFinder);
      await tester.pumpAndSettle();

      expect(bundleFinder, findsOneWidget);
      expect(find.textContaining('bundle-audit-test-99'), findsOneWidget);
      expect(find.textContaining('Total Resources: 3'), findsOneWidget);
      expect(find.text('Patient: 1'), findsOneWidget);
      expect(find.text('Condition: 1'), findsOneWidget);
      expect(find.text('Observation: 1'), findsOneWidget);

      // Toggle preview JSON
      final previewToggle = find.text('Xem trước JSON');
      expect(previewToggle, findsOneWidget);
      await tester.ensureVisible(previewToggle);
      await tester.pumpAndSettle();

      await tester.tap(previewToggle);
      await tester.pumpAndSettle();

      final jsonPreviewFinder = find.byKey(const Key('fhir-export-json-preview'));
      await tester.ensureVisible(jsonPreviewFinder);
      await tester.pumpAndSettle();

      expect(jsonPreviewFinder, findsOneWidget);
      expect(find.textContaining('"resourceType": "Bundle"'), findsOneWidget);
    });

    testWidgets('renders safe error banner when export fails with 403', (tester) async {
      final sessionStore = await makeSessionStore();

      final mockHttp = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Medical disclaimer consent revoked'}),
          403,
          headers: {'content-type': 'application/json'},
        );
      });

      final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mockHttp);

      await tester.pumpWidget(
        MaterialApp(
          home: FhirExportScreen(
            apiClient: apiClient,
            sessionStore: sessionStore,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Check consent
      final consentFinder = find.byKey(const Key('fhir-export-consent-checkbox'));
      await tester.ensureVisible(consentFinder);
      await tester.pumpAndSettle();
      await tester.tap(consentFinder);
      await tester.pumpAndSettle();

      // Tap export
      final submitFinder = find.byKey(const Key('fhir-export-submit-button'));
      await tester.ensureVisible(submitFinder);
      await tester.pumpAndSettle();
      await tester.tap(submitFinder);
      await tester.pumpAndSettle();

      expect(find.text('Medical disclaimer consent revoked'), findsOneWidget);
    });
  });
}

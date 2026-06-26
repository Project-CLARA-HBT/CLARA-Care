// Feature: clara-selfmed-careguard-upgrade — Task 9.1 (Req 8.1, 8.2, 8.5).
//
// One targeted widget test for the mobile cabinet CRUD screen. It exercises the
// full happy path through the load-bearing invariants:
//   * Consent gate first (Req 8.5): the disclaimer blocks the cabinet until the
//     caller accepts the required version via POST /auth/consent.
//   * Cabinet listing against the same API as web (Req 8.2): items returned by
//     GET /careguard/cabinet are rendered.
//   * Two-medicine guard (Req 8.1): the distinct-medicine count is surfaced and
//     the interaction-check button is enabled only with >= 2 distinct medicines.
//
// A `MockClient` (package:http/testing) backs a real [ApiClient] so the screen
// drives genuine request/response plumbing without a live server or platform
// channels.

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/screens/careguard_cabinet_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

class InMemorySessionSecureStorage implements SessionSecureStorage {
  final Map<String, String> _data = {};

  @override
  Future<String?> read(String key) async => _data[key];

  @override
  Future<void> write(String key, String value) async => _data[key] = value;

  @override
  Future<void> delete(String key) async => _data.remove(key);
}

void main() {
  Future<PersistentSessionStore> buildSession() async {
    final store = PersistentSessionStore(storage: InMemorySessionSecureStorage());
    await store.setSession(
      email: 'user@example.com',
      accessToken: 'test-token',
      refreshToken: 'refresh',
      role: 'normal',
    );
    return store;
  }

  testWidgets(
      'consent gate unlocks cabinet CRUD listing with the two-medicine guard',
      (tester) async {
    var consentAccepted = false;
    var postedConsent = false;

    final mock = MockClient((request) async {
      final path = request.url.path;
      if (path.endsWith('/auth/consent-status') && request.method == 'GET') {
        return http.Response(
          jsonEncode({
            'consent_type': 'medical_disclaimer',
            'required_version': '2026-04-v1',
            'accepted': consentAccepted,
            'user_id': 1,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      }
      if (path.endsWith('/auth/consent') && request.method == 'POST') {
        postedConsent = true;
        consentAccepted = true;
        return http.Response(
          jsonEncode({
            'consent_type': 'medical_disclaimer',
            'user_id': 1,
            'consent_version': '2026-04-v1',
            'accepted_at': '2026-04-01T00:00:00Z',
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      }
      if (path.endsWith('/careguard/cabinet') && request.method == 'GET') {
        return http.Response(
          jsonEncode({
            'cabinet_id': 1,
            'label': 'Tủ thuốc',
            'items': [
              {
                'id': 1,
                'drug_name': 'Warfarin',
                'normalized_name': 'warfarin',
                'dosage': '5mg',
                'dosage_form': 'viên',
                'quantity': 30,
                'source': 'manual',
                'rx_cui': '',
                'expires_on': null,
                'note': '',
                'created_at': '2026-01-01T00:00:00Z',
                'updated_at': '2026-01-01T00:00:00Z',
              },
              {
                'id': 2,
                'drug_name': 'Ibuprofen',
                'normalized_name': 'ibuprofen',
                'dosage': '',
                'dosage_form': '',
                'quantity': 0,
                'source': 'manual',
                'rx_cui': '',
                'expires_on': null,
                'note': '',
                'created_at': '2026-01-01T00:00:00Z',
                'updated_at': '2026-01-01T00:00:00Z',
              },
            ],
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      }
      return http.Response('{"detail":"unexpected"}', 404,
          headers: {'content-type': 'application/json'});
    });

    final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mock);
    final session = await buildSession();

    await tester.pumpWidget(MaterialApp(
      home: CareguardCabinetScreen(apiClient: apiClient, sessionStore: session),
    ));
    await tester.pumpAndSettle();

    // Consent gate is shown first; the cabinet is not yet visible (Req 8.5).
    expect(find.text('Tuyên bố miễn trừ trách nhiệm y tế'), findsOneWidget);
    expect(find.text('Warfarin'), findsNothing);

    // Accept consent: tick the checkbox, then confirm.
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Đồng ý và tiếp tục'));
    await tester.pumpAndSettle();

    expect(postedConsent, isTrue);

    // Cabinet items render (Req 8.2) and the distinct-medicine count surfaces.
    expect(find.text('Warfarin'), findsOneWidget);
    expect(find.text('Ibuprofen'), findsOneWidget);
    expect(find.textContaining('Hiện có 2 thuốc'), findsOneWidget);

    // Two-medicine guard satisfied -> the interaction-check button is enabled.
    final button = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Kiểm tra tương tác'),
    );
    expect(button.onPressed, isNotNull);
  });
}

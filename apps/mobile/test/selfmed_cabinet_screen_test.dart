// Feature: clara-mobile-feature-parity — Task 5.2 (Req 3.1, 3.2, 3.5).
//
// Widget tests for the self-med cabinet screen covering the load-bearing
// behaviour behind the gates:
//   * Flag gate (Req 15.1): with `selfmed_cabinet_mobile_enabled` off the
//     screen is inert (placeholder, no consent/cabinet calls).
//   * Consent gate first (Req 3.5): the medical disclaimer blocks the cabinet
//     until the caller accepts the required version via POST /auth/consent.
//   * List (Req 3.1): items from GET /careguard/cabinet render with source +
//     key fields; add (POST) and delete (DELETE) hit CLARA_API (Req 3.2).
//
// A `MockClient` (package:http/testing) backs a real [ApiClient] so the screen
// drives genuine request/response plumbing without a live server or platform
// channels.

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:clara_mobile/core/feature_flags.dart';
import 'package:clara_mobile/core/session_store.dart';
import 'package:clara_mobile/screens/selfmed_cabinet_screen.dart';
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

MobileFeatureFlagResolver _resolver({required bool enabled}) {
  return MobileFeatureFlagResolver(
    summary: <String, dynamic>{
      'feature_flags': <String, dynamic>{
        MobileFeatureFlags.selfmedCabinetMobileEnabled: enabled,
      },
    },
  );
}

void main() {
  Future<PersistentSessionStore> buildSession() async {
    final store =
        PersistentSessionStore(storage: InMemorySessionSecureStorage());
    await store.setSession(
      email: 'user@example.com',
      accessToken: 'test-token',
      refreshToken: 'refresh',
      role: 'normal',
    );
    return store;
  }

  http.Response _json(Object body, [int status = 200]) => http.Response(
        jsonEncode(body),
        status,
        headers: {'content-type': 'application/json'},
      );

  testWidgets('flag off renders an inert placeholder and makes no calls',
      (tester) async {
    var calls = 0;
    final mock = MockClient((request) async {
      calls++;
      return _json({'detail': 'unexpected'}, 404);
    });
    final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mock);
    final session = await buildSession();

    await tester.pumpWidget(MaterialApp(
      home: SelfMedCabinetScreen(
        apiClient: apiClient,
        sessionStore: session,
        featureFlags: _resolver(enabled: false),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Tính năng tủ thuốc chưa được bật.'), findsOneWidget);
    expect(find.text('Tuyên bố miễn trừ trách nhiệm y tế'), findsNothing);
    expect(calls, 0);
  });

  testWidgets(
      'consent gate unlocks list, then add and delete hit CLARA_API',
      (tester) async {
    var consentAccepted = false;
    var postedConsent = false;
    var postedItem = false;
    var deletedItem = false;
    // Cabinet items returned by GET, mutated by the add/delete handlers.
    final items = <Map<String, dynamic>>[
      {
        'id': 1,
        'drug_name': 'Warfarin',
        'normalized_name': 'warfarin',
        'dosage': '5mg',
        'dosage_form': 'viên',
        'quantity': 30,
        'source': 'manual',
        'expires_on': '2026-12-31',
      },
    ];

    final mock = MockClient((request) async {
      final path = request.url.path;
      final method = request.method;
      if (path.endsWith('/auth/consent-status') && method == 'GET') {
        return _json({
          'required_version': '2026-04-v1',
          'accepted': consentAccepted,
        });
      }
      if (path.endsWith('/auth/consent') && method == 'POST') {
        postedConsent = true;
        consentAccepted = true;
        return _json({'accepted_at': '2026-04-01T00:00:00Z'});
      }
      if (path.endsWith('/careguard/cabinet') && method == 'GET') {
        return _json({'cabinet_id': 1, 'items': items});
      }
      if (path.endsWith('/careguard/cabinet/items') && method == 'POST') {
        postedItem = true;
        items.add({
          'id': 2,
          'drug_name': 'Ibuprofen',
          'normalized_name': 'ibuprofen',
          'source': 'manual',
          'quantity': 10,
        });
        return _json({'id': 2});
      }
      if (path.contains('/careguard/cabinet/items/') && method == 'DELETE') {
        deletedItem = true;
        items.removeWhere((it) => path.endsWith('/${it['id']}'));
        return _json({'deleted': true});
      }
      return _json({'detail': 'unexpected'}, 404);
    });

    final apiClient = ApiClient(baseUrl: 'https://api.test', httpClient: mock);
    final session = await buildSession();

    await tester.pumpWidget(MaterialApp(
      home: SelfMedCabinetScreen(
        apiClient: apiClient,
        sessionStore: session,
        featureFlags: _resolver(enabled: true),
      ),
    ));
    await tester.pumpAndSettle();

    // Consent gate is shown first; the cabinet is not yet visible (Req 3.5).
    expect(find.text('Tuyên bố miễn trừ trách nhiệm y tế'), findsOneWidget);
    expect(find.text('Warfarin'), findsNothing);

    // Accept consent.
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Đồng ý và tiếp tục'));
    await tester.pumpAndSettle();
    expect(postedConsent, isTrue);

    // List renders item + provenance label (Req 3.1).
    expect(find.text('Warfarin'), findsOneWidget);
    expect(find.textContaining('Nhập thủ công'), findsWidgets);
    expect(find.textContaining('HSD: 2026-12-31'), findsOneWidget);

    // Add an item (Req 3.2).
    await tester.tap(find.widgetWithText(FloatingActionButton, 'Thêm thuốc'));
    await tester.pumpAndSettle();
    await tester.enterText(
        find.widgetWithText(TextField, 'Tên thuốc *'), 'Ibuprofen');
    await tester.tap(find.widgetWithText(FilledButton, 'Thêm'));
    await tester.pumpAndSettle();
    expect(postedItem, isTrue);
    expect(find.text('Ibuprofen'), findsOneWidget);

    // Delete the first item (Req 3.2).
    await tester.tap(find.byTooltip('Xóa').first);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Xóa'));
    await tester.pumpAndSettle();
    expect(deletedItem, isTrue);
    expect(find.text('Warfarin'), findsNothing);
  });
}

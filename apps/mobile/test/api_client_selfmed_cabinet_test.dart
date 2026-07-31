// Unit tests for the additive self-med cabinet client methods added to
// [ApiClient] in task 5.1 of the clara-mobile-feature-parity spec.
//
// The web "self-med" surface (`apps/web/lib/selfmed.ts`) is backed by the
// shared `/careguard/cabinet*` endpoints — CLARA_API exposes NO `/selfmed/*`
// routes — so the mobile `getCabinet` / `addCabinetItem` / `deleteCabinetItem`
// are thin selfmed-named aliases over the existing careguard cabinet methods.
// These tests pin the actual server contract (method/path/headers/body) that
// each alias drives, using a `MockClient`-backed real [ApiClient] so no live
// server or platform channels are required (Req 3.1, 3.2, 14.6, 15.5).

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

void main() {
  const token = 'test-token';
  const base = 'https://api.test';

  group('getCabinet', () {
    test('GETs /api/v1/careguard/cabinet and returns the envelope', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'cabinet_id': 7,
            'label': 'Tủ thuốc của tôi',
            'items': [
              {
                'id': 1,
                'drug_name': 'paracetamol',
                'source': 'manual',
                'quantity': 10,
              },
            ],
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.getCabinet(accessToken: token);

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/v1/careguard/cabinet');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(result['cabinet_id'], 7);
      expect((result['items'] as List), hasLength(1));
      expect((result['items'] as List).first['drug_name'], 'paracetamol');
    });

    test('surfaces server error detail as ApiException', () async {
      final mock = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'unauthorized'}),
          401,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      expect(
        () => api.getCabinet(accessToken: token),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 401)
              .having((e) => e.message, 'message', 'unauthorized'),
        ),
      );
    });
  });

  group('addCabinetItem', () {
    test('POSTs payload to /api/v1/careguard/cabinet/items', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'id': 42,
            'drug_name': 'ibuprofen',
            'source': 'manual',
            'quantity': 5,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.addCabinetItem(
        accessToken: token,
        payload: {'drug_name': 'ibuprofen', 'quantity': 5},
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/careguard/cabinet/items');
      expect(captured.headers['Authorization'], 'Bearer $token');
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['drug_name'], 'ibuprofen');
      expect(body['quantity'], 5);
      expect(result['id'], 42);
      expect(result['drug_name'], 'ibuprofen');
    });

    test('surfaces a duplicate-name 409 as ApiException', () async {
      final mock = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Thuốc này đã có trong tủ thuốc.'}),
          409,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      expect(
        () => api.addCabinetItem(
          accessToken: token,
          payload: {'drug_name': 'paracetamol'},
        ),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 409)
              .having((e) => e.message, 'message',
                  'Thuốc này đã có trong tủ thuốc.'),
        ),
      );
    });
  });

  group('deleteCabinetItem', () {
    test('DELETEs /api/v1/careguard/cabinet/items/{itemId}', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({'deleted': true}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      final result = await api.deleteCabinetItem(
        accessToken: token,
        itemId: 99,
      );

      expect(captured.method, 'DELETE');
      expect(captured.url.path, '/api/v1/careguard/cabinet/items/99');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(result['deleted'], isTrue);
    });
  });

  group('autoCheckCareguardCabinet', () {
    test(
        'POSTs only source-backed selected resolutions to the cabinet endpoint',
        () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({'status': 'requires_medication_clarification'}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = ApiClient(baseUrl: base, httpClient: mock);

      await api.autoCheckCareguardCabinet(
        accessToken: token,
        locale: 'en',
        resolutions: const [
          {
            'cabinet_item_id': 7,
            'input_alias': 'panadol xanh',
            'drugbank_id': 'DB00316',
            'drugbank_version': 'drugbank-2026-07',
          },
        ],
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/careguard/cabinet/auto-ddi-check');
      expect(captured.headers['Authorization'], 'Bearer $token');
      final body = jsonDecode(captured.body) as Map<String, dynamic>;
      expect(body['locale'], 'en');
      expect(body['resolutions'], hasLength(1));
      expect((body['resolutions'] as List).single['drugbank_id'], 'DB00316');
      expect(body.containsKey('medications'), isFalse);
    });
  });
}

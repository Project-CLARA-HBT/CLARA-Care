// Unit tests for FHIR R4 interoperability and connector sync client methods
// on [ApiClient] (Phase PH11).
//
// Validates:
//   * Correct paths, HTTP methods, headers, and query parameters.
//   * Proper serialization and deserialization of FHIR R4 conformance and bundles.
//   * Accurate error translation into [ApiException] (401, 403, 404, 422).
//   * Correct propagation of X-CLARA-Profile-Context header.

import 'dart:convert';

import 'package:clara_mobile/core/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const token = 'test-bearer-token';
  const base = 'https://api.test';

  group('getFhirConformance', () {
    test('GETs /api/v1/lifemap/v2/fhir/conformance and returns statement', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'name': 'CLARA LifeMap FHIR R4 projection',
            'fhir_version': '4.0.1',
            'mapping_version': '1.0',
            'conformance': 'fhir-r4-summary-not-ips',
            'bundle_types': ['collection'],
            'operations': {
              'export': {
                'enabled': true,
                'path': '/api/v1/lifemap/v2/export/fhir-r4',
              },
              'import': {
                'enabled': false,
                'path': '/api/v1/lifemap/v2/import/fhir-r4',
              },
              'ips_export': {
                'enabled': false,
                'package_candidate': 'hl7.fhir.uv.ips#2.0.1',
              },
            },
            'general_fhir_server': false,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = ApiClient(baseUrl: base, httpClient: mock);
      final result = await api.getFhirConformance(accessToken: token);

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/v1/lifemap/v2/fhir/conformance');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(result['fhir_version'], '4.0.1');
      expect(result['conformance'], 'fhir-r4-summary-not-ips');
      expect(result['general_fhir_server'], isFalse);
    });

    test('surfaces 401 Unauthorized as ApiException', () async {
      final mock = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Invalid or expired credentials'}),
          401,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = ApiClient(baseUrl: base, httpClient: mock);
      expect(
        () => api.getFhirConformance(accessToken: 'invalid-token'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.statusCode,
            'statusCode',
            401,
          ),
        ),
      );
    });
  });

  group('exportFhirR4Summary', () {
    test('GETs /api/v1/lifemap/v2/export/fhir-r4 with purpose and include params', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'resourceType': 'Bundle',
            'type': 'collection',
            'id': 'bundle-uuid-1234',
            'entry': [
              {
                'resource': {
                  'resourceType': 'Patient',
                  'id': 'pat-1',
                },
              },
              {
                'resource': {
                  'resourceType': 'Condition',
                  'id': 'cond-1',
                },
              },
            ],
          }),
          200,
          headers: {
            'content-type': 'application/fhir+json',
            'x-clara-conformance': 'fhir-r4-summary-not-ips',
          },
        );
      });

      final api = ApiClient(baseUrl: base, httpClient: mock);
      final result = await api.exportFhirR4Summary(
        accessToken: token,
        purpose: 'clinical_consult',
        include: 'Patient,Condition',
      );

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/v1/lifemap/v2/export/fhir-r4');
      expect(captured.url.queryParameters['purpose'], 'clinical_consult');
      expect(captured.url.queryParameters['include'], 'Patient,Condition');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(result['resourceType'], 'Bundle');
      expect(result['type'], 'collection');
      expect(result['id'], 'bundle-uuid-1234');
      expect((result['entry'] as List), hasLength(2));
    });

    test('propagates X-CLARA-Profile-Context header when profileContext is provided', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'resourceType': 'Bundle',
            'type': 'collection',
            'id': 'family-bundle-5678',
            'entry': [],
          }),
          200,
          headers: {'content-type': 'application/fhir+json'},
        );
      });

      final api = ApiClient(baseUrl: base, httpClient: mock);
      await api.exportFhirR4Summary(
        accessToken: token,
        profileContext: 'dependent-profile-42',
      );

      expect(
        captured.headers['X-CLARA-Profile-Context'],
        'dependent-profile-42',
      );
    });

    test('surfaces 403 Forbidden for missing or denied consent', () async {
      final mock = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Medical disclaimer consent required before export'}),
          403,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = ApiClient(baseUrl: base, httpClient: mock);
      expect(
        () => api.exportFhirR4Summary(accessToken: token),
        throwsA(
          isA<ApiException>().having((e) => e.statusCode, 'statusCode', 403),
        ),
      );
    });

    test('surfaces 422 Unprocessable Entity for schema validation error', () async {
      final mock = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'detail': {
              'code': 'fhir_validation_failed',
              'errors': ['Observation.valueQuantity unit invalid'],
            },
          }),
          422,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = ApiClient(baseUrl: base, httpClient: mock);
      expect(
        () => api.exportFhirR4Summary(accessToken: token),
        throwsA(
          isA<ApiException>().having((e) => e.statusCode, 'statusCode', 422),
        ),
      );
    });
  });

  group('syncConnector', () {
    test('POSTs /api/v1/connectors/{id}/sync with empty body and bearer token', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'status': 'queued',
            'connector_id': 'conn-99',
            'synced_at': '2026-10-24T12:00:00Z',
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = ApiClient(baseUrl: base, httpClient: mock);
      final result = await api.syncConnector(
        accessToken: token,
        connectorId: 'conn-99',
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/connectors/conn-99/sync');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(result['status'], 'queued');
    });

    test('surfaces 404 for unknown connector', () async {
      final mock = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Connector not found'}),
          404,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = ApiClient(baseUrl: base, httpClient: mock);
      expect(
        () => api.syncConnector(accessToken: token, connectorId: 'unknown-id'),
        throwsA(
          isA<ApiException>().having((e) => e.statusCode, 'statusCode', 404),
        ),
      );
    });
  });

  group('getConnectorStatusAdapter', () {
    test('GETs /api/v1/connectors/status-adapter', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'status': 'healthy',
            'total_connectors': 3,
            'active_connectors': 2,
            'paused_connectors': 1,
            'outbox_adapter_linked': true,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = ApiClient(baseUrl: base, httpClient: mock);
      final result = await api.getConnectorStatusAdapter(accessToken: token);

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/v1/connectors/status-adapter');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(result['status'], 'healthy');
      expect(result['total_connectors'], 3);
      expect(result['outbox_adapter_linked'], isTrue);
    });
  });

  group('exportPhrFhir', () {
    test('GETs /api/v1/phr/export with resource filter', () async {
      late http.Request captured;
      final mock = MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode({
            'resourceType': 'Bundle',
            'type': 'collection',
            'entry': [],
          }),
          200,
          headers: {'content-type': 'application/fhir+json'},
        );
      });

      final api = ApiClient(baseUrl: base, httpClient: mock);
      final result = await api.exportPhrFhir(
        accessToken: token,
        resource: 'condition',
      );

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/v1/phr/export');
      expect(captured.url.queryParameters['resource'], 'condition');
      expect(captured.headers['Authorization'], 'Bearer $token');
      expect(result['resourceType'], 'Bundle');
    });
  });
}

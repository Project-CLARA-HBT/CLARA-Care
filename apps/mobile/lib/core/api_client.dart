import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiException implements Exception {
  ApiException({required this.message, this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() {
    if (statusCode == null) {
      return message;
    }
    return 'HTTP $statusCode: $message';
  }
}

/// A single Server-Sent Event parsed from the SSE stream.
class SseEvent {
  const SseEvent({this.id, this.event, this.data});

  final String? id;
  final String? event;
  final String? data;

  /// Attempts to parse [data] as JSON. Returns null if data is null or invalid.
  Map<String, dynamic>? get json {
    if (data == null || data!.isEmpty) return null;
    try {
      final decoded = jsonDecode(data!);
      if (decoded is Map<String, dynamic>) return decoded;
      return null;
    } catch (_) {
      return null;
    }
  }
}

class LoginResponseData {
  const LoginResponseData({
    required this.accessToken,
    required this.refreshToken,
    required this.role,
    required this.tokenType,
  });

  final String accessToken;
  final String refreshToken;
  final String role;
  final String tokenType;

  factory LoginResponseData.fromJson(Map<String, dynamic> json) {
    return LoginResponseData(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String,
      role: (json['role'] as String?) ?? 'normal',
      tokenType: (json['token_type'] as String?) ?? 'bearer',
    );
  }
}

class ApiClient {
  ApiClient({
    required String baseUrl,
    http.Client? httpClient,
  })  : _baseUrl = _trimTrailingSlash(baseUrl),
        _httpClient = httpClient ?? http.Client();

  final String _baseUrl;
  final http.Client _httpClient;

  Future<LoginResponseData> login({
    required String email,
    required String password,
  }) async {
    final data = await _post(
      '/api/v1/auth/login',
      body: {
        'email': email,
        'password': password,
      },
    );

    return LoginResponseData.fromJson(data);
  }

  Future<Map<String, dynamic>> researchTier2({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/research/tier2',
      body: payload,
      accessToken: accessToken,
    );
  }

  /// Creates a tier2 research job (deep/deep_beta). Returns the full job
  /// response including `job_id` which can be used with [streamResearchJob].
  Future<Map<String, dynamic>> createResearchJob({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/research/tier2/jobs',
      body: payload,
      accessToken: accessToken,
    );
  }

  /// Opens an SSE stream for a running research job. Yields [SseEvent]
  /// instances as progress events arrive. The stream closes when the job
  /// reaches a terminal state (`completed` or `failed`) or the server
  /// disconnects.
  Stream<SseEvent> streamResearchJob({
    required String accessToken,
    required String jobId,
  }) async* {
    final uri = Uri.parse('$_baseUrl/api/v1/research/tier2/jobs/$jobId/stream');
    final request = http.Request('GET', uri);
    request.headers.addAll({
      'Accept': 'text/event-stream',
      'Cache-Control': 'no-cache',
      if (accessToken.isNotEmpty) 'Authorization': 'Bearer $accessToken',
    });

    final http.StreamedResponse response;
    try {
      response = await _httpClient.send(request);
    } catch (e) {
      throw ApiException(message: 'Không thể kết nối tới server.');
    }

    if (response.statusCode >= 400) {
      final body = await response.stream.bytesToString();
      String message = 'Request failed';
      try {
        final decoded = jsonDecode(body);
        if (decoded is Map<String, dynamic>) {
          message = decoded['detail']?.toString() ?? message;
        }
      } catch (_) {}
      throw ApiException(statusCode: response.statusCode, message: message);
    }

    // Parse SSE protocol: lines prefixed with "id:", "event:", "data:", or
    // comments ":". Events are separated by blank lines.
    String? currentId;
    String? currentEvent;
    final dataBuffer = StringBuffer();

    await for (final chunk in response.stream.transform(utf8.decoder).transform(const LineSplitter())) {
      if (chunk.isEmpty) {
        // Blank line = end of event.
        if (dataBuffer.isNotEmpty || currentEvent != null) {
          yield SseEvent(
            id: currentId,
            event: currentEvent,
            data: dataBuffer.toString(),
          );
        }
        currentId = null;
        currentEvent = null;
        dataBuffer.clear();
        continue;
      }

      if (chunk.startsWith(':')) {
        // Comment / keepalive — ignore.
        continue;
      }

      if (chunk.startsWith('id: ') || chunk.startsWith('id:')) {
        currentId = chunk.substring(chunk.indexOf(':') + 1).trimLeft();
      } else if (chunk.startsWith('event: ') || chunk.startsWith('event:')) {
        currentEvent = chunk.substring(chunk.indexOf(':') + 1).trimLeft();
      } else if (chunk.startsWith('data: ') || chunk.startsWith('data:')) {
        if (dataBuffer.isNotEmpty) {
          dataBuffer.write('\n');
        }
        dataBuffer.write(chunk.substring(chunk.indexOf(':') + 1).trimLeft());
      }
    }

    // Flush any trailing event that wasn't terminated with a blank line.
    if (dataBuffer.isNotEmpty || currentEvent != null) {
      yield SseEvent(
        id: currentId,
        event: currentEvent,
        data: dataBuffer.toString(),
      );
    }
  }

  Future<Map<String, dynamic>> analyzeCareguard({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/careguard/analyze',
      body: payload,
      accessToken: accessToken,
    );
  }

  /// Loads the owner's medicine cabinet (CareGuard_Mobile cabinet parity,
  /// clara-selfmed-careguard-upgrade Requirement 8.2). Same contract as the web
  /// client: `GET /api/v1/careguard/cabinet`.
  Future<Map<String, dynamic>> getCareguardCabinet({
    required String accessToken,
  }) {
    return _get(
      '/api/v1/careguard/cabinet',
      accessToken: accessToken,
    );
  }

  /// Creates a cabinet item (Requirement 8.2). `POST /api/v1/careguard/cabinet/items`.
  /// A duplicate normalized name is rejected server-side (409) and surfaces as
  /// an [ApiException] with the Vietnamese message.
  Future<Map<String, dynamic>> addCareguardCabinetItem({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/careguard/cabinet/items',
      body: payload,
      accessToken: accessToken,
    );
  }

  /// Updates a cabinet item (Requirement 8.2).
  /// `PATCH /api/v1/careguard/cabinet/items/{itemId}`.
  Future<Map<String, dynamic>> updateCareguardCabinetItem({
    required String accessToken,
    required int itemId,
    required Map<String, dynamic> payload,
  }) {
    return _patch(
      '/api/v1/careguard/cabinet/items/$itemId',
      body: payload,
      accessToken: accessToken,
    );
  }

  /// Deletes a cabinet item scoped to the owner (Requirement 8.2, 1.6).
  /// `DELETE /api/v1/careguard/cabinet/items/{itemId}`.
  Future<Map<String, dynamic>> deleteCareguardCabinetItem({
    required String accessToken,
    required int itemId,
  }) {
    return _delete(
      '/api/v1/careguard/cabinet/items/$itemId',
      accessToken: accessToken,
    );
  }

  /// Reads the caller's medical-disclaimer consent status (same gate as the web
  /// client, Requirement 8.5). `GET /api/v1/auth/consent-status`.
  Future<Map<String, dynamic>> getConsentStatus({
    required String accessToken,
  }) {
    return _get(
      '/api/v1/auth/consent-status',
      accessToken: accessToken,
    );
  }

  /// Records acceptance of the medical-disclaimer consent at [consentVersion]
  /// (Requirement 8.5). `POST /api/v1/auth/consent`.
  Future<Map<String, dynamic>> acceptConsent({
    required String accessToken,
    required String consentVersion,
  }) {
    return _post(
      '/api/v1/auth/consent',
      body: {'consent_version': consentVersion, 'accepted': true},
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> runCouncil({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/council/run',
      body: payload,
      accessToken: accessToken,
    );
  }

  // ---------------------------------------------------------------------------
  // Council case lifecycle (clara-council-upgrade Requirement 8.1, 8.2).
  //
  // These methods reuse the existing Council_API endpoints so the mobile parity
  // surfaces drive the same case create -> intake -> specialists -> run -> result
  // flow as the web wizard, with no mobile-only result shape (Requirement 8.2).
  // The case-scoped result envelope is the shared `run_council` shape, so the
  // mobile screens render consensus/divergence/final from the same keys.
  // ---------------------------------------------------------------------------

  /// Lists the owner's Council cases, newest-first, with owner isolation enforced
  /// server-side. `GET /api/v1/council/cases`. Returns the
  /// `{ items: [...], total: int }` envelope.
  Future<Map<String, dynamic>> listCouncilCases({
    required String accessToken,
    int limit = 20,
    int offset = 0,
  }) {
    return _get(
      '/api/v1/council/cases?limit=$limit&offset=$offset',
      accessToken: accessToken,
    );
  }

  /// Loads the owner's most-recent Council case. `GET /api/v1/council/cases/latest`.
  /// Throws an [ApiException] (404) when the owner has no cases yet.
  Future<Map<String, dynamic>> getLatestCouncilCase({
    required String accessToken,
  }) {
    return _get(
      '/api/v1/council/cases/latest',
      accessToken: accessToken,
    );
  }

  /// Creates a new Council case (Requirement 8.1). `POST /api/v1/council/cases`.
  /// [payload] mirrors the server `CouncilCaseCreateRequest`
  /// (`title`, `intake_mode`, `transcript`, optional `request`). Returns the
  /// persisted case envelope.
  Future<Map<String, dynamic>> createCouncilCase({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/council/cases',
      body: payload,
      accessToken: accessToken,
    );
  }

  /// Loads a single owned Council case, including its latest `result`
  /// (Requirement 8.1). `GET /api/v1/council/cases/{caseId}`.
  Future<Map<String, dynamic>> getCouncilCase({
    required String accessToken,
    required int caseId,
  }) {
    return _get(
      '/api/v1/council/cases/$caseId',
      accessToken: accessToken,
    );
  }

  /// Updates an owned Council case (Requirement 8.1). `PATCH /api/v1/council/cases/{caseId}`.
  /// Used to persist the specialist selection (and other intake/request edits)
  /// onto the case's `request` payload before a run. [payload] mirrors the
  /// server `CouncilCaseUpdateRequest`; e.g. `{ "request": { "specialists": [...],
  /// "specialist_count": 3 } }`.
  Future<Map<String, dynamic>> updateCouncilCase({
    required String accessToken,
    required int caseId,
    required Map<String, dynamic> payload,
  }) {
    return _patch(
      '/api/v1/council/cases/$caseId',
      body: payload,
      accessToken: accessToken,
    );
  }

  /// Runs intake extraction for an owned case (Requirement 8.1).
  /// `POST /api/v1/council/cases/{caseId}/intake` (multipart form). Provide a
  /// [transcript] and/or an audio upload via [audioBytes]; the server preserves
  /// the existing 15MB size and content-type allow-list limits and labels a
  /// degraded heuristic extraction. Returns the updated case envelope with the
  /// extracted `intake` and normalized `request`.
  Future<Map<String, dynamic>> submitCouncilCaseIntake({
    required String accessToken,
    required int caseId,
    String transcript = '',
    List<int>? audioBytes,
    String? audioFilename,
  }) {
    return _postMultipart(
      '/api/v1/council/cases/$caseId/intake',
      accessToken: accessToken,
      fields: {'transcript': transcript},
      fileField: 'audio_file',
      fileBytes: audioBytes,
      filename: audioFilename ?? 'audio-input',
    );
  }

  /// Runs the Council for an owned case (Requirement 8.1).
  /// `POST /api/v1/council/cases/{caseId}/run`. Optionally override the stored
  /// [request] payload, the [specialistCount] (clamped 2..5 server-side), or the
  /// explicit [specialists] selection. Returns the case envelope whose `result`
  /// is the shared `run_council` shape (consensus, conflicts, final
  /// recommendation, clinician directive).
  Future<Map<String, dynamic>> runCouncilCase({
    required String accessToken,
    required int caseId,
    Map<String, dynamic>? request,
    int? specialistCount,
    List<String>? specialists,
  }) {
    final body = <String, dynamic>{};
    if (request != null) {
      body['request'] = request;
    }
    if (specialistCount != null) {
      body['specialist_count'] = specialistCount;
    }
    if (specialists != null) {
      body['specialists'] = specialists;
    }
    return _post(
      '/api/v1/council/cases/$caseId/run',
      body: body,
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> getSystemMetrics({
    required String accessToken,
  }) {
    return _get(
      '/api/v1/system/metrics',
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> getMobileSummary({
    required String accessToken,
  }) {
    return _get(
      '/api/v1/mobile/summary',
      accessToken: accessToken,
    );
  }

  /// Loads the owner's Personal Health Record (profile + allergies, conditions,
  /// medications). Backs the mobile PHR screen (personal-health-record
  /// Requirement 17.1). Uses the legacy `GET /record` contract so behavior is
  /// identical regardless of enhanced flag state (Requirement 18.1).
  Future<Map<String, dynamic>> getPhrRecord({
    required String accessToken,
  }) {
    return _get(
      '/api/v1/phr/record',
      accessToken: accessToken,
    );
  }

  /// Persists the owner's full PHR profile via the server-validated
  /// `PUT /record` contract (personal-health-record Requirement 17.2). The
  /// server enforces field length/range and severity/status domains; validation
  /// failures surface as an [ApiException].
  Future<Map<String, dynamic>> updatePhrRecord({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _put(
      '/api/v1/phr/record',
      body: payload,
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> _post(
    String path, {
    required Map<String, dynamic> body,
    String? accessToken,
  }) async {
    final response = await _httpClient.post(
      Uri.parse('$_baseUrl$path'),
      headers: _headers(accessToken: accessToken),
      body: jsonEncode(body),
    );

    return _decodeResponse(response);
  }

  /// Sends a `multipart/form-data` POST, mirroring the Council intake endpoint's
  /// `Form`/`UploadFile` contract. [fields] are string form fields; an optional
  /// file part is attached when [fileBytes] is non-null. The `Content-Type`
  /// boundary header is managed by [http.MultipartRequest].
  Future<Map<String, dynamic>> _postMultipart(
    String path, {
    required Map<String, String> fields,
    String? accessToken,
    String? fileField,
    List<int>? fileBytes,
    String? filename,
  }) async {
    final request = http.MultipartRequest('POST', Uri.parse('$_baseUrl$path'));
    request.headers['Accept'] = 'application/json';
    if (accessToken != null && accessToken.isNotEmpty) {
      request.headers['Authorization'] = 'Bearer $accessToken';
    }
    request.fields.addAll(fields);
    if (fileField != null && fileBytes != null) {
      request.files.add(
        http.MultipartFile.fromBytes(
          fileField,
          fileBytes,
          filename: filename ?? 'upload',
        ),
      );
    }

    final http.Response response;
    try {
      final streamed = await _httpClient.send(request);
      response = await http.Response.fromStream(streamed);
    } catch (_) {
      throw ApiException(message: 'Không thể kết nối tới server.');
    }

    return _decodeResponse(response);
  }

  Future<Map<String, dynamic>> _put(
    String path, {
    required Map<String, dynamic> body,
    String? accessToken,
  }) async {
    final response = await _httpClient.put(
      Uri.parse('$_baseUrl$path'),
      headers: _headers(accessToken: accessToken),
      body: jsonEncode(body),
    );

    return _decodeResponse(response);
  }

  Future<Map<String, dynamic>> _patch(
    String path, {
    required Map<String, dynamic> body,
    String? accessToken,
  }) async {
    final response = await _httpClient.patch(
      Uri.parse('$_baseUrl$path'),
      headers: _headers(accessToken: accessToken),
      body: jsonEncode(body),
    );

    return _decodeResponse(response);
  }

  Future<Map<String, dynamic>> _delete(
    String path, {
    String? accessToken,
  }) async {
    final response = await _httpClient.delete(
      Uri.parse('$_baseUrl$path'),
      headers: _headers(accessToken: accessToken),
    );

    return _decodeResponse(response);
  }

  Future<Map<String, dynamic>> _get(
    String path, {
    String? accessToken,
  }) async {
    final response = await _httpClient.get(
      Uri.parse('$_baseUrl$path'),
      headers: _headers(accessToken: accessToken),
    );

    return _decodeResponse(response);
  }

  Map<String, String> _headers({String? accessToken}) {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };

    if (accessToken != null && accessToken.isNotEmpty) {
      headers['Authorization'] = 'Bearer $accessToken';
    }

    return headers;
  }

  Map<String, dynamic> _decodeResponse(http.Response response) {
    Map<String, dynamic> payload = <String, dynamic>{};

    if (response.body.isNotEmpty) {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) {
        payload = decoded;
      } else {
        payload = <String, dynamic>{'data': decoded};
      }
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = payload['detail']?.toString();
      throw ApiException(
        statusCode: response.statusCode,
        message: detail ?? 'Request failed',
      );
    }

    return payload;
  }

  static String _trimTrailingSlash(String value) {
    if (value.endsWith('/')) {
      return value.substring(0, value.length - 1);
    }
    return value;
  }
}

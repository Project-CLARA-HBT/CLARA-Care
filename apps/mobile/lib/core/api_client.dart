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

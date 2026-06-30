// Reusable test fake for the CLARA mobile feature-parity spec (task 1.1).
//
// A fake [ApiClient] that screens can be constructed with directly (the
// production screens accept an `ApiClient`), so widget tests run without a live
// server or platform channels. Unlike the `MockClient`-backed approach (which
// is great for asserting wire-level request shapes), this fake operates at the
// method level: you stub each `ApiClient` method by name with a canned response
// or error, and every call is recorded for assertions.
//
// Design tie-ins:
//   * Requirement 14.6 — tests run under `flutter test` with no live network.
//   * It NEVER performs real network I/O: the super `http.Client` throws if any
//     un-stubbed path reaches the wire, surfacing missing stubs loudly.
//
// Use `MockClient` directly when a test needs to assert on the HTTP request
// (method/path/headers/body); use [FakeApiClient] when a test only needs to
// inject responses and observe which client methods a screen invoked.

import 'dart:async';

import 'package:clara_mobile/core/api_client.dart';
import 'package:http/http.dart' as http;

/// A single recorded call to a [FakeApiClient] method.
class FakeApiInvocation {
  FakeApiInvocation(this.method, this.args, {this.accessToken});

  /// The `ApiClient` method name, e.g. `getMobileSummary`.
  final String method;

  /// The named arguments passed to the method (excluding `accessToken`).
  final Map<String, Object?> args;

  /// The access token passed to the method, if any.
  final String? accessToken;

  @override
  String toString() => 'FakeApiInvocation($method, args: $args)';
}

/// Responder signature for a stubbed JSON-returning method.
typedef FakeApiResponder = FutureOr<Map<String, dynamic>> Function(
  FakeApiInvocation invocation,
);

/// Responder signature for the SSE-returning [ApiClient.streamResearchJob].
typedef FakeSseResponder = Stream<SseEvent> Function(
  FakeApiInvocation invocation,
);

/// An `http.Client` that refuses to perform real I/O. Any request reaching it
/// means a [FakeApiClient] method was called without being stubbed.
class _UnusableHttpClient extends http.BaseClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    throw StateError(
      'FakeApiClient attempted real network I/O '
      '(${request.method} ${request.url}). Stub the corresponding ApiClient '
      'method instead.',
    );
  }
}

/// Method-level fake of [ApiClient]. Extends the real client so it is a drop-in
/// substitute wherever an `ApiClient` is required.
class FakeApiClient extends ApiClient {
  FakeApiClient({String baseUrl = 'https://fake.clara.test'})
      : super(baseUrl: baseUrl, httpClient: _UnusableHttpClient());

  /// Every call made to this fake, in order.
  final List<FakeApiInvocation> invocations = <FakeApiInvocation>[];

  final Map<String, FakeApiResponder> _responders = <String, FakeApiResponder>{};

  /// Fallback responder used when a called method has no specific stub.
  FakeApiResponder? defaultResponder;

  /// Responder for [streamResearchJob] (SSE). Set via [stubStream].
  FakeSseResponder? _sseResponder;

  // --- Stub configuration ----------------------------------------------------

  /// Stubs [method] (an `ApiClient` method name). Provide exactly one of:
  ///   * [response] — a fixed JSON map to return,
  ///   * [error] — an object to throw (e.g. an [ApiException]),
  ///   * [responder] — a function computing the result from the invocation.
  void stub(
    String method, {
    Map<String, dynamic>? response,
    Object? error,
    FakeApiResponder? responder,
  }) {
    assert(
      [response, error, responder].where((v) => v != null).length == 1,
      'stub() requires exactly one of response, error, or responder',
    );
    if (responder != null) {
      _responders[method] = responder;
    } else if (error != null) {
      _responders[method] = (_) => throw error;
    } else {
      _responders[method] = (_) => response!;
    }
  }

  /// Stubs [streamResearchJob]. Provide exactly one of [events] (emitted in
  /// order then closed), [error] (thrown on subscription), or [responder].
  void stubStream({
    List<SseEvent>? events,
    Object? error,
    FakeSseResponder? responder,
  }) {
    assert(
      [events, error, responder].where((v) => v != null).length == 1,
      'stubStream() requires exactly one of events, error, or responder',
    );
    if (responder != null) {
      _sseResponder = responder;
    } else if (error != null) {
      _sseResponder = (_) => Stream<SseEvent>.error(error);
    } else {
      _sseResponder = (_) => Stream<SseEvent>.fromIterable(events!);
    }
  }

  // --- Assertion helpers -----------------------------------------------------

  /// All recorded calls to [method], in order.
  List<FakeApiInvocation> callsTo(String method) =>
      invocations.where((i) => i.method == method).toList(growable: false);

  /// Whether [method] was called at least once.
  bool wasCalled(String method) => invocations.any((i) => i.method == method);

  /// The most recent invocation, or null if nothing has been called.
  FakeApiInvocation? get lastInvocation =>
      invocations.isEmpty ? null : invocations.last;

  /// Clears recorded invocations (keeps stubs).
  void resetInvocations() => invocations.clear();

  // --- Dispatch --------------------------------------------------------------

  Future<Map<String, dynamic>> _dispatch(
    String method,
    Map<String, Object?> args, {
    String? accessToken,
  }) async {
    final invocation =
        FakeApiInvocation(method, args, accessToken: accessToken);
    invocations.add(invocation);
    final responder = _responders[method] ?? defaultResponder;
    if (responder == null) {
      throw StateError(
        'FakeApiClient.$method was called but not stubbed. '
        'Call stub("$method", response: {...}) or set defaultResponder.',
      );
    }
    return responder(invocation);
  }

  // --- Auth ------------------------------------------------------------------

  @override
  Future<LoginResponseData> login({
    required String email,
    required String password,
  }) async {
    final data = await _dispatch('login', {'email': email, 'password': password});
    return LoginResponseData.fromJson(data);
  }

  @override
  Future<Map<String, dynamic>> getConsentStatus({required String accessToken}) {
    return _dispatch('getConsentStatus', const {}, accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> acceptConsent({
    required String accessToken,
    required String consentVersion,
  }) {
    return _dispatch('acceptConsent', {'consentVersion': consentVersion},
        accessToken: accessToken);
  }

  // --- Research --------------------------------------------------------------

  @override
  Future<Map<String, dynamic>> researchTier2({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _dispatch('researchTier2', {'payload': payload},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> createResearchJob({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _dispatch('createResearchJob', {'payload': payload},
        accessToken: accessToken);
  }

  @override
  Stream<SseEvent> streamResearchJob({
    required String accessToken,
    required String jobId,
  }) {
    final invocation = FakeApiInvocation(
      'streamResearchJob',
      {'jobId': jobId},
      accessToken: accessToken,
    );
    invocations.add(invocation);
    final responder = _sseResponder;
    if (responder == null) {
      throw StateError(
        'FakeApiClient.streamResearchJob was called but not stubbed. '
        'Call stubStream(events: [...]).',
      );
    }
    return responder(invocation);
  }

  // --- CareGuard / cabinet ---------------------------------------------------

  @override
  Future<Map<String, dynamic>> analyzeCareguard({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _dispatch('analyzeCareguard', {'payload': payload},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> getCareguardCabinet({required String accessToken}) {
    return _dispatch('getCareguardCabinet', const {}, accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> addCareguardCabinetItem({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _dispatch('addCareguardCabinetItem', {'payload': payload},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> updateCareguardCabinetItem({
    required String accessToken,
    required int itemId,
    required Map<String, dynamic> payload,
  }) {
    return _dispatch(
        'updateCareguardCabinetItem', {'itemId': itemId, 'payload': payload},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> deleteCareguardCabinetItem({
    required String accessToken,
    required int itemId,
  }) {
    return _dispatch('deleteCareguardCabinetItem', {'itemId': itemId},
        accessToken: accessToken);
  }

  // --- Council ---------------------------------------------------------------

  @override
  Future<Map<String, dynamic>> runCouncil({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _dispatch('runCouncil', {'payload': payload},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> listCouncilCases({
    required String accessToken,
    int limit = 20,
    int offset = 0,
  }) {
    return _dispatch('listCouncilCases', {'limit': limit, 'offset': offset},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> getLatestCouncilCase({required String accessToken}) {
    return _dispatch('getLatestCouncilCase', const {},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> createCouncilCase({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _dispatch('createCouncilCase', {'payload': payload},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> getCouncilCase({
    required String accessToken,
    required int caseId,
  }) {
    return _dispatch('getCouncilCase', {'caseId': caseId},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> updateCouncilCase({
    required String accessToken,
    required int caseId,
    required Map<String, dynamic> payload,
  }) {
    return _dispatch('updateCouncilCase', {'caseId': caseId, 'payload': payload},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> submitCouncilCaseIntake({
    required String accessToken,
    required int caseId,
    String transcript = '',
    List<int>? audioBytes,
    String? audioFilename,
  }) {
    return _dispatch(
      'submitCouncilCaseIntake',
      {
        'caseId': caseId,
        'transcript': transcript,
        'audioBytes': audioBytes,
        'audioFilename': audioFilename,
      },
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> runCouncilCase({
    required String accessToken,
    required int caseId,
    Map<String, dynamic>? request,
    int? specialistCount,
    List<String>? specialists,
  }) {
    return _dispatch(
      'runCouncilCase',
      {
        'caseId': caseId,
        'request': request,
        'specialistCount': specialistCount,
        'specialists': specialists,
      },
      accessToken: accessToken,
    );
  }

  // --- System / summary ------------------------------------------------------

  @override
  Future<Map<String, dynamic>> getSystemMetrics({required String accessToken}) {
    return _dispatch('getSystemMetrics', const {}, accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> getMobileSummary({required String accessToken}) {
    return _dispatch('getMobileSummary', const {}, accessToken: accessToken);
  }

  // --- PHR -------------------------------------------------------------------

  @override
  Future<Map<String, dynamic>> getPhrRecord({required String accessToken}) {
    return _dispatch('getPhrRecord', const {}, accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> updatePhrRecord({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _dispatch('updatePhrRecord', {'payload': payload},
        accessToken: accessToken);
  }
}

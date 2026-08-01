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
  FakeApiClient({super.baseUrl = 'https://fake.clara.test'})
      : super(httpClient: _UnusableHttpClient());

  /// Every call made to this fake, in order.
  final List<FakeApiInvocation> invocations = <FakeApiInvocation>[];

  final Map<String, FakeApiResponder> _responders =
      <String, FakeApiResponder>{};

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
    final data =
        await _dispatch('login', {'email': email, 'password': password});
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

  @override
  Future<Map<String, dynamic>> getComplianceConsents({
    required String accessToken,
  }) {
    return _dispatch('getComplianceConsents', const {},
        accessToken: accessToken);
  }

  @override
  Future<void> grantComplianceConsent({
    required String accessToken,
    required String purpose,
    String? policyVersion,
  }) async {
    await _dispatch(
      'grantComplianceConsent',
      {'purpose': purpose, 'policyVersion': policyVersion},
      accessToken: accessToken,
    );
  }

  @override
  Future<void> withdrawComplianceConsent({
    required String accessToken,
    required String purpose,
  }) async {
    await _dispatch(
      'withdrawComplianceConsent',
      {'purpose': purpose},
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> submitDsarRequest({
    required String accessToken,
    required String kind,
  }) {
    return _dispatch('submitDsarRequest', {'kind': kind},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> deleteDsarData({
    required String accessToken,
  }) {
    return _dispatch('deleteDsarData', const {}, accessToken: accessToken);
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
  Future<Map<String, dynamic>> autoCheckCareguardCabinet({
    required String accessToken,
    List<String> symptoms = const <String>[],
    Map<String, dynamic> labs = const <String, dynamic>{},
    List<String> allergies = const <String>[],
    String locale = 'vi',
    List<Map<String, dynamic>> resolutions = const <Map<String, dynamic>>[],
  }) {
    return _dispatch(
      'autoCheckCareguardCabinet',
      <String, Object?>{
        'symptoms': symptoms,
        'labs': labs,
        'allergies': allergies,
        'locale': locale,
        'resolutions': resolutions,
      },
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> getCareguardCabinet(
      {required String accessToken}) {
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
  Future<Map<String, dynamic>> getLatestCouncilCase(
      {required String accessToken}) {
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
    return _dispatch(
        'updateCouncilCase', {'caseId': caseId, 'payload': payload},
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

  // --- Unified: PHR onboarding + LifeMap/Today -------------------------------

  @override
  Future<Map<String, dynamic>> getPhrOnboarding({required String accessToken}) {
    return _dispatch('getPhrOnboarding', const {}, accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> updatePhrOnboarding({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _dispatch('updatePhrOnboarding', {'payload': payload},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> getLifeMapToday({required String accessToken}) {
    return _dispatch('getLifeMapToday', const {}, accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> createLifeMapEpisode({
    required String accessToken,
    required String title,
    String goal = '',
    String priority = 'routine',
  }) {
    return _dispatch(
      'createLifeMapEpisode',
      {'title': title, 'goal': goal, 'priority': priority},
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> createLifeMapTask({
    required String accessToken,
    required String episodeId,
    required String title,
    String? dueAt,
  }) {
    return _dispatch(
      'createLifeMapTask',
      {'episodeId': episodeId, 'title': title, 'dueAt': dueAt},
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> acceptLifeMapTask({
    required String accessToken,
    required String taskId,
  }) {
    return _dispatch('acceptLifeMapTask', {'taskId': taskId},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> completeLifeMapTask({
    required String accessToken,
    required String taskId,
    Map<String, dynamic> evidence = const <String, dynamic>{},
  }) {
    return _dispatch(
        'completeLifeMapTask', {'taskId': taskId, 'evidence': evidence},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> getLifeMapReplay({
    required String accessToken,
    required String episodeId,
  }) {
    return _dispatch('getLifeMapReplay', {'episodeId': episodeId},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> correctLifeMapEvent({
    required String accessToken,
    required String eventId,
    required int revision,
    required Map<String, dynamic> payload,
    required String reason,
  }) {
    return _dispatch(
      'correctLifeMapEvent',
      {
        'eventId': eventId,
        'revision': revision,
        'payload': payload,
        'reason': reason,
      },
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> disputeLifeMapEvent({
    required String accessToken,
    required String eventId,
    required int revision,
    required String reason,
  }) {
    return _dispatch(
      'disputeLifeMapEvent',
      {'eventId': eventId, 'revision': revision, 'reason': reason},
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> resolveLifeMapEvent({
    required String accessToken,
    required String eventId,
    required int revision,
    required String reason,
  }) {
    return _dispatch(
      'resolveLifeMapEvent',
      {'eventId': eventId, 'revision': revision, 'reason': reason},
      accessToken: accessToken,
    );
  }

  @override
  Future<List<Map<String, dynamic>>> getLifeMapDisputes({
    required String accessToken,
  }) async {
    final value = await _dispatch('getLifeMapDisputes', const {},
        accessToken: accessToken);
    final data = value['data'];
    return data is List
        ? data
            .whereType<Map>()
            .map((item) => item.cast<String, dynamic>())
            .toList()
        : const <Map<String, dynamic>>[];
  }

  @override
  Future<Map<String, dynamic>> getLifeMapBaselines({
    required String accessToken,
  }) {
    return _dispatch('getLifeMapBaselines', const {}, accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> getLifeMapNextQuestion({
    required String accessToken,
    required String episodeId,
    String locale = 'vi',
  }) {
    return _dispatch(
      'getLifeMapNextQuestion',
      {'episodeId': episodeId, 'locale': locale},
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> recordLifeMapQuestionInteraction({
    required String accessToken,
    required String episodeId,
    required String questionId,
    required String action,
    String reason = '',
  }) {
    return _dispatch(
      'recordLifeMapQuestionInteraction',
      {
        'episodeId': episodeId,
        'questionId': questionId,
        'action': action,
        'reason': reason,
      },
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> startLifeMapGuidedAnswer({
    required String accessToken,
    required String episodeId,
    required String questionId,
    required Map<String, dynamic> answer,
    String locale = 'vi',
  }) {
    return _dispatch(
      'startLifeMapGuidedAnswer',
      {
        'episodeId': episodeId,
        'questionId': questionId,
        'answer': answer,
        'locale': locale,
      },
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> startLifeMapTextCapture({
    required String accessToken,
    required String text,
    String locale = 'vi',
  }) {
    return _dispatch(
      'startLifeMapTextCapture',
      {'text': text, 'locale': locale},
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> getLifeMapCaptureSession({
    required String accessToken,
    required String sessionId,
  }) {
    return _dispatch(
      'getLifeMapCaptureSession',
      {'sessionId': sessionId},
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> abandonLifeMapCaptureSession({
    required String accessToken,
    required String sessionId,
  }) {
    return _dispatch(
      'abandonLifeMapCaptureSession',
      {'sessionId': sessionId},
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> reviewLifeMapCaptureCandidate({
    required String accessToken,
    required String candidateId,
    required String action,
    Map<String, dynamic>? value,
    String reason = '',
    bool acceptNormalization = false,
  }) {
    return _dispatch(
      'reviewLifeMapCaptureCandidate',
      {
        'candidateId': candidateId,
        'action': action,
        'value': value,
        'reason': reason,
        'acceptNormalization': acceptNormalization,
      },
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> getLifeMapCaptureNormalization({
    required String accessToken,
    required String candidateId,
  }) {
    return _dispatch(
      'getLifeMapCaptureNormalization',
      {'candidateId': candidateId},
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> startLifeMapArtifactCapture({
    required String accessToken,
    required String inputKind,
    String locale = 'vi',
  }) {
    return _dispatch(
      'startLifeMapArtifactCapture',
      {'inputKind': inputKind, 'locale': locale},
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> uploadLifeMapCaptureArtifact({
    required String accessToken,
    required String sessionId,
    required List<int> bytes,
    required String filename,
  }) {
    return _dispatch(
      'uploadLifeMapCaptureArtifact',
      {
        'sessionId': sessionId,
        'byteCount': bytes.length,
        'filename': filename,
      },
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> getLifeMapCaptureJob({
    required String accessToken,
    required String jobId,
  }) {
    return _dispatch(
      'getLifeMapCaptureJob',
      {'jobId': jobId},
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> getLifeMapSummary({
    required String accessToken,
    required String level,
    String? episodeId,
    String locale = 'vi',
  }) {
    return _dispatch(
      'getLifeMapSummary',
      {'level': level, 'episodeId': episodeId, 'locale': locale},
      accessToken: accessToken,
    );
  }

  // --- Scribe ----------------------------------------------------------------

  @override
  Future<Map<String, dynamic>> listScribeSessions({
    required String accessToken,
    int limit = 20,
    int offset = 0,
  }) {
    return _dispatch('listScribeSessions', {'limit': limit, 'offset': offset},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> createScribeSession({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _dispatch('createScribeSession', {'payload': payload},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> getScribeSession({
    required String accessToken,
    required int sessionId,
  }) {
    return _dispatch('getScribeSession', {'sessionId': sessionId},
        accessToken: accessToken);
  }

  @override
  Future<Map<String, dynamic>> transcribeScribeAudio({
    required String accessToken,
    required List<int> audioBytes,
    String? filename,
    String? language,
    String? prompt,
    int? chunkIndex,
    int? sessionId,
    bool? appendToSession,
  }) {
    return _dispatch(
      'transcribeScribeAudio',
      {
        'audioBytes': audioBytes,
        'filename': filename,
        'language': language,
        'prompt': prompt,
        'chunkIndex': chunkIndex,
        'sessionId': sessionId,
        'appendToSession': appendToSession,
      },
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> regenerateScribeSession({
    required String accessToken,
    required int sessionId,
    Map<String, dynamic> payload = const {},
  }) {
    return _dispatch(
      'regenerateScribeSession',
      {'sessionId': sessionId, 'payload': payload},
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> captureScribeConsent({
    required String accessToken,
    required int sessionId,
    String method = 'verbal',
    String scope = 'encounter',
  }) {
    return _dispatch(
      'captureScribeConsent',
      {'sessionId': sessionId, 'method': method, 'scope': scope},
      accessToken: accessToken,
    );
  }

  @override
  Future<Map<String, dynamic>> revokeScribeConsent({
    required String accessToken,
    required int sessionId,
  }) {
    return _dispatch('revokeScribeConsent', {'sessionId': sessionId},
        accessToken: accessToken);
  }

  // --- Social platform -------------------------------------------------------
  // The list-returning social methods can't route through the Map-typed
  // `_dispatch`, so they use dedicated in-memory stub fields.

  Map<String, dynamic> socialConsent = <String, dynamic>{'granted': false};
  List<Map<String, dynamic>> socialCommunities = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> socialFeed = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> socialComments = <Map<String, dynamic>>[];
  Object? socialError;

  @override
  Future<Map<String, dynamic>> getSocialConsent(
      {required String accessToken}) async {
    invocations.add(FakeApiInvocation('getSocialConsent', const {},
        accessToken: accessToken));
    if (socialError != null) throw socialError!;
    return socialConsent;
  }

  @override
  Future<Map<String, dynamic>> grantSocialConsent(
      {required String accessToken}) async {
    invocations.add(FakeApiInvocation('grantSocialConsent', const {},
        accessToken: accessToken));
    socialConsent = <String, dynamic>{'granted': true};
    return socialConsent;
  }

  @override
  Future<List<Map<String, dynamic>>> listSocialCommunities(
      {required String accessToken}) async {
    invocations.add(FakeApiInvocation('listSocialCommunities', const {},
        accessToken: accessToken));
    if (socialError != null) throw socialError!;
    return socialCommunities;
  }

  @override
  Future<Map<String, dynamic>> joinSocialCommunity({
    required String accessToken,
    required int communityId,
  }) async {
    invocations.add(FakeApiInvocation(
        'joinSocialCommunity', {'communityId': communityId},
        accessToken: accessToken));
    return <String, dynamic>{'joined': true};
  }

  @override
  Future<List<Map<String, dynamic>>> getSocialFeed({
    required String accessToken,
    int limit = 20,
    int offset = 0,
  }) async {
    invocations.add(FakeApiInvocation(
        'getSocialFeed', {'limit': limit, 'offset': offset},
        accessToken: accessToken));
    if (socialError != null) throw socialError!;
    return socialFeed;
  }

  @override
  Future<Map<String, dynamic>> createSocialPost({
    required String accessToken,
    required int communityId,
    required String title,
    required String body,
  }) async {
    invocations.add(FakeApiInvocation(
      'createSocialPost',
      {'communityId': communityId, 'title': title, 'body': body},
      accessToken: accessToken,
    ));
    if (socialError != null) throw socialError!;
    return <String, dynamic>{'id': 1, 'title': title, 'body': body};
  }

  @override
  Future<List<Map<String, dynamic>>> getSocialComments({
    required String accessToken,
    required int postId,
  }) async {
    invocations.add(FakeApiInvocation('getSocialComments', {'postId': postId},
        accessToken: accessToken));
    return socialComments;
  }

  /// When set, `addSocialComment` throws this instead of succeeding (used to
  /// exercise the moderation-block path).
  Object? socialCommentError;

  @override
  Future<Map<String, dynamic>> addSocialComment({
    required String accessToken,
    required int postId,
    required String body,
  }) async {
    invocations.add(FakeApiInvocation(
        'addSocialComment', {'postId': postId, 'body': body},
        accessToken: accessToken));
    if (socialCommentError != null) throw socialCommentError!;
    return <String, dynamic>{'id': 1, 'body': body};
  }

  @override
  Future<Map<String, dynamic>> addSocialReaction({
    required String accessToken,
    required int postId,
    required String kind,
  }) async {
    invocations.add(FakeApiInvocation(
        'addSocialReaction', {'postId': postId, 'kind': kind},
        accessToken: accessToken));
    return <String, dynamic>{'ok': true};
  }

  @override
  Future<Map<String, dynamic>> reportSocialContent({
    required String accessToken,
    required String targetType,
    required int targetId,
    String reason = '',
  }) async {
    invocations.add(FakeApiInvocation(
      'reportSocialContent',
      {'targetType': targetType, 'targetId': targetId, 'reason': reason},
      accessToken: accessToken,
    ));
    return <String, dynamic>{'reported': true};
  }
}

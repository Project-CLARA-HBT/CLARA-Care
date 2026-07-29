import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'session_store.dart';

/// Seam the [ApiClient] uses to read the current session, persist a refreshed
/// session, or clear it (forcing re-login). Kept as a small interface so the
/// refresh state machine is testable without `flutter_secure_storage` and
/// without coupling networking to a concrete store. When no hooks are attached
/// the client behaves exactly as before (fully back-compatible — no pre-flight
/// check and no 401 refresh-retry).
abstract class AuthSessionHooks {
  /// The currently held access token (may be expired).
  String? get accessToken;

  /// The currently held refresh token, or null/empty when none is held.
  String? get refreshToken;

  /// The current role, used to preserve role when a refresh response omits it.
  String? get role;

  /// Pre-flight check: whether the held access token is expired/invalid.
  bool get isAccessTokenExpired;

  /// Persists a freshly refreshed session (Req 6.2).
  Future<void> onSessionRefreshed({
    required String accessToken,
    required String refreshToken,
    required String role,
  });

  /// Clears the session, forcing re-login (Req 6.3).
  Future<void> onSessionCleared();
}

/// Adapts a [PersistentSessionStore] to [AuthSessionHooks] so the production
/// app wires token refresh straight onto the existing secure-storage session
/// store. Additive: construct this and pass it to [ApiClient] (or attach it via
/// [ApiClient.authHooks]) to enable refresh; omit it to preserve old behavior.
class SessionStoreAuthHooks implements AuthSessionHooks {
  SessionStoreAuthHooks(this._store, {this.onCleared});

  final PersistentSessionStore _store;

  /// Optional navigation side-effect invoked after the session is cleared
  /// (e.g. routing to the login screen). Kept separate from persistence so the
  /// store stays UI-agnostic.
  final Future<void> Function()? onCleared;

  @override
  String? get accessToken => _store.accessToken;

  @override
  String? get refreshToken => _store.refreshToken;

  @override
  String? get role => _store.role;

  @override
  bool get isAccessTokenExpired => _store.isExpired;

  @override
  Future<void> onSessionRefreshed({
    required String accessToken,
    required String refreshToken,
    required String role,
  }) {
    return _store.setSession(
      email: _store.email ?? '',
      accessToken: accessToken,
      refreshToken: refreshToken,
      role: role,
    );
  }

  @override
  Future<void> onSessionCleared() async {
    await _store.clear();
    if (onCleared != null) {
      await onCleared!();
    }
  }
}

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
    Duration requestTimeout = const Duration(seconds: 30),
    Duration streamIdleTimeout = const Duration(seconds: 60),
    this.authHooks,
  })  : _baseUrl = _trimTrailingSlash(baseUrl),
        _httpClient = httpClient ?? http.Client(),
        _requestTimeout = requestTimeout,
        _streamIdleTimeout = streamIdleTimeout;

  final String _baseUrl;
  final http.Client _httpClient;

  /// Resolved API origin used by this client.
  ///
  /// This exposes configuration only (never credentials) for the few
  /// authenticated, additive surfaces that have their own narrowly scoped
  /// transport seam, such as the PDPD data-rights request screen.
  String get baseUrl => _baseUrl;

  /// Session seam enabling pre-flight expiry refresh and the single 401-retry
  /// (Req 6.2, 6.3). Null until attached (default), keeping the legacy path
  /// untouched. Settable so the store and client can be constructed in either
  /// order (e.g. wired together in `main`).
  AuthSessionHooks? authHooks;

  /// De-duplicates concurrent refreshes: parallel authenticated requests that
  /// all see an expired token (or all receive 401) share a single in-flight
  /// `POST /auth/refresh` rather than stampeding the endpoint.
  Future<String?>? _refreshInFlight;

  /// Monotonic counter feeding [_idempotencyKey] so repeated mutations within a
  /// session get distinct keys while a retried single call can reuse one.
  int _idempotencyCounter = 0;

  /// Generates a client-side `Idempotency-Key` for LifeMap/medication/visit
  /// mutations that require one. Combines a millisecond timestamp with a
  /// per-instance counter so keys are unique without a UUID dependency.
  String _idempotencyKey() {
    _idempotencyCounter += 1;
    return 'm-${DateTime.now().microsecondsSinceEpoch}-$_idempotencyCounter';
  }

  /// Maximum time to await a single request/response round-trip before it is
  /// surfaced as a recoverable [ApiException] instead of hanging (Req 9.2).
  final Duration _requestTimeout;

  /// Maximum idle time between SSE events before a stalled stream is surfaced
  /// as a recoverable [ApiException]. Reset by every event, including the
  /// server's keepalive comments (Req 9.2, 2.6).
  final Duration _streamIdleTimeout;

  /// Vietnamese-first, PII-free message used when a request/stream exceeds its
  /// bounded timeout. Maps cleanly onto the existing [ApiException] type so
  /// callers handle a timeout exactly like any other recoverable API error.
  static const String _timeoutMessage = 'Hết thời gian chờ phản hồi từ server.';

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

  // ---------------------------------------------------------------------------
  // Auth lifecycle parity (clara-mobile-feature-parity Req 6.1).
  //
  // These mirror the web auth surface (`apps/web/lib/http-client.ts` /
  // `logout.ts`) and the server Auth_API routes mounted under `/api/v1/auth`
  // (see `services/api/.../endpoints/auth.py`). register/verify-email/
  // forgot-password/reset-password are unauthenticated (no access token), so
  // they take the `_sendAuthed` fast path with no pre-flight refresh. logout
  // accepts an optional access token because the server gate is
  // `get_optional_current_token`. Request/response bodies match the server
  // pydantic schemas exactly (`RegisterRequest`/`RegisterResponse`,
  // `VerifyEmailRequest`, `ForgotPasswordRequest`/`ForgotPasswordResponse`,
  // `ResetPasswordRequest`) — no mobile-only shape is introduced. The consent
  // status / accept methods already exist below (`getConsentStatus` /
  // `acceptConsent`) and are intentionally not duplicated here.
  // ---------------------------------------------------------------------------

  /// Registers a new account (Req 6.1). `POST /api/v1/auth/register`.
  /// [payload] mirrors the server `RegisterRequest`: `email`, `password`, and
  /// the optional `full_name`, `role`, and `accepted_terms` /
  /// `accepted_privacy` / `accepted_medical_consent` flags (the latter three
  /// are required in production). Returns the `RegisterResponse` envelope
  /// (`user_id`, `email`, `role`, `is_email_verified`, `email_delivery_status`,
  /// `verification_token_preview`). A duplicate email is rejected server-side
  /// (409) and surfaces as an [ApiException]. Unauthenticated.
  Future<Map<String, dynamic>> register({
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/auth/register',
      body: payload,
    );
  }

  /// Verifies an email-verification token (Req 6.1).
  /// `POST /api/v1/auth/verify-email`. The body mirrors the server
  /// `VerifyEmailRequest` (`{ "token": ... }`); an invalid or expired token is
  /// rejected server-side (400) and surfaces as an [ApiException]. Returns
  /// `{ "verified": true, "email": ... }`. Unauthenticated.
  Future<Map<String, dynamic>> verifyEmail({
    required String token,
  }) {
    return _post(
      '/api/v1/auth/verify-email',
      body: {'token': token},
    );
  }

  /// Requests a password-reset email (Req 6.1).
  /// `POST /api/v1/auth/forgot-password`. The body mirrors the server
  /// `ForgotPasswordRequest` (`{ "email": ... }`). To avoid account
  /// enumeration the server always returns an accepted envelope regardless of
  /// whether the email exists (`ForgotPasswordResponse`: `accepted`,
  /// `email_delivery_status`, `reset_token_preview`). Unauthenticated.
  Future<Map<String, dynamic>> forgotPassword({
    required String email,
  }) {
    return _post(
      '/api/v1/auth/forgot-password',
      body: {'email': email},
    );
  }

  /// Resets a password using a reset token (Req 6.1).
  /// `POST /api/v1/auth/reset-password`. The body mirrors the server
  /// `ResetPasswordRequest` (`{ "token": ..., "new_password": ... }`); an
  /// invalid/expired token (400) or a new password that fails the server
  /// policy surfaces as an [ApiException]. Returns `{ "reset": true }`.
  /// Unauthenticated.
  Future<Map<String, dynamic>> resetPassword({
    required String token,
    required String newPassword,
  }) {
    return _post(
      '/api/v1/auth/reset-password',
      body: {'token': token, 'new_password': newPassword},
    );
  }

  /// Logs out, revoking the caller's server-side refresh sessions (Req 6.1).
  /// `POST /api/v1/auth/logout`. The access token is optional server-side
  /// (`get_optional_current_token`); pass [accessToken] when one is held so the
  /// server can revoke the matching refresh sessions and denylist the presented
  /// token. Returns `{ "logged_out": true, "revoked_refresh_sessions": int }`.
  Future<Map<String, dynamic>> logout({
    String? accessToken,
  }) {
    return _post(
      '/api/v1/auth/logout',
      body: const {},
      accessToken: accessToken,
    );
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
  }) {
    final uri = Uri.parse('$_baseUrl/api/v1/research/tier2/jobs/$jobId/stream');
    final request = http.Request('GET', uri);
    request.headers.addAll({
      'Accept': 'text/event-stream',
      'Cache-Control': 'no-cache',
      if (accessToken.isNotEmpty) 'Authorization': 'Bearer $accessToken',
    });
    return _streamSse(request);
  }

  /// Shared SSE consumer reused by the research-job and chat streams. Sends the
  /// prepared [request], maps a stalled connection/idle gap onto the existing
  /// recoverable [ApiException] (Req 9.2, 2.6), then parses the SSE protocol:
  /// lines prefixed with `id:`, `event:`, `data:`, or comments `:`, with events
  /// separated by blank lines. Yields one [SseEvent] per complete frame and
  /// flushes a trailing frame that was not terminated by a blank line.
  Stream<SseEvent> _streamSse(http.BaseRequest request) async* {
    final http.StreamedResponse response;
    try {
      response = await _httpClient.send(request).timeout(_requestTimeout);
    } on TimeoutException {
      throw ApiException(message: _timeoutMessage);
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

    String? currentId;
    String? currentEvent;
    final dataBuffer = StringBuffer();

    // Bound the idle gap between SSE events: if no line (event or keepalive
    // comment) arrives within [_streamIdleTimeout], surface a recoverable
    // [ApiException] instead of hanging forever (Req 9.2, 2.6).
    final lines = response.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .timeout(
      _streamIdleTimeout,
      onTimeout: (sink) {
        sink.addError(ApiException(message: _timeoutMessage));
        sink.close();
      },
    );

    await for (final chunk in lines) {
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

  /// Submits a chat turn and returns the full assistant answer envelope in a
  /// single blocking response (Req 1.1). Mirrors the web `sendChatMessage`
  /// contract: `POST /api/v1/chat` with `{ "message": ... }`, returning the
  /// `ChatResponse` shape (`reply`, `role`, `intent`, `confidence`,
  /// `emergency`, `model_used`, `retrieved_ids`, `ml`, `fallback`,
  /// `attribution`, optional `ai_disclosure`). Routes through [_sendAuthed], so
  /// it inherits the bounded timeout and token-refresh resilience.
  ///
  /// [payload] is the request body; callers pass at least `{'message': text}`.
  Future<Map<String, dynamic>> chat({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/chat',
      body: payload,
      accessToken: accessToken,
    );
  }

  /// Opens the chat SSE stream and yields [SseEvent]s as the answer is
  /// produced (Req 1.2). Mirrors the web `streamChatMessage` contract:
  /// `POST /api/v1/chat/stream` with `{ "message": ... }` and
  /// `Accept: text/event-stream`. The server emits `start`, `step`, `token`
  /// (`{"text": ...}`), and a terminal `done` (final envelope) or `error`
  /// (`{"message": ...}`) frame; callers can fall back to [chat] on `error` or
  /// disconnect, preserving any already-streamed content (Req 1.3).
  ///
  /// Reuses the shared SSE parser ([_streamSse]) so the bounded idle timeout
  /// applies identically to research and chat streams.
  Stream<SseEvent> streamChat({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    final uri = Uri.parse('$_baseUrl/api/v1/chat/stream');
    final request = http.Request('POST', uri);
    request.headers.addAll({
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
      'Cache-Control': 'no-cache',
      if (accessToken.isNotEmpty) 'Authorization': 'Bearer $accessToken',
    });
    request.body = jsonEncode(payload);
    return _streamSse(request);
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

  /// Scans a medication-label image through the API OCR bridge
  /// (`POST /api/v1/careguard/cabinet/scan-file`, multipart `file`), returning
  /// the `CabinetScanTextResponse` envelope: `{ detections, extracted_text,
  /// ocr_provider, ocr_endpoint, prioritized_fields, confirm_gate }`
  /// (clara-mobile-liquid-glass R4). The server rejects an empty file (400) or
  /// one larger than its limit (413), surfacing as an [ApiException]. No OCR is
  /// performed client-side; the raw image is sent for server-side extraction.
  Future<Map<String, dynamic>> scanCareguardCabinetFile({
    required String accessToken,
    required List<int> fileBytes,
    String? filename,
  }) {
    return _postMultipart(
      '/api/v1/careguard/cabinet/scan-file',
      accessToken: accessToken,
      fields: const <String, String>{},
      fileField: 'file',
      fileBytes: fileBytes,
      filename: filename ?? 'medication-label.jpg',
    );
  }

  /// Imports user-confirmed OCR detections into the cabinet
  /// (`POST /api/v1/careguard/cabinet/import-detections`, JSON
  /// `{ detections: [...] }`, max 200). The server enforces the manual-confirm
  /// gate (422 when a low-confidence detection is unconfirmed), so callers must
  /// only send detections the user explicitly confirmed (R4.4). Returns
  /// `{ inserted, prioritized_fields }`.
  Future<Map<String, dynamic>> importCareguardDetections({
    required String accessToken,
    required List<Map<String, dynamic>> detections,
  }) {
    return _post(
      '/api/v1/careguard/cabinet/import-detections',
      body: <String, dynamic>{'detections': detections},
      accessToken: accessToken,
    );
  }

  // ---------------------------------------------------------------------------
  // Social platform ops (spec: clara-health-social). All routes 404 when the
  // server-side `social_platform_enabled` flag is off, so callers must treat a
  // NotFound as "feature unavailable" and hide the surface (fail-closed).
  // ---------------------------------------------------------------------------

  /// Returns the current user's social-participation consent status
  /// (`GET /api/v1/social/consent`) → `{ consent_type, granted }`.
  Future<Map<String, dynamic>> getSocialConsent({required String accessToken}) {
    return _get('/api/v1/social/consent', accessToken: accessToken);
  }

  /// Grants social-participation consent (`POST /api/v1/social/consent`).
  Future<Map<String, dynamic>> grantSocialConsent(
      {required String accessToken}) {
    return _post('/api/v1/social/consent',
        body: const {}, accessToken: accessToken);
  }

  /// Lists curated communities (`GET /api/v1/social/communities`).
  Future<List<Map<String, dynamic>>> listSocialCommunities({
    required String accessToken,
  }) async {
    final res =
        await _get('/api/v1/social/communities', accessToken: accessToken);
    return _asMapList(res['data'] ?? res['items']);
  }

  /// Joins a community (`POST /api/v1/social/communities/{id}/join`).
  Future<Map<String, dynamic>> joinSocialCommunity({
    required String accessToken,
    required int communityId,
  }) {
    return _post(
      '/api/v1/social/communities/$communityId/join',
      body: const {},
      accessToken: accessToken,
    );
  }

  /// Returns the recency-ranked feed (`GET /api/v1/social/feed`).
  Future<List<Map<String, dynamic>>> getSocialFeed({
    required String accessToken,
    int limit = 20,
    int offset = 0,
  }) async {
    final res = await _get(
      '/api/v1/social/feed?limit=$limit&offset=$offset',
      accessToken: accessToken,
    );
    return _asMapList(res['data'] ?? res['items']);
  }

  /// Creates a post (`POST /api/v1/social/posts`). The server screens the body
  /// through the moderation guard before persisting (422 when blocked).
  Future<Map<String, dynamic>> createSocialPost({
    required String accessToken,
    required int communityId,
    required String title,
    required String body,
  }) {
    return _post(
      '/api/v1/social/posts',
      body: <String, dynamic>{
        'community_id': communityId,
        'title': title,
        'body': body,
      },
      accessToken: accessToken,
    );
  }

  /// Returns a post's comments (`GET /api/v1/social/posts/{id}/comments`).
  Future<List<Map<String, dynamic>>> getSocialComments({
    required String accessToken,
    required int postId,
  }) async {
    final res = await _get(
      '/api/v1/social/posts/$postId/comments',
      accessToken: accessToken,
    );
    return _asMapList(res['data'] ?? res['items']);
  }

  /// Adds a comment (`POST /api/v1/social/posts/{id}/comments`), moderated.
  Future<Map<String, dynamic>> addSocialComment({
    required String accessToken,
    required int postId,
    required String body,
  }) {
    return _post(
      '/api/v1/social/posts/$postId/comments',
      body: <String, dynamic>{'body': body},
      accessToken: accessToken,
    );
  }

  /// Adds a supportive reaction (`POST /api/v1/social/posts/{id}/reactions`).
  Future<Map<String, dynamic>> addSocialReaction({
    required String accessToken,
    required int postId,
    required String kind,
  }) {
    return _post(
      '/api/v1/social/posts/$postId/reactions',
      body: <String, dynamic>{'kind': kind},
      accessToken: accessToken,
    );
  }

  /// Reports a post/comment (`POST /api/v1/social/reports`).
  Future<Map<String, dynamic>> reportSocialContent({
    required String accessToken,
    required String targetType,
    required int targetId,
    String reason = '',
  }) {
    return _post(
      '/api/v1/social/reports',
      body: <String, dynamic>{
        'target_type': targetType,
        'target_id': targetId,
        'reason': reason,
      },
      accessToken: accessToken,
    );
  }

  /// Returns the current user's social profile (`GET /api/v1/social/me/profile`).
  Future<Map<String, dynamic>> getSocialProfile({required String accessToken}) {
    return _get('/api/v1/social/me/profile', accessToken: accessToken);
  }

  /// Updates the current user's social profile
  /// (`PATCH /api/v1/social/me/profile`).
  Future<Map<String, dynamic>> updateSocialProfile({
    required String accessToken,
    required String displayName,
    required String bio,
  }) {
    return _patch(
      '/api/v1/social/me/profile',
      body: <String, dynamic>{'display_name': displayName, 'bio': bio},
      accessToken: accessToken,
    );
  }

  static List<Map<String, dynamic>> _asMapList(Object? raw) {
    if (raw is! List) return const [];
    return raw.whereType<Map>().map((e) => e.cast<String, dynamic>()).toList();
  }

  // ---------------------------------------------------------------------------
  // Self-med cabinet ops (clara-mobile-feature-parity Req 3.1, 3.2).
  //
  // The web "self-med" surface (`apps/web/lib/selfmed.ts`) is NOT backed by a
  // distinct `/selfmed/*` API — its `getCabinet` / `addCabinetItem` /
  // `deleteCabinetItem` all call the shared `/careguard/cabinet*` endpoints
  // (the CLARA_API exposes no `/selfmed/*` routes). To match that actual server
  // contract without changing it (Req 15.5), the mobile self-med cabinet ops are
  // thin, selfmed-named aliases that delegate to the existing careguard cabinet
  // methods. This keeps the change additive/surgical and lets the SelfMedCabinet
  // screen (task 5.2) depend on parity-named methods rather than reaching for
  // the careguard-prefixed ones directly.
  // ---------------------------------------------------------------------------

  /// Loads the owner's self-med cabinet, mirroring the web `getCabinet`
  /// contract (`GET /api/v1/careguard/cabinet`). Returns the
  /// `{ cabinet_id, items: [...], ... }` envelope (Req 3.1).
  Future<Map<String, dynamic>> getCabinet({
    required String accessToken,
  }) {
    return getCareguardCabinet(accessToken: accessToken);
  }

  /// Adds a self-med cabinet item, mirroring the web `addCabinetItem` contract
  /// (`POST /api/v1/careguard/cabinet/items`). A duplicate normalized name is
  /// rejected server-side (409) and surfaces as an [ApiException] (Req 3.2).
  Future<Map<String, dynamic>> addCabinetItem({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return addCareguardCabinetItem(accessToken: accessToken, payload: payload);
  }

  /// Deletes a self-med cabinet item scoped to the owner, mirroring the web
  /// `deleteCabinetItem` contract
  /// (`DELETE /api/v1/careguard/cabinet/items/{itemId}`) (Req 3.2).
  Future<Map<String, dynamic>> deleteCabinetItem({
    required String accessToken,
    required int itemId,
  }) {
    return deleteCareguardCabinetItem(
      accessToken: accessToken,
      itemId: itemId,
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

  // ---------------------------------------------------------------------------
  // Ambient scribe ops (clara-mobile-feature-parity Req 4.1, 4.2, 4.3, 4.4, 4.5).
  //
  // These mirror the web scribe client (`apps/web/lib/scribe.ts`) and the
  // server Scribe_API routes mounted under `/api/v1/scribe` (see
  // `services/api/.../endpoints/scribe.py`). Every route is doctor-RBAC-gated
  // server-side and owner-scoped; the mobile screen (task 6.2) layers the
  // `scribe_mobile_enabled` flag + RBAC + consent gate on top. The methods are
  // thin, additive wrappers reusing `_get`/`_post`/`_postMultipart`, so they
  // inherit the same bounded-timeout / token-refresh resilience as the rest of
  // the client. No mobile-only request/response shape is introduced — the
  // session envelope is the shared `ScribeSessionResponse`.
  // ---------------------------------------------------------------------------

  /// Lists the clinician's own scribe sessions, newest-first
  /// (`GET /api/v1/scribe/sessions`). Returns the `{ items: [...], total: int }`
  /// envelope; each item is the shared `ScribeSessionResponse` shape (Req 4.2).
  Future<Map<String, dynamic>> listScribeSessions({
    required String accessToken,
    int limit = 20,
    int offset = 0,
  }) {
    return _get(
      '/api/v1/scribe/sessions?limit=$limit&offset=$offset',
      accessToken: accessToken,
    );
  }

  /// Creates a new scribe session (`POST /api/v1/scribe/sessions`). [payload]
  /// mirrors the server `ScribeSessionCreateRequest`
  /// (`title`, `transcript`, `auto_generate_soap`); when a transcript is
  /// supplied and `auto_generate_soap` is true the server returns the session
  /// with its generated SOAP note (Req 4.1, 4.2). Returns the session envelope.
  Future<Map<String, dynamic>> createScribeSession({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/scribe/sessions',
      body: payload,
      accessToken: accessToken,
    );
  }

  /// Loads a single owned scribe session by id, including its transcript, SOAP
  /// note, insights, and status (`GET /api/v1/scribe/sessions/{sessionId}`).
  /// Throws an [ApiException] (404) when the session is not owned/absent.
  Future<Map<String, dynamic>> getScribeSession({
    required String accessToken,
    required int sessionId,
  }) {
    return _get(
      '/api/v1/scribe/sessions/$sessionId',
      accessToken: accessToken,
    );
  }

  /// Transcribes an uploaded audio clip via the server ASR proxy
  /// (`POST /api/v1/scribe/transcribe`, multipart form). Mirrors the web
  /// `transcribeScribeAudio` contract: the file part is `audio_file` and the
  /// optional string form fields are `language`, `prompt`, `chunk_index`,
  /// `session_id`, and `append_to_session`. When [sessionId] is provided with
  /// [appendToSession] true the server appends the recognized text to that
  /// session's transcript. The server enforces the 15MB size limit and the
  /// audio content-type allow-list, and (when consent is required) rejects a
  /// transcription for a session with no active consent before any ASR work
  /// (Req 4.1, 4.4). Returns the ML transcribe payload (`{ text, language, ...}`).
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
    final fields = <String, String>{};
    if (language != null && language.isNotEmpty) {
      fields['language'] = language;
    }
    if (prompt != null && prompt.isNotEmpty) {
      fields['prompt'] = prompt;
    }
    if (chunkIndex != null) {
      fields['chunk_index'] = chunkIndex.toString();
    }
    if (sessionId != null) {
      fields['session_id'] = sessionId.toString();
    }
    if (appendToSession != null) {
      fields['append_to_session'] = appendToSession ? 'true' : 'false';
    }
    return _postMultipart(
      '/api/v1/scribe/transcribe',
      accessToken: accessToken,
      fields: fields,
      fileField: 'audio_file',
      fileBytes: audioBytes,
      filename: filename ?? 'scribe-live.webm',
    );
  }

  /// Regenerates the SOAP note for an owned session
  /// (`POST /api/v1/scribe/sessions/{sessionId}/regenerate`). [payload] mirrors
  /// the server `ScribeSessionRegenerateRequest` (optional `transcript` to
  /// regenerate from, optional `status`); an empty/absent transcript with no
  /// stored transcript is rejected server-side (400) and surfaces as an
  /// [ApiException] (Req 4.2). Returns the updated session envelope.
  Future<Map<String, dynamic>> regenerateScribeSession({
    required String accessToken,
    required int sessionId,
    Map<String, dynamic> payload = const {},
  }) {
    return _post(
      '/api/v1/scribe/sessions/$sessionId/regenerate',
      body: payload,
      accessToken: accessToken,
    );
  }

  /// Captures an immutable patient-consent record for a session
  /// (`POST /api/v1/scribe/sessions/{sessionId}/consent`). [method] and [scope]
  /// mirror the server `ConsentRequest` defaults (`verbal` / `encounter`).
  /// Consent must be captured before audio processing when consent is required
  /// (Req 4.4). Returns `{ session_id, consent_id, captured: true }`.
  Future<Map<String, dynamic>> captureScribeConsent({
    required String accessToken,
    required int sessionId,
    String method = 'verbal',
    String scope = 'encounter',
  }) {
    return _post(
      '/api/v1/scribe/sessions/$sessionId/consent',
      body: {'method': method, 'scope': scope},
      accessToken: accessToken,
    );
  }

  /// Revokes the active consent for a session
  /// (`POST /api/v1/scribe/sessions/{sessionId}/consent/revoke`). Revocation is
  /// a new audit event that leaves the original consent record immutable and
  /// flags the session so further transcription/streaming is blocked (Req 4.4).
  /// Throws an [ApiException] (404) when there is no active consent to revoke.
  /// Returns `{ session_id, consent_id, revoked: true }`.
  Future<Map<String, dynamic>> revokeScribeConsent({
    required String accessToken,
    required int sessionId,
  }) {
    return _post(
      '/api/v1/scribe/sessions/$sessionId/consent/revoke',
      body: const {},
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

  /// Server-authoritative state vocabulary, capability and offline policy.
  Future<Map<String, dynamic>> getLifeMapClientContract({
    required String accessToken,
  }) {
    return _get(
      '/api/v1/lifemap/v2/client-contract',
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

  // ---------------------------------------------------------------------------
  // Connected-health control plane. These methods intentionally expose only
  // CLARA's provider-neutral API model; native SDK objects never leave the
  // Android bridge or enter screens.
  // ---------------------------------------------------------------------------

  Future<List<Map<String, dynamic>>> getConnectorCapabilities({
    required String accessToken,
  }) async {
    final data = await _get(
      '/api/v1/connectors/capabilities',
      accessToken: accessToken,
    );
    return _asMapList(data['items'] ?? data['data']);
  }

  Future<List<Map<String, dynamic>>> listConnectedHealthSources({
    required String accessToken,
  }) async {
    final data = await _get('/api/v1/connectors', accessToken: accessToken);
    return _asMapList(data['items'] ?? data['data']);
  }

  Future<Map<String, dynamic>> pauseConnectedHealthSource({
    required String accessToken,
    required String connectorId,
  }) {
    return _post(
      '/api/v1/connectors/$connectorId/pause',
      body: const <String, dynamic>{},
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> resumeConnectedHealthSource({
    required String accessToken,
    required String connectorId,
  }) {
    return _post(
      '/api/v1/connectors/$connectorId/resume',
      body: const <String, dynamic>{},
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> disconnectConnectedHealthSource({
    required String accessToken,
    required String connectorId,
  }) {
    return _delete(
      '/api/v1/connectors/$connectorId',
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> deleteConnectedHealthImportedData({
    required String accessToken,
    required String connectorId,
  }) {
    return _delete(
      '/api/v1/connectors/$connectorId/imported-data',
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

  // --- PHR onboarding (clara-mobile-unified) --------------------------------

  /// Returns the durable first-run onboarding decision (never infers health
  /// facts). `needs_onboarding` is true only while status is `pending`.
  Future<Map<String, dynamic>> getPhrOnboarding({
    required String accessToken,
  }) {
    return _get('/api/v1/phr/onboarding', accessToken: accessToken);
  }

  /// Partially saves, completes, or skips onboarding. [payload] carries an
  /// `action` of `save` | `complete` | `skip` plus any optional profile fields.
  Future<Map<String, dynamic>> updatePhrOnboarding({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _patch(
      '/api/v1/phr/onboarding',
      body: payload,
      accessToken: accessToken,
    );
  }

  // --- LifeMap / Today (clara-mobile-unified) -------------------------------

  /// Today agenda: accepted care tasks, open episodes, and the pending-
  /// confirmation count. Returns 409 when no PHR profile exists yet (the caller
  /// routes that to onboarding).
  Future<Map<String, dynamic>> getLifeMapToday({
    required String accessToken,
  }) {
    return _get('/api/v1/lifemap/today', accessToken: accessToken);
  }

  /// Creates a user-owned care episode. Mutations carry an `Idempotency-Key`.
  Future<Map<String, dynamic>> createLifeMapEpisode({
    required String accessToken,
    required String title,
    String goal = '',
    String priority = 'routine',
  }) {
    return _post(
      '/api/v1/lifemap/episodes',
      body: <String, dynamic>{
        'title': title,
        'goal': goal,
        'priority': priority,
      },
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  /// Proposes a task under an open episode.
  Future<Map<String, dynamic>> createLifeMapTask({
    required String accessToken,
    required String episodeId,
    required String title,
    String? dueAt,
  }) {
    return _post(
      '/api/v1/lifemap/episodes/$episodeId/tasks',
      body: <String, dynamic>{
        'title': title,
        if (dueAt != null) 'due_at': dueAt,
      },
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  /// Marks a proposed task accepted so it enters Today.
  Future<Map<String, dynamic>> acceptLifeMapTask({
    required String accessToken,
    required String taskId,
  }) {
    return _post(
      '/api/v1/lifemap/tasks/$taskId/accept',
      body: const <String, dynamic>{},
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  /// Marks an accepted task complete.
  Future<Map<String, dynamic>> completeLifeMapTask({
    required String accessToken,
    required String taskId,
    Map<String, dynamic> evidence = const <String, dynamic>{},
  }) {
    return _post(
      '/api/v1/lifemap/tasks/$taskId/complete',
      body: <String, dynamic>{'evidence': evidence},
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  /// Reads exact event revisions, provenance, decision versions, and stale
  /// markers for one episode.
  Future<Map<String, dynamic>> getLifeMapReplay({
    required String accessToken,
    required String episodeId,
  }) {
    return _get(
      '/api/v1/episodes/$episodeId/replay',
      accessToken: accessToken,
    );
  }

  /// Creates a replacement fact revision. Health mutations are online-only and
  /// guarded by both idempotency and optimistic concurrency.
  Future<Map<String, dynamic>> correctLifeMapEvent({
    required String accessToken,
    required String eventId,
    required int revision,
    required Map<String, dynamic> payload,
    required String reason,
  }) {
    return _post(
      '/api/v1/lifemap/events/$eventId/correct',
      body: <String, dynamic>{'payload': payload, 'reason': reason},
      accessToken: accessToken,
      extraHeaders: <String, String>{
        'Idempotency-Key': _idempotencyKey(),
        'If-Match': '$revision',
      },
    );
  }

  /// Opens an exact-revision dispute. This online-only mutation never deletes
  /// the source fact and creates a server-owned review case.
  Future<Map<String, dynamic>> disputeLifeMapEvent({
    required String accessToken,
    required String eventId,
    required int revision,
    required String reason,
  }) {
    return _post(
      '/api/v1/lifemap/events/$eventId/dispute',
      body: <String, dynamic>{'reason': reason},
      accessToken: accessToken,
      extraHeaders: <String, String>{
        'Idempotency-Key': _idempotencyKey(),
        'If-Match': '$revision',
      },
    );
  }

  Future<Map<String, dynamic>> resolveLifeMapEvent({
    required String accessToken,
    required String eventId,
    required int revision,
    required String reason,
  }) {
    return _post(
      '/api/v1/lifemap/events/$eventId/resolve',
      body: <String, dynamic>{'reason': reason},
      accessToken: accessToken,
      extraHeaders: <String, String>{
        'Idempotency-Key': _idempotencyKey(),
        'If-Match': '$revision',
      },
    );
  }

  Future<List<Map<String, dynamic>>> getLifeMapDisputes({
    required String accessToken,
  }) async {
    final response =
        await _get('/api/v1/lifemap/v2/disputes', accessToken: accessToken);
    return _asMapList(response['data']);
  }

  Future<Map<String, dynamic>> getLifeMapBaselines({
    required String accessToken,
  }) {
    return _get('/api/v1/lifemap/v2/baselines', accessToken: accessToken);
  }

  /// Read-only, revision-cited Ask My LifeMap query. The server owns intent,
  /// model, retrieval, policy, and safety routing.
  Future<Map<String, dynamic>> askLifeMap({
    required String accessToken,
    required String query,
    String? episodeId,
    String locale = 'vi',
  }) {
    return _post(
      '/api/v1/lifemap/v2/ask',
      body: <String, dynamic>{
        'query': query,
        'episode_id': episodeId,
        'locale': locale,
      },
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> scanLifeMapReviewFindings({
    required String accessToken,
  }) {
    return _post(
      '/api/v1/lifemap/v2/review-findings/scan',
      body: const <String, dynamic>{},
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> actOnLifeMapReviewFinding({
    required String accessToken,
    required String findingId,
    required String action,
    required String reason,
  }) {
    return _post(
      '/api/v1/lifemap/v2/review-findings/$findingId/actions',
      body: <String, dynamic>{'action': action, 'reason': reason},
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  Future<Map<String, dynamic>> getLifeMapNextQuestion({
    required String accessToken,
    required String episodeId,
    String locale = 'vi',
  }) {
    return _get(
      '/api/v1/episodes/$episodeId/next-question?locale=$locale',
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> recordLifeMapQuestionInteraction({
    required String accessToken,
    required String episodeId,
    required String questionId,
    required String action,
    String reason = '',
  }) {
    return _post(
      '/api/v1/episodes/$episodeId/questions/$questionId/interaction',
      body: <String, dynamic>{'action': action, 'reason': reason},
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  Future<Map<String, dynamic>> startLifeMapGuidedAnswer({
    required String accessToken,
    required String episodeId,
    required String questionId,
    required Map<String, dynamic> answer,
    String locale = 'vi',
  }) {
    return _post(
      '/api/v1/lifemap/capture/guided-answers',
      body: <String, dynamic>{
        'episode_id': episodeId,
        'question_id': questionId,
        'answer': answer,
        'locale': locale,
      },
      accessToken: accessToken,
    );
  }

  /// Creates a Universal Capture text draft. The server may return an
  /// emergency escalation with `persisted=false` before writing any content.
  Future<Map<String, dynamic>> startLifeMapTextCapture({
    required String accessToken,
    required String text,
    String locale = 'vi',
  }) {
    return _post(
      '/api/v1/lifemap/capture/sessions',
      body: <String, dynamic>{'text': text, 'locale': locale},
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> getLifeMapCaptureSession({
    required String accessToken,
    required String sessionId,
  }) {
    return _get(
      '/api/v1/lifemap/capture/sessions/$sessionId',
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> abandonLifeMapCaptureSession({
    required String accessToken,
    required String sessionId,
  }) {
    return _post(
      '/api/v1/lifemap/capture/sessions/$sessionId/abandon',
      body: const <String, dynamic>{},
      accessToken: accessToken,
    );
  }

  /// Applies an explicit online review action to one capture candidate.
  Future<Map<String, dynamic>> reviewLifeMapCaptureCandidate({
    required String accessToken,
    required String candidateId,
    required String action,
    Map<String, dynamic>? value,
    String reason = '',
    bool acceptNormalization = false,
  }) {
    return _post(
      '/api/v1/lifemap/capture/candidates/$candidateId/review',
      body: <String, dynamic>{
        'action': action,
        if (value != null) 'value': value,
        'reason': reason,
        'accept_normalization': acceptNormalization,
      },
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  Future<Map<String, dynamic>> getLifeMapCaptureNormalization({
    required String accessToken,
    required String candidateId,
  }) {
    return _get(
      '/api/v1/lifemap/capture/candidates/$candidateId/normalization',
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> startLifeMapArtifactCapture({
    required String accessToken,
    required String inputKind,
    String locale = 'vi',
  }) {
    return _post(
      '/api/v1/lifemap/capture/artifact-sessions',
      body: <String, dynamic>{
        'input_kind': inputKind,
        'locale': locale,
      },
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> uploadLifeMapCaptureArtifact({
    required String accessToken,
    required String sessionId,
    required List<int> bytes,
    required String filename,
  }) {
    return _postMultipart(
      '/api/v1/lifemap/capture/sessions/$sessionId/artifacts',
      fields: const <String, String>{},
      accessToken: accessToken,
      fileField: 'artifact',
      fileBytes: bytes,
      filename: filename,
    );
  }

  Future<Map<String, dynamic>> getLifeMapCaptureJob({
    required String accessToken,
    required String jobId,
  }) {
    return _get(
      '/api/v1/lifemap/capture/jobs/$jobId',
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> getLifeMapSummary({
    required String accessToken,
    required String level,
    String? episodeId,
    String locale = 'vi',
  }) {
    final query = Uri(
      queryParameters: <String, String>{
        'locale': locale,
        if (episodeId != null && episodeId.isNotEmpty) 'episode_id': episodeId,
      },
    ).query;
    return _get(
      '/api/v1/lifemap/v2/summaries/$level?$query',
      accessToken: accessToken,
    );
  }

  // --- Living Evidence ------------------------------------------------------

  Future<Map<String, dynamic>> createEvidenceQuestion({
    required String accessToken,
    required String episodeId,
    required String question,
    String populationContext = '',
    List<String> outcomes = const <String>[],
    String timeHorizon = '',
  }) {
    return _post(
      '/api/v1/episodes/$episodeId/evidence-questions',
      body: <String, dynamic>{
        'question': question,
        'population_context': populationContext,
        'outcomes': outcomes,
        'time_horizon': timeHorizon,
        'confirmed': false,
      },
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> confirmEvidenceQuestion({
    required String accessToken,
    required String questionId,
  }) {
    return _patch(
      '/api/v1/evidence-questions/$questionId',
      body: const <String, dynamic>{'confirmed': true},
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> runEvidenceQuestion({
    required String accessToken,
    required String questionId,
  }) {
    return _post(
      '/api/v1/evidence-questions/$questionId/run',
      body: const <String, dynamic>{},
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  Future<Map<String, dynamic>> getEvidenceRun({
    required String accessToken,
    required String runId,
  }) {
    return _get('/api/v1/evidence-runs/$runId', accessToken: accessToken);
  }

  Future<Map<String, dynamic>> getEvidenceApplicability({
    required String accessToken,
    required String runId,
  }) {
    return _get(
      '/api/v1/evidence-runs/$runId/applicability',
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> getEvidenceContradictions({
    required String accessToken,
    required String runId,
  }) {
    return _get(
      '/api/v1/evidence-runs/$runId/contradictions',
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> subscribeToEvidenceRun({
    required String accessToken,
    required String runId,
    int intervalHours = 168,
  }) {
    return _post(
      '/api/v1/evidence-runs/$runId/subscribe',
      body: <String, dynamic>{
        'delivery_channel': 'in_app',
        'interval_hours': intervalHours,
      },
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> getEvidenceSubscriptions({
    required String accessToken,
  }) {
    return _get('/api/v1/evidence-subscriptions', accessToken: accessToken);
  }

  Future<Map<String, dynamic>> updateEvidenceSubscription({
    required String accessToken,
    required String subscriptionId,
    required int intervalHours,
  }) {
    return _patch(
      '/api/v1/evidence-subscriptions/$subscriptionId',
      body: <String, dynamic>{'interval_hours': intervalHours},
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> revokeEvidenceSubscription({
    required String accessToken,
    required String subscriptionId,
  }) {
    return _delete(
      '/api/v1/evidence-subscriptions/$subscriptionId',
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> getEvidenceChangeNotifications({
    required String accessToken,
  }) {
    return _get(
      '/api/v1/evidence-change-notifications',
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> readEvidenceChangeNotification({
    required String accessToken,
    required String notificationId,
  }) {
    return _post(
      '/api/v1/evidence-change-notifications/$notificationId/read',
      body: const <String, dynamic>{},
      accessToken: accessToken,
    );
  }

  // --- Medication courses (clara-mobile-unified) ----------------------------

  /// Lists confirmed medication courses. Requires an existing PHR profile.
  Future<Map<String, dynamic>> getMedicationCourses({
    required String accessToken,
  }) {
    return _get('/api/v1/medication-courses', accessToken: accessToken);
  }

  /// Records a confirmed medication course (never inferred).
  Future<Map<String, dynamic>> createMedicationCourse({
    required String accessToken,
    required String medicationName,
    String doseText = '',
    String scheduleText = '',
    String routeText = '',
    String formText = '',
    String? drugbankId,
  }) {
    return _post(
      '/api/v1/medication-courses',
      body: <String, dynamic>{
        'medication_name': medicationName,
        'dose_text': doseText,
        'schedule_text': scheduleText,
        'route_text': routeText,
        'form_text': formText,
        if (drugbankId != null && drugbankId.isNotEmpty)
          'drugbank_id': drugbankId,
      },
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  /// Replaces a confirmed medication course with an explicitly corrected
  /// version. The API preserves the prior values in its append-only history.
  Future<Map<String, dynamic>> correctMedicationCourse({
    required String accessToken,
    required String courseId,
    required int version,
    required String medicationName,
    required String reason,
    String doseText = '',
    String scheduleText = '',
    String routeText = '',
    String formText = '',
  }) {
    return _post(
      '/api/v1/medication-courses/$courseId/correct',
      body: <String, dynamic>{
        'medication_name': medicationName,
        'dose_text': doseText,
        'schedule_text': scheduleText,
        'route_text': routeText,
        'form_text': formText,
        'reason': reason,
      },
      accessToken: accessToken,
      extraHeaders: <String, String>{
        'Idempotency-Key': _idempotencyKey(),
        'If-Match': '$version',
      },
    );
  }

  /// Records that a course ended. This is historical record-keeping and never
  /// advice to stop a medicine.
  Future<Map<String, dynamic>> endMedicationCourse({
    required String accessToken,
    required String courseId,
    required int version,
    required String reason,
    DateTime? endedAt,
  }) {
    return _post(
      '/api/v1/medication-courses/$courseId/end',
      body: <String, dynamic>{
        'reason': reason,
        if (endedAt != null) 'ended_at': endedAt.toUtc().toIso8601String(),
      },
      accessToken: accessToken,
      extraHeaders: <String, String>{
        'Idempotency-Key': _idempotencyKey(),
        'If-Match': '$version',
      },
    );
  }

  // --- Visits (clara-mobile-unified) ----------------------------------------

  /// Lists the user's visit-prep sessions. Requires an existing PHR profile
  /// (the server returns 409 when none exists yet — the caller routes that to
  /// onboarding). A visit helps prepare for a doctor's appointment; it is not
  /// medical advice or a diagnosis.
  Future<Map<String, dynamic>> getVisits({
    required String accessToken,
  }) {
    return _get('/api/v1/visits', accessToken: accessToken);
  }

  /// Fetches a single visit by id.
  Future<Map<String, dynamic>> getVisit(
    String visitId, {
    required String accessToken,
  }) {
    return _get('/api/v1/visits/$visitId', accessToken: accessToken);
  }

  /// Creates a visit-prep session from a user-authored payload.
  Future<Map<String, dynamic>> createVisit({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/visits',
      body: payload,
      accessToken: accessToken,
    );
  }

  /// Adds a concern to a visit.
  Future<Map<String, dynamic>> addVisitConcern({
    required String accessToken,
    required String visitId,
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/visits/$visitId/concerns',
      body: payload,
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  /// Submits intake answers for a visit.
  Future<Map<String, dynamic>> submitVisitIntakeAnswers({
    required String accessToken,
    required String visitId,
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/visits/$visitId/intake/answers',
      body: payload,
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  /// Generates the shareable visit pack (the prep summary for the appointment).
  Future<Map<String, dynamic>> createVisitPack({
    required String accessToken,
    required String visitId,
    required Map<String, dynamic> selection,
  }) {
    return _post(
      '/api/v1/visits/$visitId/pack',
      body: <String, dynamic>{'selection': selection},
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  Future<Map<String, dynamic>> getVisitPackOptions({
    required String accessToken,
    required String visitId,
  }) {
    return _get(
      '/api/v1/visits/$visitId/pack-options',
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> getVisitDocuments({
    required String accessToken,
    required String visitId,
  }) {
    return _get(
      '/api/v1/visits/$visitId/documents',
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> createVisitDocument({
    required String accessToken,
    required String visitId,
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/visits/$visitId/documents',
      body: payload,
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  Future<Map<String, dynamic>> withdrawVisitDocument({
    required String accessToken,
    required String visitId,
    required String documentId,
    String reason = 'owner_withdrew',
  }) {
    return _post(
      '/api/v1/visits/$visitId/documents/$documentId/withdraw',
      body: <String, dynamic>{'reason': reason},
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  Future<Map<String, dynamic>> deleteVisitDocument({
    required String accessToken,
    required String visitId,
    required String documentId,
    String reason = 'owner_requested_deletion',
  }) {
    return _delete(
      '/api/v1/visits/$visitId/documents/$documentId',
      body: <String, dynamic>{'reason': reason},
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> extractVisitPlan({
    required String accessToken,
    required String visitId,
    required String documentId,
  }) {
    return _post(
      '/api/v1/visits/$visitId/plan/extract',
      body: <String, dynamic>{'document_id': documentId},
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  Future<Map<String, dynamic>> confirmVisitPlan({
    required String accessToken,
    required String visitId,
    required String draftId,
    required List<String> candidateIds,
    String? episodeId,
  }) {
    return _post(
      '/api/v1/visits/$visitId/plan/confirm',
      body: <String, dynamic>{
        'draft_id': draftId,
        'candidate_ids': candidateIds,
        if (episodeId != null && episodeId.isNotEmpty) 'episode_id': episodeId,
      },
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  Future<Map<String, dynamic>> withdrawVisitPlan({
    required String accessToken,
    required String visitId,
    required String draftId,
    String reason = 'owner_withdrew',
  }) {
    return _post(
      '/api/v1/visits/$visitId/plan/$draftId/withdraw',
      body: <String, dynamic>{'reason': reason},
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  Future<Map<String, dynamic>> approveVisitPack({
    required String accessToken,
    required String packId,
  }) {
    return _post(
      '/api/v1/visit-packs/$packId/approve',
      body: const <String, dynamic>{},
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  Future<Map<String, dynamic>> shareVisitPack({
    required String accessToken,
    required String packId,
    required DateTime expiresAt,
  }) {
    return _post(
      '/api/v1/visit-packs/$packId/shares',
      body: <String, dynamic>{
        'expires_at': expiresAt.toUtc().toIso8601String(),
      },
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  Future<Map<String, dynamic>> revokeVisitShare({
    required String accessToken,
    required String packId,
    required String shareId,
  }) {
    return _delete(
      '/api/v1/visit-packs/$packId/shares/$shareId',
      accessToken: accessToken,
    );
  }

  Future<Map<String, dynamic>> grantVisitScribeConsent({
    required String accessToken,
    required String visitId,
  }) {
    return _post(
      '/api/v1/visits/$visitId/scribe-consents',
      body: const <String, dynamic>{
        'purpose': 'scribe_recording',
        'policy_version': 'visit-scribe-v1',
      },
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  Future<Map<String, dynamic>> revokeVisitScribeConsent({
    required String accessToken,
    required String visitId,
  }) {
    return _delete(
      '/api/v1/visits/$visitId/scribe-consents/scribe_recording',
      accessToken: accessToken,
    );
  }

  // --- Family (clara-mobile-unified) ----------------------------------------

  /// Lists the user's family relationships (minimal, consent-based sharing).
  Future<Map<String, dynamic>> getFamilyRelationships({
    required String accessToken,
  }) {
    return _get('/api/v1/family/relationships', accessToken: accessToken);
  }

  /// Lists pending family notifications awaiting acknowledgement.
  Future<Map<String, dynamic>> getFamilyNotifications({
    required String accessToken,
  }) {
    return _get('/api/v1/family/notifications', accessToken: accessToken);
  }

  /// Acknowledges ("Đã xem") a family notification for a given grant + task.
  Future<Map<String, dynamic>> acknowledgeFamilyNotification({
    required String accessToken,
    required String grantId,
    required String taskId,
    required String purpose,
  }) {
    return _post(
      '/api/v1/family/notifications/$grantId/$taskId/acknowledge',
      body: <String, dynamic>{'purpose': purpose},
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  /// Lists the active access grants shared with the user's supporters.
  Future<Map<String, dynamic>> getFamilyAccessGrants({
    required String accessToken,
  }) {
    return _get('/api/v1/family/access-grants', accessToken: accessToken);
  }

  /// Revokes a family access grant.
  Future<Map<String, dynamic>> revokeFamilyAccessGrant({
    required String accessToken,
    required String grantId,
  }) {
    return _delete(
      '/api/v1/family/access-grants/$grantId',
      accessToken: accessToken,
    );
  }

  /// Fetches the access log (who viewed what, and when).
  Future<Map<String, dynamic>> getFamilyAccessLog({
    required String accessToken,
  }) {
    return _get('/api/v1/family/access-log', accessToken: accessToken);
  }

  Future<Map<String, dynamic>> getFamilyShareOptions({
    required String accessToken,
  }) {
    return _get('/api/v1/family/share-options', accessToken: accessToken);
  }

  /// Invites a supporter to a minimal, consent-based sharing relationship.
  Future<Map<String, dynamic>> createFamilyInvitation({
    required String accessToken,
    required Map<String, dynamic> payload,
  }) {
    return _post(
      '/api/v1/family/invitations',
      body: payload,
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  /// Accepts a family invitation. The invitation token travels in the
  /// `X-Family-Invitation-Token` header rather than the URL.
  Future<Map<String, dynamic>> acceptFamilyInvitation({
    required String accessToken,
    required String invitationToken,
  }) {
    return _post(
      '/api/v1/family/invitations/accept',
      body: const <String, dynamic>{},
      accessToken: accessToken,
      extraHeaders: <String, String>{
        'X-Family-Invitation-Token': invitationToken,
      },
    );
  }

  Future<Map<String, dynamic>> renewFamilyAccessGrant({
    required String accessToken,
    required String grantId,
    required DateTime expiresAt,
  }) {
    return _post(
      '/api/v1/family/access-grants/$grantId/renewals',
      body: <String, dynamic>{
        'expires_at': expiresAt.toUtc().toIso8601String(),
      },
      accessToken: accessToken,
      extraHeaders: <String, String>{'Idempotency-Key': _idempotencyKey()},
    );
  }

  /// Applies the bounded [_requestTimeout] to a single request future, mapping a
  /// stalled request onto the existing [ApiException] type (Req 9.2). Additive:
  /// callers keep awaiting an `http.Response` exactly as before.
  Future<http.Response> _withTimeout(Future<http.Response> request) {
    return request.timeout(
      _requestTimeout,
      onTimeout: () => throw ApiException(message: _timeoutMessage),
    );
  }

  /// Sends an authenticated request with token-refresh resilience (Req 6.2,
  /// 6.3). [send] builds the request from whichever access token should be
  /// used (it may differ from [accessToken] after a refresh).
  ///
  /// Behavior:
  ///  * No hooks attached, or an unauthenticated request -> sent once, exactly
  ///    as before (back-compatible).
  ///  * Hooks attached + access token expired (pre-flight) -> refresh first,
  ///    then send with the new token.
  ///  * A `401` from the API -> a single refresh + one resend (no loop).
  ///  * A failed refresh (or no refresh token) -> session cleared and a
  ///    PII-free auth error is thrown to route the user to login.
  Future<Map<String, dynamic>> _sendAuthed(
    String? accessToken,
    Future<http.Response> Function(String? token) send,
  ) async {
    final hooks = authHooks;

    // Fast path: unauthenticated request or no refresh wiring — unchanged.
    if (hooks == null || accessToken == null || accessToken.isEmpty) {
      final response = await _withTimeout(send(accessToken));
      return _decodeResponse(response);
    }

    // Pre-flight expiry check: refresh proactively before spending a request
    // we know will be rejected (Req 6.2).
    var token = accessToken;
    if (hooks.isAccessTokenExpired) {
      final refreshed = await _attemptRefresh();
      if (refreshed == null) {
        throw _sessionExpiredError();
      }
      token = refreshed;
    }

    var response = await _withTimeout(send(token));

    // Single 401 retry: one refresh attempt, then one resend (Req 6.2). If the
    // resend is still 401, it falls through to _decodeResponse and surfaces as
    // a normal auth error — never an infinite refresh loop.
    if (response.statusCode == 401) {
      final refreshed = await _attemptRefresh();
      if (refreshed == null) {
        throw _sessionExpiredError();
      }
      response = await _withTimeout(send(refreshed));
    }

    return _decodeResponse(response);
  }

  /// Coalesces concurrent refreshes into one in-flight `POST /auth/refresh` and
  /// returns the new access token, or null when refresh is impossible/failed
  /// (in which case the session has already been cleared).
  Future<String?> _attemptRefresh() {
    final existing = _refreshInFlight;
    if (existing != null) {
      return existing;
    }
    final future = _doRefresh();
    _refreshInFlight = future;
    return future.whenComplete(() => _refreshInFlight = null);
  }

  Future<String?> _doRefresh() async {
    final hooks = authHooks;
    if (hooks == null) {
      return null;
    }

    final refreshToken = hooks.refreshToken;
    if (refreshToken == null || refreshToken.isEmpty) {
      // No refresh token to exchange -> clear and force re-login (Req 6.3).
      await hooks.onSessionCleared();
      return null;
    }

    http.Response response;
    try {
      response = await _withTimeout(
        _httpClient.post(
          Uri.parse('$_baseUrl/api/v1/auth/refresh'),
          headers: _headers(),
          body: jsonEncode({'refresh_token': refreshToken}),
        ),
      );
    } catch (_) {
      // Timeout / transport error during refresh -> clear (Req 6.3).
      await hooks.onSessionCleared();
      return null;
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      await hooks.onSessionCleared();
      return null;
    }

    Object? decoded;
    try {
      decoded = response.body.isEmpty ? null : jsonDecode(response.body);
    } catch (_) {
      decoded = null;
    }

    if (decoded is! Map<String, dynamic>) {
      await hooks.onSessionCleared();
      return null;
    }

    final newAccess = decoded['access_token'];
    if (newAccess is! String || newAccess.isEmpty) {
      // A 2xx without a usable token is treated as a failed refresh.
      await hooks.onSessionCleared();
      return null;
    }

    // Preserve the existing refresh token / role when the response omits them.
    final newRefresh = (decoded['refresh_token'] as String?) ?? refreshToken;
    final newRole = (decoded['role'] as String?) ?? hooks.role ?? 'normal';

    await hooks.onSessionRefreshed(
      accessToken: newAccess,
      refreshToken: newRefresh,
      role: newRole,
    );
    return newAccess;
  }

  /// PII-free, Vietnamese-first auth error raised when a session cannot be
  /// refreshed. The 401 status lets callers route to login (Req 6.3).
  ApiException _sessionExpiredError() => ApiException(
        statusCode: 401,
        message: 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
      );

  Future<Map<String, dynamic>> _post(
    String path, {
    required Map<String, dynamic> body,
    String? accessToken,
    Map<String, String>? extraHeaders,
  }) {
    return _sendAuthed(
      accessToken,
      (token) => _httpClient.post(
        Uri.parse('$_baseUrl$path'),
        headers: _headers(accessToken: token, extra: extraHeaders),
        body: jsonEncode(body),
      ),
    );
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
      final streamed = await _httpClient.send(request).timeout(
            _requestTimeout,
            onTimeout: () => throw ApiException(message: _timeoutMessage),
          );
      response = await http.Response.fromStream(streamed).timeout(
        _requestTimeout,
        onTimeout: () => throw ApiException(message: _timeoutMessage),
      );
    } on ApiException {
      rethrow;
    } catch (_) {
      throw ApiException(message: 'Không thể kết nối tới server.');
    }

    return _decodeResponse(response);
  }

  Future<Map<String, dynamic>> _put(
    String path, {
    required Map<String, dynamic> body,
    String? accessToken,
  }) {
    return _sendAuthed(
      accessToken,
      (token) => _httpClient.put(
        Uri.parse('$_baseUrl$path'),
        headers: _headers(accessToken: token),
        body: jsonEncode(body),
      ),
    );
  }

  Future<Map<String, dynamic>> _patch(
    String path, {
    required Map<String, dynamic> body,
    String? accessToken,
  }) {
    return _sendAuthed(
      accessToken,
      (token) => _httpClient.patch(
        Uri.parse('$_baseUrl$path'),
        headers: _headers(accessToken: token),
        body: jsonEncode(body),
      ),
    );
  }

  Future<Map<String, dynamic>> _delete(
    String path, {
    String? accessToken,
    Map<String, dynamic>? body,
  }) {
    return _sendAuthed(
      accessToken,
      (token) => _httpClient.delete(
        Uri.parse('$_baseUrl$path'),
        headers: _headers(accessToken: token),
        body: body == null ? null : jsonEncode(body),
      ),
    );
  }

  Future<Map<String, dynamic>> _get(
    String path, {
    String? accessToken,
  }) {
    return _sendAuthed(
      accessToken,
      (token) => _httpClient.get(
        Uri.parse('$_baseUrl$path'),
        headers: _headers(accessToken: token),
      ),
    );
  }

  Map<String, String> _headers(
      {String? accessToken, Map<String, String>? extra}) {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };

    if (accessToken != null && accessToken.isNotEmpty) {
      headers['Authorization'] = 'Bearer $accessToken';
    }

    if (extra != null) {
      headers.addAll(extra);
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

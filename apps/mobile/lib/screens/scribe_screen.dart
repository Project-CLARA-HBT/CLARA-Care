import 'package:flutter/material.dart';

import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/connectivity_service.dart';
import '../core/feature_flags.dart';
import '../core/research_telemetry_gate.dart' show stripTelemetryLabels;
import '../core/session_store.dart';
import '../widgets/error_retry_view.dart';
import '../widgets/offline_banner.dart';

// =============================================================================
// ScribeScreen — clara-mobile-feature-parity Tasks 6.2, 6.3, 6.4
// (Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7).
//
// The ambient-scribe surface: list / create scribe sessions, append a
// transcript (typed text or — when a recorder/file plugin supplies bytes — an
// uploaded audio clip), regenerate the SOAP note, and surface session status.
// It consumes the existing, additive `ApiClient` scribe methods
// (`listScribeSessions` / `createScribeSession` / `getScribeSession` /
// `transcribeScribeAudio` / `regenerateScribeSession` / `captureScribeConsent` /
// `revokeScribeConsent`) — no backend contract changes (Req 15.5).
//
//   * 4.1 Authorized role can create, list, and open scribe sessions.
//   * 4.2 Capture/upload audio and submit it to the transcribe endpoint,
//         appending the recognized text to the active session.
//   * 4.3 Regenerate + display the SOAP note and surface session status
//         (draft / ready / finalized / error).
//   * 4.4 Capture and allow revocation of scribe consent for a session BEFORE
//         audio is processed, and BLOCK processing when consent is absent
//         (task 6.3 — the consent-capture gate).
//   * 4.5 Sanitize backend-derived clinical text through `stripTelemetryLabels`
//         so internal jargon never reaches the End_User view, and never let
//         clinical free text reach analytics/telemetry (task 6.3).
//   * 4.6 Restrict scribe surfaces to roles authorized by CLARA_API
//         (doctor RBAC, fail-closed) and hide them for unauthorized roles.
//   * 4.7 Gated by `scribe_mobile_enabled`: hidden/inert when the flag is off.
//
// Gating layers (all fail-closed):
//   1. `scribe_mobile_enabled` flag off  -> inert placeholder, zero calls.
//   2. Role not doctor-authorized        -> "not authorized" placeholder, zero
//                                            calls.
//   3. Consent not captured for a session -> audio processing / transcription
//                                            blocked client-side (Req 4.4).
//
// Audio capture note (no recorder/file plugin in pubspec): the screen always
// offers the transcript-text path, and exposes an upload-bytes path only when
// the host injects an [audioBytesProvider] (e.g. a recorder/file-picker plugin
// wired in by the app, or a test). This keeps parity work additive and avoids
// adding a platform dependency.
// =============================================================================

/// Roles authorized to use the scribe surface, mirroring the server RBAC
/// (`require_roles("doctor")` on every `/api/v1/scribe/*` route). Matching is
/// case-insensitive; any other / missing / unparseable role is unauthorized
/// (fail-closed, Req 4.6).
const Set<String> kScribeAuthorizedRoles = <String>{'doctor'};

/// Whether [role] may access the scribe surface (Req 4.6). Fail-closed: a null,
/// empty, or unrecognized role is never authorized.
bool isScribeAuthorizedRole(String? role) {
  final normalized = role?.trim().toLowerCase();
  if (normalized == null || normalized.isEmpty) {
    return false;
  }
  return kScribeAuthorizedRoles.contains(normalized);
}

String _str(Object? value) => value == null ? '' : value.toString();

/// Vietnamese-first label for a session status (status conveyed by text, not
/// color alone — Req 10.5). Clearly distinguishes: Recording, Transcript ready,
/// Draft, Reviewed, Signed, Exported, Amended, Error.
String scribeStatusLabel(String status) {
  switch (status.trim().toLowerCase()) {
    case 'recording':
      return 'Đang ghi';
    case 'ready':
    case 'transcript_ready':
      return 'Bản ghi sẵn sàng';
    case 'draft':
    case '':
      return 'Bản nháp';
    case 'in_review':
    case 'reviewed':
    case 'finalized':
      return 'Đã duyệt';
    case 'signed':
      return 'Đã ký';
    case 'exported':
      return 'Đã xuất bản';
    case 'amended':
      return 'Bản sửa đổi';
    case 'error':
    case 'failed':
      return 'Lỗi xử lý';
    default:
      return status;
  }
}

/// Ordered SOAP section keys with Vietnamese-first bilingual labels. The server
/// normalizes both long (`subjective`) and short (`S`) keys; we prefer the long
/// form and fall back to the short one.
const List<List<String>> _kSoapSections = <List<String>>[
  <String>['subjective', 'S', 'Chủ quan (S)'],
  <String>['objective', 'O', 'Khách quan (O)'],
  <String>['assessment', 'A', 'Đánh giá (A)'],
  <String>['plan', 'P', 'Kế hoạch (P)'],
];

/// An End_User-safe scribe session projection. All clinical free text
/// (`transcript`, SOAP sections) is passed through [stripTelemetryLabels] so no
/// internal telemetry label survives into the rendered view (Req 4.5; P4).
class ScribeSessionView {
  ScribeSessionView({
    required this.id,
    required this.title,
    required this.status,
    required this.transcript,
    required this.soapSections,
  });

  final int id;
  final String title;
  final String status;

  /// Sanitized transcript text (telemetry labels stripped).
  final String transcript;

  /// Ordered (label, sanitized-text) SOAP sections with non-empty content.
  final List<MapEntry<String, String>> soapSections;

  bool get hasTranscript => transcript.isNotEmpty;
  bool get hasSoap => soapSections.isNotEmpty;

  factory ScribeSessionView.fromJson(Map<String, dynamic> json) {
    final soap = json['soap'];
    final sections = <MapEntry<String, String>>[];
    if (soap is Map) {
      for (final section in _kSoapSections) {
        final longKey = section[0];
        final shortKey = section[1];
        final label = section[2];
        final raw = soap[longKey] ?? soap[shortKey];
        // Clinical text is sanitized before it is ever shown (Req 4.5).
        final text = stripTelemetryLabels(_str(raw));
        if (text.isNotEmpty) {
          sections.add(MapEntry(label, text));
        }
      }
    }
    return ScribeSessionView(
      id: (json['id'] is num) ? (json['id'] as num).toInt() : 0,
      title: _str(json['title']).isEmpty ? 'Phiên không tên' : _str(json['title']),
      status: _str(json['status']),
      transcript: stripTelemetryLabels(_str(json['transcript'])),
      soapSections: sections,
    );
  }
}

/// Supplies audio bytes (and an optional filename) for the upload path. Returns
/// `null` when the host cancels / has no clip. The screen only renders the
/// upload affordance when this is provided, so no recorder/file plugin is
/// required to compile (see the audio-capture note above).
typedef ScribeAudioProvider = Future<ScribeAudioClip?> Function();

/// A captured/selected audio clip for the upload-bytes transcription path.
class ScribeAudioClip {
  const ScribeAudioClip({required this.bytes, this.filename});

  final List<int> bytes;
  final String? filename;
}

class ScribeScreen extends StatefulWidget {
  const ScribeScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.featureFlags,
    this.connectivity,
    this.audioProvider,
    this.analytics,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// Resolver for `scribe_mobile_enabled` (Req 4.7). When closed the screen is
  /// inert and makes no network calls, preserving the pre-feature app.
  final MobileFeatureFlagResolver featureFlags;

  /// Optional connectivity signal; when supplied, an offline banner is shown
  /// and processing/mutations are blocked offline with preserved input
  /// (Req 9.5).
  final ConnectivityService? connectivity;

  /// Optional audio-bytes source for the upload transcription path. When null
  /// (the default in a plugin-less build) only the transcript-text path is
  /// offered.
  final ScribeAudioProvider? audioProvider;

  /// Optional analytics client; defaults to the shared, consent/PII-guarded
  /// singleton. Injectable so tests can assert no clinical text is transmitted.
  final Analytics? analytics;

  @override
  State<ScribeScreen> createState() => _ScribeScreenState();
}

class _ScribeScreenState extends State<ScribeScreen> {
  static const _mutationGuard = OfflineMutationGuard();

  // Sessions list state.
  bool _listLoading = false;
  String? _listError;
  List<ScribeSessionView> _sessions = const [];

  // Active session detail state.
  ScribeSessionView? _active;
  bool _detailBusy = false;
  String? _detailError;

  // Consent gate (Req 4.4): false until the clinician captures consent for the
  // active session. Fail-closed — processing is blocked while false.
  bool _consentCaptured = false;

  final _appendController = TextEditingController();

  bool get _enabled => widget.featureFlags.scribeEnabled;
  bool get _authorized => isScribeAuthorizedRole(widget.sessionStore.role);
  bool get _isOnline => widget.connectivity?.currentValue ?? true;

  Analytics get _analytics => widget.analytics ?? getAnalyticsClient();

  @override
  void initState() {
    super.initState();
    if (_enabled && _authorized) {
      // Screen-view event carries no clinical content (Req 4.5, 11.5).
      _analytics.track('mobile_scribe_viewed');
      _loadSessions();
    }
  }

  @override
  void dispose() {
    _appendController.dispose();
    super.dispose();
  }

  String? get _token {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) return null;
    return token;
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  String? _requireToken() {
    final token = _token;
    if (token == null) {
      setState(() {
        _detailError = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
        _listError = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
      });
      return null;
    }
    return token;
  }

  // --- Sessions list (Req 4.1) ---------------------------------------------

  Future<void> _loadSessions() async {
    final token = _token;
    if (token == null) {
      setState(() {
        _listLoading = false;
        _listError = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
      });
      return;
    }
    setState(() {
      _listLoading = true;
      _listError = null;
    });
    try {
      final data = await widget.apiClient.listScribeSessions(accessToken: token);
      final raw = data['items'];
      final items = <ScribeSessionView>[];
      if (raw is List) {
        for (final item in raw) {
          if (item is Map) {
            items.add(ScribeSessionView.fromJson(item.cast<String, dynamic>()));
          }
        }
      }
      if (!mounted) return;
      setState(() => _sessions = items);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _listError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() =>
          _listError = 'Không thể tải danh sách phiên. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _listLoading = false);
      }
    }
  }

  Future<void> _createSession() async {
    if (!_isOnline) {
      _showSnack(kOfflineMutationBlockedMessage);
      return;
    }
    final title = await showDialog<String>(
      context: context,
      builder: (_) => const _NewSessionDialog(),
    );
    if (title == null) return;
    final token = _requireToken();
    if (token == null) return;

    setState(() {
      _detailBusy = true;
      _detailError = null;
    });
    await _mutationGuard.run(
      isOnline: _isOnline,
      mutate: () async {
        final data = await widget.apiClient.createScribeSession(
          accessToken: token,
          // No transcript and no auto-generate: an empty draft. Clinical text
          // is only added later, after consent is captured.
          payload: {'title': title, 'auto_generate_soap': false},
        );
        // Coarse, content-free analytics (Req 4.5, 11.5).
        _analytics.track('mobile_scribe_session_created');
        if (!mounted) return;
        _openSessionView(ScribeSessionView.fromJson(data));
      },
      onBlocked: _showSnack,
    );
    if (mounted) {
      setState(() => _detailBusy = false);
    }
  }

  // --- Session detail ------------------------------------------------------

  Future<void> _openSession(ScribeSessionView summary) async {
    final token = _requireToken();
    if (token == null) return;
    setState(() {
      _detailBusy = true;
      _detailError = null;
    });
    try {
      final data = await widget.apiClient
          .getScribeSession(accessToken: token, sessionId: summary.id);
      if (!mounted) return;
      _openSessionView(ScribeSessionView.fromJson(data));
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _detailError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _detailError = 'Không thể mở phiên. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _detailBusy = false);
      }
    }
  }

  /// Switches to the detail view for [view]. Consent always resets to absent on
  /// open, so processing is blocked until the clinician captures it in-session
  /// (fail-closed, Req 4.4).
  void _openSessionView(ScribeSessionView view) {
    setState(() {
      _active = view;
      _consentCaptured = false;
      _appendController.clear();
      _detailError = null;
    });
  }

  void _closeSession() {
    setState(() {
      _active = null;
      _consentCaptured = false;
      _detailError = null;
      _appendController.clear();
    });
    _loadSessions();
  }

  // --- Consent gate (Req 4.4, task 6.3) ------------------------------------

  Future<void> _captureConsent() async {
    final active = _active;
    if (active == null) return;
    if (!_isOnline) {
      _showSnack(kOfflineMutationBlockedMessage);
      return;
    }
    final token = _requireToken();
    if (token == null) return;
    setState(() {
      _detailBusy = true;
      _detailError = null;
    });
    await _mutationGuard.run(
      isOnline: _isOnline,
      mutate: () async {
        await widget.apiClient
            .captureScribeConsent(accessToken: token, sessionId: active.id);
        _analytics.track('mobile_scribe_consent_captured');
        if (!mounted) return;
        setState(() => _consentCaptured = true);
      },
      onBlocked: _showSnack,
    );
    if (mounted) {
      setState(() => _detailBusy = false);
    }
  }

  Future<void> _revokeConsent() async {
    final active = _active;
    if (active == null) return;
    if (!_isOnline) {
      _showSnack(kOfflineMutationBlockedMessage);
      return;
    }
    final token = _requireToken();
    if (token == null) return;
    setState(() {
      _detailBusy = true;
      _detailError = null;
    });
    try {
      await widget.apiClient
          .revokeScribeConsent(accessToken: token, sessionId: active.id);
      _analytics.track('mobile_scribe_consent_revoked');
      if (!mounted) return;
      // Revoking re-blocks all further processing (Req 4.4).
      setState(() => _consentCaptured = false);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _detailError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _detailError = 'Không thể thu hồi đồng ý. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _detailBusy = false);
      }
    }
  }

  // --- Audio / transcript processing (Req 4.2, 4.3) ------------------------

  /// The single client-side gate for every processing path: consent must be
  /// captured (Req 4.4) and the device must be online (Req 9.5). Returns true
  /// when processing may proceed; otherwise surfaces a message and returns
  /// false WITHOUT performing any work or touching entered input.
  bool _canProcess() {
    if (!_consentCaptured) {
      _showSnack(
        'Cần thu thập sự đồng ý của bệnh nhân trước khi xử lý âm thanh hoặc '
        'lời thoại.',
      );
      return false;
    }
    if (!_isOnline) {
      _showSnack(kOfflineMutationBlockedMessage);
      return false;
    }
    return true;
  }

  /// Uploads an audio clip to the transcribe endpoint and appends the
  /// recognized text to the active session (Req 4.2). Blocked entirely until
  /// consent is captured (Req 4.4).
  Future<void> _uploadAudio() async {
    final active = _active;
    final provider = widget.audioProvider;
    if (active == null || provider == null) return;
    // Consent + connectivity gate is evaluated BEFORE any audio is requested or
    // processed (Req 4.4).
    if (!_canProcess()) return;

    final clip = await provider();
    if (clip == null || clip.bytes.isEmpty) return;
    final token = _requireToken();
    if (token == null) return;

    setState(() {
      _detailBusy = true;
      _detailError = null;
    });
    try {
      await widget.apiClient.transcribeScribeAudio(
        accessToken: token,
        audioBytes: clip.bytes,
        filename: clip.filename,
        sessionId: active.id,
        appendToSession: true,
      );
      // Coarse, content-free analytics — never the recognized text (Req 4.5).
      _analytics.track('mobile_scribe_audio_processed');
      // Reload to pick up the appended transcript (sanitized on parse).
      await _reloadActive(token, active.id);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _detailError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _detailError = 'Không thể xử lý âm thanh. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _detailBusy = false);
      }
    }
  }

  /// Appends typed transcript text and regenerates the SOAP note (Req 4.2,
  /// 4.3). Blocked until consent is captured (Req 4.4).
  Future<void> _appendTranscriptAndRegenerate() async {
    final active = _active;
    if (active == null) return;
    final addition = _appendController.text.trim();
    if (addition.isEmpty) {
      _showSnack('Vui lòng nhập nội dung lời thoại để bổ sung.');
      return;
    }
    if (!_canProcess()) return;
    final token = _requireToken();
    if (token == null) return;

    // Combine the existing (already-sanitized) transcript with the new text.
    final combined = active.transcript.isEmpty
        ? addition
        : '${active.transcript}\n$addition';

    setState(() {
      _detailBusy = true;
      _detailError = null;
    });
    try {
      final data = await widget.apiClient.regenerateScribeSession(
        accessToken: token,
        sessionId: active.id,
        payload: {'transcript': combined},
      );
      _analytics.track('mobile_scribe_soap_regenerated');
      if (!mounted) return;
      setState(() {
        _active = ScribeSessionView.fromJson(data);
        _appendController.clear();
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _detailError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _detailError = 'Không thể tạo lại SOAP. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _detailBusy = false);
      }
    }
  }

  /// Regenerates the SOAP note from the session's stored transcript (Req 4.3).
  Future<void> _regenerateSoap() async {
    final active = _active;
    if (active == null) return;
    if (!active.hasTranscript) {
      _showSnack('Chưa có lời thoại để tạo SOAP.');
      return;
    }
    if (!_canProcess()) return;
    final token = _requireToken();
    if (token == null) return;

    setState(() {
      _detailBusy = true;
      _detailError = null;
    });
    try {
      final data = await widget.apiClient
          .regenerateScribeSession(accessToken: token, sessionId: active.id);
      _analytics.track('mobile_scribe_soap_regenerated');
      if (!mounted) return;
      setState(() => _active = ScribeSessionView.fromJson(data));
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _detailError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _detailError = 'Không thể tạo lại SOAP. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _detailBusy = false);
      }
    }
  }

  Future<void> _reloadActive(String token, int sessionId) async {
    final data =
        await widget.apiClient.getScribeSession(accessToken: token, sessionId: sessionId);
    if (!mounted) return;
    setState(() => _active = ScribeSessionView.fromJson(data));
  }

  // --- Build ---------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ghi chú lâm sàng (Scribe)'),
        leading: _active != null
            ? IconButton(
                icon: const Icon(Icons.arrow_back),
                tooltip: 'Danh sách phiên',
                onPressed: _detailBusy ? null : _closeSession,
              )
            : null,
      ),
      floatingActionButton: (_enabled && _authorized && _active == null)
          ? FloatingActionButton.extended(
              onPressed: _detailBusy ? null : _createSession,
              icon: const Icon(Icons.add),
              label: const Text('Phiên mới'),
            )
          : null,
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (!_enabled) {
      return const _ScribePlaceholder(
        message: 'Tính năng ghi chú lâm sàng chưa được bật.',
      );
    }
    if (!_authorized) {
      // Fail-closed RBAC: unauthorized roles see no scribe content and trigger
      // no calls (Req 4.6).
      return const _ScribePlaceholder(
        message: 'Tài khoản của bạn không có quyền sử dụng tính năng này.',
      );
    }
    final connectivity = widget.connectivity;
    final content = _active == null
        ? _buildSessionList(context)
        : _buildSessionDetail(context, _active!);
    if (connectivity == null) {
      return content;
    }
    return Column(
      children: [
        OfflineBanner(connectivity: connectivity),
        Expanded(child: content),
      ],
    );
  }

  Widget _buildSessionList(BuildContext context) {
    if (_listError != null) {
      return ErrorRetryView(message: _listError!, onRetry: _loadSessions);
    }
    return RefreshIndicator(
      onRefresh: _loadSessions,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        children: [
          if (_listLoading) const LinearProgressIndicator(),
          if (!_listLoading && _sessions.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Center(
                child: Text('Chưa có phiên nào. Tạo phiên mới để bắt đầu.'),
              ),
            ),
          ..._sessions.map(_buildSessionTile),
        ],
      ),
    );
  }

  Widget _buildSessionTile(ScribeSessionView session) {
    return Card(
      child: ListTile(
        title: Text(session.title),
        subtitle: Text('Trạng thái: ${scribeStatusLabel(session.status)}'),
        trailing: const Icon(Icons.chevron_right),
        onTap: _detailBusy ? null : () => _openSession(session),
      ),
    );
  }

  int _computeCurrentStep(ScribeSessionView session, bool consentCaptured) {
    final status = session.status.trim().toLowerCase();
    if (status == 'signed' || status == 'exported' || status == 'amended') {
      return 5;
    }
    if (status == 'finalized' || status == 'in_review' || status == 'reviewed' || status == 'completed') {
      return 4;
    }
    if (session.hasSoap) {
      return 3;
    }
    if (session.hasTranscript) {
      return 2;
    }
    if (consentCaptured) {
      return 1;
    }
    return 0;
  }

  Widget _buildSessionDetail(BuildContext context, ScribeSessionView session) {
    final theme = Theme.of(context);
    final canUploadAudio = widget.audioProvider != null;
    final currentStep = _computeCurrentStep(session, _consentCaptured);
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Expanded(child: Text(session.title, style: theme.textTheme.titleLarge)),
            const SizedBox(width: 8),
            Semantics(
              label: 'Trạng thái phiên: ${scribeStatusLabel(session.status)}',
              child: Chip(label: Text('Trạng thái: ${scribeStatusLabel(session.status)}')),
            ),
          ],
        ),
        const SizedBox(height: 8),

        // Canonical 6-stage Scribe state model: Consent -> Capture -> Transcript Review -> SOAP Review -> Draft Complete -> Export/Sign
        _ScribeWorkflowStepperCard(currentStep: currentStep),
        const SizedBox(height: 8),

        // Consent-capture gate (Req 4.4).
        _ConsentGateCard(
          captured: _consentCaptured,
          busy: _detailBusy,
          onCapture: _captureConsent,
          onRevoke: _revokeConsent,
        ),
        const SizedBox(height: 8),

        if (_detailError != null) ...[
          Text(
            _detailError!,
            style: TextStyle(color: theme.colorScheme.error),
          ),
          const SizedBox(height: 8),
        ],

        // Transcript (sanitized) — Req 4.2, 4.5.
        Text('Lời thoại', style: theme.textTheme.titleMedium),
        const SizedBox(height: 4),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Text(
              session.hasTranscript ? session.transcript : '(Chưa có lời thoại)',
              key: const Key('scribe-transcript'),
            ),
          ),
        ),
        const SizedBox(height: 16),

        // Add transcript text (always available once consent is captured).
        TextField(
          controller: _appendController,
          minLines: 2,
          maxLines: 6,
          enabled: !_detailBusy,
          decoration: const InputDecoration(
            labelText: 'Bổ sung lời thoại',
            border: OutlineInputBorder(),
            hintText: 'Nhập hoặc dán nội dung trao đổi để thêm vào phiên',
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 12,
          runSpacing: 8,
          children: [
            FilledButton.icon(
              onPressed: _detailBusy ? null : _appendTranscriptAndRegenerate,
              icon: const Icon(Icons.note_add_outlined),
              label: const Text('Thêm & tạo SOAP'),
            ),
            if (canUploadAudio)
              OutlinedButton.icon(
                key: const Key('scribe-upload-audio'),
                onPressed: _detailBusy ? null : _uploadAudio,
                icon: const Icon(Icons.mic_none),
                label: const Text('Tải âm thanh'),
              ),
            OutlinedButton.icon(
              onPressed: _detailBusy ? null : _regenerateSoap,
              icon: const Icon(Icons.refresh),
              label: const Text('Tạo lại SOAP'),
            ),
          ],
        ),
        if (!canUploadAudio) ...[
          const SizedBox(height: 8),
          Text(
            'Ghi âm/tải tệp âm thanh chưa khả dụng trên bản dựng này; hãy nhập '
            'lời thoại bằng văn bản.',
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
        ],
        const SizedBox(height: 20),

        // SOAP note (sanitized) — Req 4.3, 4.5.
        Text('Ghi chú SOAP', style: theme.textTheme.titleMedium),
        const SizedBox(height: 6),
        if (!session.hasSoap)
          const Text('(Chưa có ghi chú SOAP)')
        else
          ...session.soapSections.map(
            (entry) => Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(entry.key,
                        style: theme.textTheme.titleSmall),
                    const SizedBox(height: 4),
                    Text(entry.value),
                  ],
                ),
              ),
            ),
          ),
        if (_detailBusy) ...[
          const SizedBox(height: 16),
          const Center(child: CircularProgressIndicator()),
        ],
      ],
    );
  }
}

/// Inert placeholder used when the flag is off or the role is unauthorized
/// (Req 4.6, 4.7). Renders no scribe content and triggers no network calls.
class _ScribePlaceholder extends StatelessWidget {
  const _ScribePlaceholder({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(message, textAlign: TextAlign.center),
      ),
    );
  }
}

/// The consent-capture gate card (Req 4.4, task 6.3). While consent is absent
/// it makes clear that audio processing is blocked; capturing unlocks
/// processing and revoking re-blocks it.
class _ConsentGateCard extends StatelessWidget {
  const _ConsentGateCard({
    required this.captured,
    required this.busy,
    required this.onCapture,
    required this.onRevoke,
  });

  final bool captured;
  final bool busy;
  final VoidCallback onCapture;
  final VoidCallback onRevoke;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      key: const Key('scribe-consent-gate'),
      color: captured
          ? theme.colorScheme.surfaceContainerHighest
          : theme.colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                ExcludeSemantics(
                  child: Icon(
                    captured ? Icons.verified_user : Icons.gpp_maybe,
                    color: captured
                        ? theme.colorScheme.onSurfaceVariant
                        : theme.colorScheme.onErrorContainer,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    captured
                        ? 'Đã thu thập sự đồng ý của bệnh nhân.'
                        : 'Chưa có sự đồng ý. Việc xử lý âm thanh/lời thoại đang bị '
                            'chặn cho đến khi thu thập được sự đồng ý.',
                    style: TextStyle(
                      color: captured
                          ? theme.colorScheme.onSurfaceVariant
                          : theme.colorScheme.onErrorContainer,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (!captured)
              Semantics(
                button: true,
                label: 'Thu thập sự đồng ý',
                child: FilledButton(
                  onPressed: busy ? null : onCapture,
                  style: FilledButton.styleFrom(
                    minimumSize:
                        const Size(kMinTouchTarget, kMinTouchTarget),
                  ),
                  child: const Text('Thu thập sự đồng ý'),
                ),
              )
            else
              Semantics(
                button: true,
                label: 'Thu hồi sự đồng ý',
                child: OutlinedButton(
                  onPressed: busy ? null : onRevoke,
                  style: OutlinedButton.styleFrom(
                    minimumSize:
                        const Size(kMinTouchTarget, kMinTouchTarget),
                  ),
                  child: const Text('Thu hồi sự đồng ý'),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Canonical 6-stage Scribe state model:
/// Consent -> Capture -> Transcript Review -> SOAP Review -> Draft Complete -> Export/Sign
class _ScribeWorkflowStepperCard extends StatelessWidget {
  const _ScribeWorkflowStepperCard({
    required this.currentStep,
  });

  final int currentStep;

  static const List<String> _steps = <String>[
    'Đồng thuận',
    'Ghi âm',
    'Kiểm tra bản ghi',
    'Kiểm tra SOAP',
    'Hoàn tất bản nháp',
    'Ký & Xuất bản',
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Semantics(
      label: 'Quy trình xử lý Scribe',
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: List.generate(_steps.length, (index) {
                final isCompleted = index < currentStep;
                final isCurrent = index == currentStep;
                final label = _steps[index];

                Color circleBg;
                Color circleFg;
                Color textColor;
                FontWeight fontWeight;

                if (isCompleted) {
                  circleBg = colorScheme.primaryContainer;
                  circleFg = colorScheme.onPrimaryContainer;
                  textColor = colorScheme.onSurface;
                  fontWeight = FontWeight.w500;
                } else if (isCurrent) {
                  circleBg = colorScheme.primary;
                  circleFg = colorScheme.onPrimary;
                  textColor = colorScheme.primary;
                  fontWeight = FontWeight.bold;
                } else {
                  circleBg = colorScheme.surfaceContainerHighest;
                  circleFg = colorScheme.onSurfaceVariant;
                  textColor = colorScheme.onSurfaceVariant;
                  fontWeight = FontWeight.normal;
                }

                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 22,
                        height: 22,
                        decoration: BoxDecoration(
                          color: circleBg,
                          shape: BoxShape.circle,
                          border: isCurrent
                              ? Border.all(color: colorScheme.primary, width: 1.5)
                              : null,
                        ),
                        alignment: Alignment.center,
                        child: isCompleted
                            ? Icon(Icons.check, size: 13, color: circleFg)
                            : Text(
                                '${index + 1}',
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  color: circleFg,
                                ),
                              ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        label,
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: textColor,
                          fontWeight: fontWeight,
                        ),
                      ),
                      if (index < _steps.length - 1) ...[
                        const SizedBox(width: 6),
                        Icon(
                          Icons.chevron_right,
                          size: 14,
                          color: colorScheme.outlineVariant,
                        ),
                      ],
                    ],
                  ),
                );
              }),
            ),
          ),
        ),
      ),
    );
  }
}

/// Small dialog to name a new scribe session. Returns the trimmed title or
/// `null` when cancelled.
class _NewSessionDialog extends StatefulWidget {
  const _NewSessionDialog();

  @override
  State<_NewSessionDialog> createState() => _NewSessionDialogState();
}

class _NewSessionDialogState extends State<_NewSessionDialog> {
  final _controller = TextEditingController(text: 'Phiên khám mới');

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Tạo phiên mới'),
      content: TextField(
        controller: _controller,
        autofocus: true,
        decoration: const InputDecoration(
          labelText: 'Tên phiên',
          border: OutlineInputBorder(),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Hủy'),
        ),
        FilledButton(
          onPressed: () {
            final title = _controller.text.trim();
            Navigator.of(context).pop(title.isEmpty ? 'Phiên khám mới' : title);
          },
          child: const Text('Tạo'),
        ),
      ],
    );
  }
}

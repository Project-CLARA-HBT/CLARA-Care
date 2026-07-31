// Medical Scribe surface for the CLARA_Mobile redesign (Experience_V3).
//
// clara-mobile-redesign, Task 8: a polished, light-first "Ghi chú lâm sàng"
// (clinical scribe) surface built on the shared `ClaraTokens` design system.
// It is a modern reskin of the legacy `scribe_screen.dart` flow — session list
// + detail, per-session consent capture, transcript append, and SOAP
// regeneration — with every safety gate preserved and no CLARA_API contract
// change (INV-8).
//
// It reuses the legacy screen's public, End_User-safe projection
// (`ScribeSessionView`, which passes all clinical free text through
// `stripTelemetryLabels` on parse — INV / Req 4.5) and the Vietnamese-first
// `scribeStatusLabel` helper, so no sanitization logic is duplicated.
//
// Safety invariants (all fail-closed; regression-locked):
//   1. Flag gate — `scribe_mobile_enabled` (`resolver.scribeEnabled`) off ⇒
//      inert placeholder, ZERO network calls.
//   2. Role gate — only `doctor` OR `admin` (the redesign enables Scribe for
//      admin too); any other/missing role ⇒ placeholder, ZERO network calls.
//   3. Per-session consent gate (INV-2) — a session's patient consent must be
//      captured BEFORE any processing (transcript append / SOAP regenerate);
//      absent consent blocks processing client-side. Consent resets to absent
//      on every open, so processing is blocked until captured in-session.
//
// Clinical text is only ever shown after `stripTelemetryLabels` (via
// `ScribeSessionView`) and is NEVER sent to analytics — only coarse, no-PII
// `mobile_scribe_*` event names are emitted (Req 4.5). Mutations are blocked
// while offline with the user's typed input preserved (Req 9.5).
//
// Audio note: there is no recorder/file plugin in pubspec, so this surface
// offers only the text-transcript path (append + regenerate). No audio
// affordance and no recorder dependency are added.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../core/analytics.dart';
import '../../core/api_client.dart';
import '../../core/connectivity_service.dart';
import '../../core/feature_flags.dart';
import '../../core/session_store.dart';
import '../../screens/scribe_screen.dart'
    show ScribeSessionView, scribeStatusLabel;
import '../../theme/components/clara_button.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/clara_input.dart';
import '../../theme/components/section_header.dart';
import '../../theme/glass/glass_surface.dart';
import '../../theme/glass/glass_tokens.dart';
import '../../theme/tokens.dart';
import '../../widgets/error_retry_view.dart';
import '../../widgets/offline_banner.dart';
import '../states/empty_state.dart';
import '../states/skeleton.dart';

// --- Analytics event names (coarse, no-PII — Req 4.5) ------------------------
// Reuse the legacy screen's content-free event literals so telemetry stays
// consistent across the two surfaces. No clinical text is ever attached.
const String _kEvtViewed = 'mobile_scribe_viewed';
const String _kEvtSessionCreated = 'mobile_scribe_session_created';
const String _kEvtConsentCaptured = 'mobile_scribe_consent_captured';
const String _kEvtConsentRevoked = 'mobile_scribe_consent_revoked';
const String _kEvtSoapRegenerated = 'mobile_scribe_soap_regenerated';

/// Roles authorized for the redesigned Scribe surface. The redesign widens the
/// legacy `doctor`-only RBAC to also include `admin` (which has implicit access
/// across CLARA). Matching is case-insensitive; any other / missing /
/// unparseable role is unauthorized (fail-closed).
bool _isScribeAuthorizedRoleV3(String? role) {
  final normalized = role?.trim().toLowerCase();
  if (normalized == null || normalized.isEmpty) {
    return false;
  }
  return normalized == 'doctor' || normalized == 'admin';
}

/// Maps a scribe session status to a color-independent status level so meaning
/// is conveyed by text + icon, not color alone (Req 10.5).
A11yStatusLevel _statusLevel(String status) {
  switch (status.trim().toLowerCase()) {
    case 'ready':
    case 'finalized':
      return A11yStatusLevel.success;
    case 'error':
      return A11yStatusLevel.danger;
    default:
      return A11yStatusLevel.info;
  }
}

/// Locale-aware fixed copy for transcript and SOAP actions. Transcript and SOAP
/// content itself remains the already-sanitized, authoritative session data.
class _ScribeTranscriptCopy {
  const _ScribeTranscriptCopy._(this._english);

  factory _ScribeTranscriptCopy.forContext(BuildContext context) {
    final language = Localizations.localeOf(context).languageCode.toLowerCase();
    return _ScribeTranscriptCopy._(language == 'en');
  }

  final bool _english;

  String get consentRequired => _english
      ? 'Patient consent must be captured before transcript processing.'
      : 'Cần thu thập sự đồng ý của bệnh nhân trước khi xử lý lời thoại.';
  String get offlineBlocked => _english
      ? 'You are offline. This change is paused and your input is kept. Try again when connected.'
      : 'Không có kết nối mạng. Thao tác đã được tạm dừng — dữ liệu bạn nhập vẫn được giữ lại. Vui lòng thử lại khi có mạng.';
  String get transcriptRequired => _english
      ? 'Enter transcript text to add.'
      : 'Vui lòng nhập nội dung lời thoại để bổ sung.';
  String get soapUnavailable => _english
      ? 'There is no transcript yet to create a SOAP note.'
      : 'Chưa có lời thoại để tạo ghi chú SOAP.';
  String get regenerateFailed => _english
      ? 'We could not regenerate the SOAP note. Try again.'
      : 'Không thể tạo lại SOAP. Vui lòng thử lại.';
  String get sessionStatusPrefix => _english ? 'Session status' : 'Trạng thái phiên';
  String get errorPrefix => _english ? 'Error' : 'Lỗi';
  String get transcriptTitle => _english ? 'Transcript' : 'Lời thoại';
  String get transcriptSemantic => _english ? 'Session transcript' : 'Lời thoại của phiên';
  String get noTranscript => _english ? '(No transcript yet)' : '(Chưa có lời thoại)';
  String get appendLabel => _english ? 'Add transcript' : 'Bổ sung lời thoại';
  String get appendHint => _english
      ? 'Type or paste discussion text to add to this session'
      : 'Nhập hoặc dán nội dung trao đổi để thêm vào phiên';
  String get appendAndRegenerate => _english ? 'Add & create note' : 'Thêm & tạo ghi chú';
  String get regenerate => _english ? 'Regenerate note (SOAP)' : 'Tạo lại ghi chú (SOAP)';
  String get audioUnavailable => _english
      ? 'Audio recording and file upload are not available in this build; enter the transcript as text.'
      : 'Ghi âm/tải tệp âm thanh chưa khả dụng trên bản dựng này; hãy nhập lời thoại bằng văn bản.';
  String get soapTitle => _english ? 'SOAP note' : 'Ghi chú SOAP';
  String get soapSemantic => _english ? 'SOAP note' : 'Ghi chú SOAP';
  String get noSoap => _english ? '(No SOAP note yet)' : '(Chưa có ghi chú SOAP)';
}

/// Locale-aware fixed chrome for the session list and its creation dialog.
/// Session titles and server-provided clinical text are rendered unchanged.
class _ScribeSessionCopy {
  const _ScribeSessionCopy._(this._english);

  factory _ScribeSessionCopy.forContext(BuildContext context) {
    final language = Localizations.localeOf(context).languageCode.toLowerCase();
    return _ScribeSessionCopy._(language == 'en');
  }

  final bool _english;

  String get sessionExpired => _english
      ? 'Your session has expired. Please sign in again.'
      : 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
  String get sessionsLoadFailed => _english
      ? 'We could not load the sessions. Try again.'
      : 'Không thể tải danh sách phiên. Vui lòng thử lại.';
  String get sessionOpenFailed => _english
      ? 'We could not open this session. Try again.'
      : 'Không thể mở phiên. Vui lòng thử lại.';
  String get offlineBlocked => _english
      ? 'You are offline. This change is paused and your input is kept. Try again when connected.'
      : 'Không có kết nối mạng. Thao tác đã được tạm dừng — dữ liệu bạn nhập vẫn được giữ lại. Vui lòng thử lại khi có mạng.';
  String get appTitle => _english ? 'Clinical notes' : 'Ghi chú lâm sàng';
  String get backToSessions => _english ? 'Session list' : 'Danh sách phiên';
  String get createSession => _english ? 'Create session' : 'Tạo phiên mới';
  String get unavailable => _english ? 'Unavailable' : 'Không khả dụng';
  String get featureDisabled => _english
      ? 'The clinical-notes feature is not enabled.'
      : 'Tính năng ghi chú lâm sàng chưa được bật.';
  String get doctorOnly => _english
      ? 'This feature is available only to doctors.'
      : 'Tính năng này chỉ dành cho bác sĩ.';
  String get sessionsTitle => _english ? 'Note sessions' : 'Phiên ghi chú';
  String get emptyTitle => _english ? 'No sessions yet' : 'Chưa có phiên nào';
  String get emptyDescription => _english
      ? 'Create a new session to start clinical notes for a visit.'
      : 'Tạo phiên mới để bắt đầu ghi chú lâm sàng cho một lần khám.';
  String sessionSemantic(String title, String status) => _english
      ? 'Session: $title. Status: $status'
      : 'Phiên: $title. Trạng thái: $status';
  String get statusPrefix => _english ? 'Status' : 'Trạng thái';
  String statusLabel(String status) {
    if (!_english) return scribeStatusLabel(status);
    switch (status.trim().toLowerCase()) {
      case 'draft':
      case '':
        return 'Draft';
      case 'ready':
        return 'Ready';
      case 'finalized':
        return 'Finalized';
      case 'error':
        return 'Processing error';
      default:
        return status;
    }
  }
  String get dialogTitle => _english ? 'Create session' : 'Tạo phiên mới';
  String get sessionName => _english ? 'Session name' : 'Tên phiên';
  String get sessionHint => _english
      ? 'For example: This morning\'s visit'
      : 'Ví dụ: Phiên khám sáng nay';
  String get cancel => _english ? 'Cancel' : 'Hủy';
  String get create => _english ? 'Create' : 'Tạo';
  String get defaultSessionName => _english ? 'New visit session' : 'Phiên khám mới';
}

/// The redesigned Medical Scribe surface. See file header.
class ScribeSurfaceV3 extends StatefulWidget {
  const ScribeSurfaceV3({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.resolver,
    ConnectivityService? connectivity,
    Analytics? analytics,
  })  : _connectivity = connectivity,
        _analytics = analytics;

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final MobileFeatureFlagResolver resolver;

  /// Optional connectivity signal. When omitted a default (always-online in the
  /// absence of a probe) service is created; tests inject a fake to drive the
  /// offline path.
  final ConnectivityService? _connectivity;

  /// Optional analytics client; defaults to the shared, consent/PII-guarded
  /// singleton. Injectable so tests can assert no clinical text is transmitted.
  final Analytics? _analytics;

  @override
  State<ScribeSurfaceV3> createState() => _ScribeSurfaceV3State();
}

class _ScribeSurfaceV3State extends State<ScribeSurfaceV3> {
  static const _mutationGuard = OfflineMutationGuard();

  // Sessions list state.
  bool _listLoading = false;
  String? _listError;
  List<ScribeSessionView> _sessions = const [];

  // Active session detail state.
  ScribeSessionView? _active;
  bool _detailBusy = false;
  String? _detailError;

  // Per-session consent gate (INV-2): false until the clinician captures
  // consent for the active session. Fail-closed — processing is blocked while
  // false, and it resets on every open.
  bool _consentCaptured = false;

  final _appendController = TextEditingController();

  late final ConnectivityService _connectivity;
  DefaultConnectivityService? _ownedConnectivity;

  bool get _enabled => widget.resolver.scribeEnabled;
  bool get _authorized => _isScribeAuthorizedRoleV3(widget.sessionStore.role);
  bool get _isOnline => _connectivity.currentValue;
  _ScribeTranscriptCopy get _transcriptCopy =>
      _ScribeTranscriptCopy.forContext(context);
  _ScribeSessionCopy get _sessionCopy => _ScribeSessionCopy.forContext(context);

  Analytics get _analytics => widget._analytics ?? getAnalyticsClient();

  @override
  void initState() {
    super.initState();
    if (widget._connectivity != null) {
      _connectivity = widget._connectivity!;
    } else {
      _ownedConnectivity = DefaultConnectivityService();
      _connectivity = _ownedConnectivity!;
    }

    // Both gates must be open before any network call is made (fail-closed).
    if (_enabled && _authorized) {
      // Screen-view event carries no clinical content (Req 4.5).
      _analytics.track(_kEvtViewed);
      _loadSessions();
    }
  }

  @override
  void dispose() {
    _appendController.dispose();
    _ownedConnectivity?.dispose();
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
        _detailError = _sessionCopy.sessionExpired;
        _listError = _sessionCopy.sessionExpired;
      });
      return null;
    }
    return token;
  }

  // --- Sessions list -------------------------------------------------------

  Future<void> _loadSessions() async {
    final token = _token;
    if (token == null) {
      setState(() {
        _listLoading = false;
        _listError = _sessionCopy.sessionExpired;
      });
      return;
    }
    setState(() {
      _listLoading = true;
      _listError = null;
    });
    try {
      final data =
          await widget.apiClient.listScribeSessions(accessToken: token);
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
          _listError = _sessionCopy.sessionsLoadFailed);
    } finally {
      if (mounted) {
        setState(() => _listLoading = false);
      }
    }
  }

  Future<void> _createSession() async {
    if (!_isOnline) {
      _showSnack(_sessionCopy.offlineBlocked);
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
          // Empty draft: no transcript, no auto-generate. Clinical text is only
          // added later, after consent is captured (INV-2).
          payload: {'title': title, 'auto_generate_soap': false},
        );
        // Coarse, content-free analytics (Req 4.5).
        _analytics.track(_kEvtSessionCreated);
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
      setState(() => _detailError = _sessionCopy.sessionOpenFailed);
    } finally {
      if (mounted) {
        setState(() => _detailBusy = false);
      }
    }
  }

  /// Switches to the detail view for [view]. Consent always resets to absent on
  /// open, so processing is blocked until the clinician captures it in-session
  /// (fail-closed, INV-2).
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

  // --- Consent gate (INV-2) ------------------------------------------------

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
        _analytics.track(_kEvtConsentCaptured);
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
      _analytics.track(_kEvtConsentRevoked);
      if (!mounted) return;
      // Revoking re-blocks all further processing (INV-2).
      setState(() => _consentCaptured = false);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _detailError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(
          () => _detailError = 'Không thể thu hồi đồng ý. Vui lòng thử lại.');
    } finally {
      if (mounted) {
        setState(() => _detailBusy = false);
      }
    }
  }

  // --- Transcript / SOAP processing ----------------------------------------

  /// The single client-side gate for every processing path: consent must be
  /// captured (INV-2) and the device must be online (Req 9.5). Returns true
  /// when processing may proceed; otherwise surfaces a message and returns
  /// false WITHOUT performing any work or touching entered input.
  bool _canProcess() {
    if (!_consentCaptured) {
      _showSnack(_transcriptCopy.consentRequired);
      return false;
    }
    if (!_isOnline) {
      _showSnack(_transcriptCopy.offlineBlocked);
      return false;
    }
    return true;
  }

  /// Appends typed transcript text and regenerates the SOAP note (Req 4.2,
  /// 4.3). Blocked until consent is captured (INV-2).
  Future<void> _appendTranscriptAndRegenerate() async {
    final active = _active;
    if (active == null) return;
    final addition = _appendController.text.trim();
    if (addition.isEmpty) {
      _showSnack(_transcriptCopy.transcriptRequired);
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
      _analytics.track(_kEvtSoapRegenerated);
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
      setState(
          () => _detailError = _transcriptCopy.regenerateFailed);
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
      _showSnack(_transcriptCopy.soapUnavailable);
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
      _analytics.track(_kEvtSoapRegenerated);
      if (!mounted) return;
      setState(() => _active = ScribeSessionView.fromJson(data));
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _detailError = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(
          () => _detailError = _transcriptCopy.regenerateFailed);
    } finally {
      if (mounted) {
        setState(() => _detailBusy = false);
      }
    }
  }

  // --- Build ---------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final copy = _ScribeSessionCopy.forContext(context);
    final showFab = _enabled && _authorized && _active == null;
    return Scaffold(
      appBar: AppBar(
        title: Text(copy.appTitle),
        leading: _active != null
            ? IconButton(
                icon: const Icon(Icons.arrow_back),
                tooltip: copy.backToSessions,
                onPressed: _detailBusy ? null : _closeSession,
              )
            : null,
      ),
      floatingActionButton: showFab
          ? FloatingActionButton.extended(
              onPressed: _detailBusy ? null : _createSession,
              icon: const Icon(Icons.add),
              label: Text(copy.createSession),
            )
          : null,
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    // Gate 1 — flag off ⇒ inert placeholder, zero calls (fail-closed).
    if (!_enabled) {
      return _ScribePlaceholder(
        title: _sessionCopy.unavailable,
        message: _sessionCopy.featureDisabled,
      );
    }
    // Gate 2 — unauthorized role ⇒ placeholder, zero calls (fail-closed).
    if (!_authorized) {
      return _ScribePlaceholder(
        title: _sessionCopy.unavailable,
        message: _sessionCopy.doctorOnly,
      );
    }
    final content = _active == null
        ? _buildSessionList(context)
        : _buildSessionDetail(context, _active!);
    return Column(
      children: [
        OfflineBanner(connectivity: _connectivity),
        Expanded(child: content),
      ],
    );
  }

  Widget _buildSessionList(BuildContext context) {
    final copy = _ScribeSessionCopy.forContext(context);
    if (_listError != null) {
      return ErrorRetryView(message: _listError!, onRetry: _loadSessions);
    }
    if (_listLoading && _sessions.isEmpty) {
      return const ClaraSkeletonList(itemCount: 4);
    }
    return RefreshIndicator(
      onRefresh: _loadSessions,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(
          ClaraTokens.spaceMd,
          ClaraTokens.spaceMd,
          ClaraTokens.spaceMd,
          96,
        ),
        children: [
          SectionHeader(title: copy.sessionsTitle),
          if (_listLoading)
            const Padding(
              padding: EdgeInsets.only(bottom: ClaraTokens.spaceSm),
              child: LinearProgressIndicator(),
            ),
          if (_sessions.isEmpty)
            ClaraEmptyState(
              icon: Icons.note_alt_outlined,
              title: copy.emptyTitle,
              message: copy.emptyDescription,
              action: ClaraButton.primary(
                label: copy.createSession,
                icon: Icons.add,
                onPressed: _detailBusy ? null : _createSession,
              ),
            )
          else
            ..._sessions.map(
              (session) => Padding(
                padding: const EdgeInsets.only(bottom: ClaraTokens.spaceMd),
                child: _buildSessionTile(context, session),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildSessionTile(BuildContext context, ScribeSessionView session) {
    final theme = Theme.of(context);
    final copy = _ScribeSessionCopy.forContext(context);
    final statusText = copy.statusLabel(session.status);

    // A session tile is a navigation affordance into the session detail (the
    // clinical transcript/SOAP live on opaque cards inside that detail). As
    // chrome it may sit on a liquid-glass surface; when the ambient GlassScope
    // is off the same tile renders opaque with identical geometry. The whole
    // surface is the tap target, announced as a button, and the semantic label
    // + status-by-text are unchanged.
    return A11yLabeled(
      label: copy.sessionSemantic(session.title, statusText),
      isButton: true,
      child: GlassSurface(
        blurSigma: GlassTokens.blurCard,
        radius: GlassTokens.radiusCard,
        child: Material(
          type: MaterialType.transparency,
          child: InkWell(
            onTap: _detailBusy ? null : () => _openSession(session),
            borderRadius: BorderRadius.circular(
              GlassTokens.radiusCard * GlassTokens.squircleFactor,
            ),
            child: Padding(
              padding: const EdgeInsets.all(ClaraTokens.spaceMd),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          session.title,
                          style: theme.textTheme.titleMedium,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: ClaraTokens.spaceSm),
                        StatusByText(
                          label: statusText,
                          level: _statusLevel(session.status),
                          semanticsPrefix: copy.statusPrefix,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: ClaraTokens.spaceSm),
                  Icon(
                    Icons.chevron_right,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSessionDetail(BuildContext context, ScribeSessionView session) {
    final theme = Theme.of(context);
    final copy = _ScribeTranscriptCopy.forContext(context);
    final sessionCopy = _ScribeSessionCopy.forContext(context);
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        ClaraTokens.spaceMd,
        ClaraTokens.spaceMd,
        ClaraTokens.spaceMd,
        ClaraTokens.spaceXl,
      ),
      children: [
        // Session header + status (text/semantics, not color alone — Req 10.5).
        Text(session.title, style: theme.textTheme.titleLarge),
        const SizedBox(height: ClaraTokens.spaceSm),
        StatusByText(
          label: sessionCopy.statusLabel(session.status),
          level: _statusLevel(session.status),
          semanticsPrefix: copy.sessionStatusPrefix,
        ),
        const SizedBox(height: ClaraTokens.spaceMd),

        // Per-session consent gate (INV-2).
        _ConsentGateCard(
          captured: _consentCaptured,
          busy: _detailBusy,
          onCapture: _captureConsent,
          onRevoke: _revokeConsent,
        ),
        const SizedBox(height: ClaraTokens.spaceMd),

        if (_detailError != null) ...[
          StatusByText(
            label: _detailError!,
            level: A11yStatusLevel.danger,
            semanticsPrefix: copy.errorPrefix,
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
        ],

        // Transcript (sanitized via ScribeSessionView — Req 4.5).
        SectionHeader(title: copy.transcriptTitle),
        ClaraCard.static_(
          semanticLabel: copy.transcriptSemantic,
          child: Text(
            session.hasTranscript ? session.transcript : copy.noTranscript,
            key: const Key('scribe-v3-transcript'),
            style: session.hasTranscript
                ? theme.textTheme.bodyMedium
                : theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
          ),
        ),
        const SizedBox(height: ClaraTokens.spaceMd),

        // Append transcript (available once consent is captured; the gate is
        // enforced inside the processing handlers).
        ClaraInput(
          controller: _appendController,
          label: copy.appendLabel,
          hint: copy.appendHint,
          enabled: !_detailBusy,
          keyboardType: TextInputType.multiline,
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        Wrap(
          spacing: ClaraTokens.spaceSm,
          runSpacing: ClaraTokens.spaceSm,
          children: [
            ClaraButton.primary(
              label: copy.appendAndRegenerate,
              icon: Icons.note_add_outlined,
              onPressed: _detailBusy ? null : _appendTranscriptAndRegenerate,
            ),
            ClaraButton.secondary(
              label: copy.regenerate,
              icon: Icons.refresh,
              onPressed: _detailBusy ? null : _regenerateSoap,
            ),
          ],
        ),
        const SizedBox(height: ClaraTokens.spaceSm),
        Text(
          copy.audioUnavailable,
          style: theme.textTheme.bodySmall
              ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
        const SizedBox(height: ClaraTokens.spaceLg),

        // SOAP note (sanitized via ScribeSessionView — Req 4.3, 4.5).
        SectionHeader(title: copy.soapTitle),
        if (!session.hasSoap)
          ClaraCard.static_(
            semanticLabel: copy.soapSemantic,
            child: Text(
              copy.noSoap,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          )
        else
          ...session.soapSections.map(
            (entry) => Padding(
              padding: const EdgeInsets.only(bottom: ClaraTokens.spaceMd),
              child: ClaraCard.static_(
                semanticLabel: entry.key,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(entry.key, style: theme.textTheme.titleSmall),
                    const SizedBox(height: ClaraTokens.spaceXs),
                    Text(entry.value, style: theme.textTheme.bodyMedium),
                  ],
                ),
              ),
            ),
          ),

        if (_detailBusy) ...[
          const SizedBox(height: ClaraTokens.spaceMd),
          const Center(child: CircularProgressIndicator()),
        ],
      ],
    );
  }
}

/// Inert placeholder shown when the flag is off or the role is unauthorized
/// (fail-closed). Renders no scribe content and triggers no network calls.
class _ScribePlaceholder extends StatelessWidget {
  const _ScribePlaceholder({required this.title, required this.message});

  final String title;
  final String message;

  @override
  Widget build(BuildContext context) {
    return ClaraEmptyState(
      icon: Icons.lock_outline,
      title: title,
      message: message,
    );
  }
}

/// The per-session consent-capture gate card (INV-2), on the V3 design system.
/// While consent is absent it makes clear that processing is blocked; capturing
/// unlocks processing and revoking re-blocks it. Status is conveyed by text +
/// icon, not color alone (Req 10.5).
class _ScribeConsentCopy {
  const _ScribeConsentCopy._(this._english);

  factory _ScribeConsentCopy.forContext(BuildContext context) {
    final language = Localizations.localeOf(context).languageCode.toLowerCase();
    return _ScribeConsentCopy._(language == 'en');
  }

  final bool _english;

  String get semanticLabel =>
      _english ? 'Patient consent' : 'Đồng ý của bệnh nhân';
  String get captured => _english
      ? 'Patient consent has been captured.'
      : 'Đã thu thập sự đồng ý của bệnh nhân.';
  String get missing => _english
      ? 'Patient consent has not been captured — transcript processing is blocked.'
      : 'Chưa có sự đồng ý — việc xử lý lời thoại đang bị chặn.';
  String get prefix => _english ? 'Consent' : 'Đồng ý';
  String get capture => _english ? 'Capture consent' : 'Thu thập sự đồng ý';
  String get revoke => _english ? 'Revoke consent' : 'Thu hồi sự đồng ý';
}

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
    final copy = _ScribeConsentCopy.forContext(context);
    return ClaraCard.static_(
      key: const Key('scribe-v3-consent-gate'),
      semanticLabel: copy.semanticLabel,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          StatusByText(
            label: captured
                ? copy.captured
                : copy.missing,
            level: captured ? A11yStatusLevel.success : A11yStatusLevel.warning,
            icon: captured ? Icons.verified_user : Icons.gpp_maybe,
            semanticsPrefix: copy.prefix,
          ),
          const SizedBox(height: ClaraTokens.spaceMd),
          if (!captured)
            ClaraButton.primary(
              label: copy.capture,
              icon: Icons.verified_user_outlined,
              onPressed: busy ? null : onCapture,
            )
          else
            ClaraButton.secondary(
              label: copy.revoke,
              icon: Icons.gpp_bad_outlined,
              onPressed: busy ? null : onRevoke,
            ),
        ],
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
  final TextEditingController _controller = TextEditingController();
  bool _seededDefaultName = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_seededDefaultName) {
      _controller.text =
          _ScribeSessionCopy.forContext(context).defaultSessionName;
      _seededDefaultName = true;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final copy = _ScribeSessionCopy.forContext(context);
    return AlertDialog(
      title: Text(copy.dialogTitle),
      content: ClaraInput(
        controller: _controller,
        label: copy.sessionName,
        hint: copy.sessionHint,
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(copy.cancel),
        ),
        FilledButton(
          onPressed: () {
            final title = _controller.text.trim();
            Navigator.of(context).pop(
              title.isEmpty ? copy.defaultSessionName : title,
            );
          },
          child: Text(copy.create),
        ),
      ],
    );
  }
}

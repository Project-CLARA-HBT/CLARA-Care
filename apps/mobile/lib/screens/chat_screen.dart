import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/a11y.dart';
import '../core/analytics.dart';
import '../core/api_client.dart';
import '../core/connectivity_service.dart';
import '../core/feature_flags.dart';
import '../core/session_store.dart';
import '../theme/tokens.dart';
import '../widgets/end_user_safe_answer.dart';
import '../widgets/error_retry_view.dart';
import '../widgets/markdown_view.dart';
import '../widgets/offline_banner.dart';
import '../widgets/screen_error_boundary.dart';
import 'chat/polished_chat_view.dart';

// =============================================================================
// ChatScreen — conversational chat parity for CLARA_Mobile.
// clara-mobile-feature-parity Task 3.2 (Requirements 1.1–1.6).
//
//   * 1.1 Submit a user message and render the assistant answer + citations.
//   * 1.2 WHERE streaming is enabled, consume `POST /chat/stream` (SSE) and
//         progressively render answer tokens until a terminal event, via
//         [ApiClient.streamChat].
//   * 1.3 WHEN the stream errors/disconnects, fall back to a non-PII error
//         state and preserve any already-streamed content; if nothing was
//         streamed, fall back to the blocking [ApiClient.chat] endpoint.
//   * 1.4 Render the standing medical disclaimer + the directive to review with
//         a licensed clinician on the chat surface.
//   * 1.5 Present an emergency fast-path affordance directing the user to
//         emergency services WITHOUT diagnostic reasoning.
//   * 1.6 Exclude internal runtime fields from the answer view for non-admin
//         roles — answers are rendered through the merged [EndUserSafeAnswer]
//         widget (task 3.3) so the End_User-safe projection is applied.
//   * 1.7 Gated behind `chat_mobile_enabled` via [MobileFeatureFlagResolver];
//         when the flag is absent/false the surface is hidden/disabled.
//
// Privacy: analytics events emitted here are coarse and PII-free — the message
// text, transcript, and any free-text query are NEVER sent to analytics
// (Requirements 11.2, 11.5; Property P5). The [Analytics] facade additionally
// strips PII, but this screen never even hands it free text.
// =============================================================================

/// Coarse, no-PII analytics event names for the chat surface. Defined locally
/// (rather than in the shared `analytics.dart`) so this screen stays additive
/// and does not write a foundation file.
const String kChatViewedEvent = 'mobile_chat_viewed';
const String kChatSubmittedEvent = 'mobile_chat_submitted';
const String kChatAnsweredEvent = 'mobile_chat_answered';
const String kChatEmergencyOpenedEvent = 'mobile_chat_emergency_opened';

/// Coarse, no-PII events for the polished chat surface (clara-mobile-ux-polish
/// Requirement 5.4, 10.3). None carry message/prompt text or model identity.
const String kChatStoppedEvent = 'mobile_chat_stopped';
const String kChatRegeneratedEvent = 'mobile_chat_regenerated';
const String kChatCopiedEvent = 'mobile_chat_copied';

/// Vietnamese-first standing medical disclaimer (Requirement 1.4).
const String _kChatDisclaimerVi =
    'CLARA là công cụ hỗ trợ quyết định, không thay thế tư vấn y khoa. Hãy '
    'trao đổi với bác sĩ hoặc nhân viên y tế có chuyên môn trước khi quyết định.';
const String _kChatDisclaimerEn =
    'CLARA supports decisions only and does not replace medical advice. Please '
    'review any guidance with a licensed clinician.';

/// Vietnamese-first emergency guidance copy. Intentionally directive only — no
/// diagnostic reasoning (Requirement 1.5).
const String _kEmergencyTitleVi = 'Tình huống khẩn cấp?';
const String _kEmergencyTitleEn = 'Emergency?';
const String _kEmergencyBodyVi =
    'Nếu đây là tình huống nguy hiểm đến tính mạng, hãy gọi 115 hoặc đến cơ sở '
    'y tế gần nhất ngay lập tức. CLARA không xử lý cấp cứu.';
const String _kEmergencyBodyEn =
    'If this is a life-threatening situation, call 115 (local emergency) or go '
    'to the nearest medical facility immediately. CLARA does not handle '
    'emergencies.';

/// A single chat message (user prompt or assistant answer).
///
/// Mutable so the assistant bubble can accumulate streamed tokens in place and
/// flip to its terminal (envelope-rendered) state without rebuilding the list.
class ChatMessage {
  ChatMessage.user(this.text)
      : isUser = true,
        isStreaming = false,
        envelope = null,
        errorNote = null;

  ChatMessage.assistantStreaming()
      : isUser = false,
        text = '',
        isStreaming = true,
        envelope = null,
        errorNote = null;

  final bool isUser;

  /// Accumulated streamed text (assistant) or the prompt (user).
  String text;

  /// True while the assistant answer is still streaming.
  bool isStreaming;

  /// The terminal answer envelope (assistant only), rendered through the
  /// End_User-safe projection. Null until a terminal `done`/blocking response.
  Map<String, dynamic>? envelope;

  /// A non-PII error note shown when the stream errored after partial content
  /// (Requirement 1.3). The already-streamed [text] is preserved.
  String? errorNote;
}

/// The conversational chat surface (Requirement 1).
class ChatScreen extends StatefulWidget {
  const ChatScreen({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.resolver,
    this.connectivity,
    this.analytics,
    this.streamingEnabled = true,
    this.isEnglish = false,
    this.polished = false,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;

  /// Resolves the `chat_mobile_enabled` gate (Requirement 1.7).
  final MobileFeatureFlagResolver resolver;

  /// Optional connectivity signal; when offline, sending is blocked with a
  /// clear message and the typed input is preserved (Requirements 9.1, 9.5).
  final ConnectivityService? connectivity;

  /// Analytics facade; defaults to the shared client. Injected in tests.
  final Analytics? analytics;

  /// Whether to consume the SSE stream ([ApiClient.streamChat]); when false the
  /// blocking [ApiClient.chat] endpoint is used directly (Requirement 1.2).
  final bool streamingEnabled;

  /// Vietnamese-first by default; pass `true` for English copy.
  final bool isEnglish;

  /// When true, render the ChatGPT-class polished body (clara-mobile-ux-polish,
  /// gated by `mobile_ux_polish_enabled`). When false the legacy body renders
  /// unchanged (Property P1). Defaults to false so callers opt in explicitly.
  final bool polished;

  /// Builds the screen only when the `chat_mobile_enabled` gate is open;
  /// returns `null` otherwise so the entry point can be omitted entirely
  /// (Requirement 1.7 / 15.1 — flags-off equivalence).
  static Widget? maybe({
    required ApiClient apiClient,
    required SessionStore sessionStore,
    required MobileFeatureFlagResolver resolver,
    ConnectivityService? connectivity,
    Analytics? analytics,
    bool streamingEnabled = true,
    bool isEnglish = false,
    bool? polished,
    Key? key,
  }) {
    if (!resolver.chatEnabled) {
      return null;
    }
    return ChatScreen(
      key: key,
      apiClient: apiClient,
      sessionStore: sessionStore,
      resolver: resolver,
      connectivity: connectivity,
      analytics: analytics,
      streamingEnabled: streamingEnabled,
      isEnglish: isEnglish,
      polished: polished ?? resolver.uxPolishEnabled,
    );
  }

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _input = TextEditingController();
  final ScrollController _scroll = ScrollController();
  final List<ChatMessage> _messages = <ChatMessage>[];

  bool _sending = false;
  bool _emergencyActive = false;

  // --- Polished-surface transient state (clara-mobile-ux-polish) -----------
  // The active SSE subscription so a user-initiated stop can cancel it, and a
  // guard so the "stream closed without terminal event" branch does not treat
  // a user stop as a fallback trigger (Req 3.3 / P10).
  StreamSubscription<SseEvent>? _activeSubscription;
  StringBuffer? _activeBuffer;
  ChatMessage? _activeAssistant;
  bool _cancelled = false;
  bool _atBottom = true;
  bool _showJumpToLatest = false;

  Analytics get _analytics => widget.analytics ?? getAnalyticsClient();
  bool get _enabled => widget.resolver.chatEnabled;
  bool get _polished => widget.polished;

  String? get _token {
    final token = widget.sessionStore.accessToken;
    if (token == null || token.isEmpty) return null;
    return token;
  }

  @override
  void initState() {
    super.initState();
    if (_enabled) {
      // Coarse, no-PII screen-view event.
      _analytics.capture(const AnalyticsEvent(kChatViewedEvent));
    }
    if (_polished) {
      _scroll.addListener(_onScroll);
    }
  }

  @override
  void dispose() {
    _activeSubscription?.cancel();
    _scroll.removeListener(_onScroll);
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  /// Tracks whether the list is at/near the bottom so auto-scroll is gated and
  /// the jump-to-latest affordance is offered otherwise (Req 2.3, 2.4 / P3).
  void _onScroll() {
    if (!_scroll.hasClients) return;
    final atBottom = isNearBottom(
      _scroll.position.pixels,
      _scroll.position.maxScrollExtent,
    );
    if (atBottom == _atBottom) return;
    setState(() {
      _atBottom = atBottom;
      _showJumpToLatest = !atBottom;
    });
  }

  // --- Send / stream -------------------------------------------------------

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty || _sending) return;

    final token = _token;
    if (token == null) {
      _showSnack(widget.isEnglish
          ? 'Your session has expired. Please sign in again.'
          : 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
      return;
    }

    // Offline guard: block the request, keep the typed input (Req 9.5).
    final connectivity = widget.connectivity;
    if (connectivity != null && !connectivity.currentValue) {
      _showSnack(kOfflineMutationBlockedMessage);
      return;
    }

    // Clear the field only once we are committed to sending; the input is
    // otherwise preserved for retry.
    _input.clear();
    final assistant = ChatMessage.assistantStreaming();
    setState(() {
      _messages.add(ChatMessage.user(text));
      _messages.add(assistant);
      _sending = true;
      _emergencyActive = false;
    });
    _scrollToEnd();

    // Coarse, no-PII event: never carries the message text.
    _analytics.capture(AnalyticsEvent(
      kChatSubmittedEvent,
      {'streaming': widget.streamingEnabled},
    ));

    final payload = <String, dynamic>{'message': text};
    if (widget.streamingEnabled) {
      await _runStreaming(token, payload, assistant);
    } else {
      await _runBlocking(token, payload, assistant);
    }
  }

  Future<void> _runStreaming(
    String token,
    Map<String, dynamic> payload,
    ChatMessage assistant,
  ) async {
    final buffer = StringBuffer();
    _cancelled = false;
    final completer = Completer<void>();

    // Fall back to the blocking endpoint when the stream produced no content,
    // else preserve what streamed and show a non-PII note (Req 1.3).
    Future<void> handleInterruption() async {
      if (!mounted || _cancelled) return;
      if (buffer.isEmpty) {
        await _runBlocking(token, payload, assistant);
      } else {
        setState(() {
          assistant.isStreaming = false;
          assistant.errorNote = _streamErrorMessage;
        });
        _finishSending();
      }
    }

    late StreamSubscription<SseEvent> sub;
    sub = widget.apiClient
        .streamChat(accessToken: token, payload: payload)
        .listen(
      (event) {
        if (!mounted || _cancelled) return;
        switch (event.event) {
          case 'token':
            final t = event.json?['text'];
            if (t is String && t.isNotEmpty) {
              buffer.write(t);
              setState(() => assistant.text = buffer.toString());
              _scrollToEnd();
            }
            break;
          case 'done':
            final envelope = event.json ?? <String, dynamic>{};
            _completeAnswer(assistant, envelope, buffer.toString());
            _cancelled = true; // terminal — suppress the onDone fallback
            sub.cancel();
            if (!completer.isCompleted) completer.complete();
            break;
          case 'error':
            _cancelled = true;
            sub.cancel();
            handleInterruption().whenComplete(() {
              if (!completer.isCompleted) completer.complete();
            });
            break;
          default:
            // start / step / keepalive — no user-facing content.
            break;
        }
      },
      onError: (Object _) {
        // Failed to connect/parse the stream (Req 1.3).
        handleInterruption().whenComplete(() {
          if (!completer.isCompleted) completer.complete();
        });
      },
      onDone: () {
        // Stream closed without a terminal `done`/`error` and not user-stopped.
        if (_cancelled) {
          if (!completer.isCompleted) completer.complete();
          return;
        }
        if (buffer.isEmpty) {
          _runBlocking(token, payload, assistant).whenComplete(() {
            if (!completer.isCompleted) completer.complete();
          });
        } else {
          _completeAnswer(
            assistant,
            <String, dynamic>{'reply': buffer.toString()},
            buffer.toString(),
          );
          if (!completer.isCompleted) completer.complete();
        }
      },
      cancelOnError: true,
    );

    _activeSubscription = sub;
    _activeBuffer = buffer;
    _activeAssistant = assistant;
    await completer.future;
    if (identical(_activeSubscription, sub)) {
      _activeSubscription = null;
      _activeBuffer = null;
      _activeAssistant = null;
    }
  }

  /// Stops an in-flight stream (Req 3.3 / P10): cancels the subscription and
  /// finalizes the assistant turn with exactly the buffered text, without
  /// raising a user-facing error (a user-initiated stop is not an error).
  void _stop() {
    final sub = _activeSubscription;
    final assistant = _activeAssistant;
    final buffer = _activeBuffer;
    if (sub == null || assistant == null) return;
    _cancelled = true;
    sub.cancel();
    _activeSubscription = null;
    final streamed = buffer?.toString() ?? assistant.text;
    setState(() {
      assistant.isStreaming = false;
      if (assistant.text.isEmpty && streamed.isNotEmpty) {
        assistant.text = streamed;
      }
      if (assistant.envelope == null && streamed.isNotEmpty) {
        assistant.envelope = <String, dynamic>{'reply': streamed};
      }
    });
    _analytics.capture(const AnalyticsEvent(kChatStoppedEvent));
    _finishSending();
    _activeBuffer = null;
    _activeAssistant = null;
  }

  /// Regenerates the answer at [index] (Req 5.2): drops the assistant turn and
  /// the preceding user turn, then resubmits that prompt through the send path.
  Future<void> _regenerate(int index) async {
    if (_sending) return;
    if (index <= 0 || index >= _messages.length) return;
    final assistant = _messages[index];
    if (assistant.isUser) return;
    final user = _messages[index - 1];
    if (!user.isUser) return;
    final prompt = user.text;
    setState(() {
      _messages.removeRange(index - 1, index + 1);
    });
    _analytics.capture(const AnalyticsEvent(kChatRegeneratedEvent));
    _input.text = prompt;
    await _send();
  }

  /// Copies the answer at [index] to the clipboard as plain text (Req 5.1).
  Future<void> _copy(int index) async {
    if (index < 0 || index >= _messages.length) return;
    final message = _messages[index];
    final envelope = message.envelope;
    final raw = envelope != null
        ? extractAnswerText(
            endUserSafeProjection(envelope, isAdmin: false),
          )
        : message.text;
    final plain = mdToPlainText(raw);
    await Clipboard.setData(ClipboardData(text: plain));
    _analytics.capture(const AnalyticsEvent(kChatCopiedEvent));
    _showSnack(widget.isEnglish ? 'Copied' : 'Đã sao chép');
  }

  void _onSuggestionSelected(String prompt) {
    _input.text = prompt;
    _input.selection =
        TextSelection.collapsed(offset: _input.text.length);
  }

  Future<void> _runBlocking(
    String token,
    Map<String, dynamic> payload,
    ChatMessage assistant,
  ) async {
    try {
      final envelope =
          await widget.apiClient.chat(accessToken: token, payload: payload);
      if (!mounted) return;
      _completeAnswer(assistant, envelope, assistant.text);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        assistant.isStreaming = false;
        assistant.errorNote = error.message;
      });
      _finishSending();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        assistant.isStreaming = false;
        assistant.errorNote = _genericErrorMessage;
      });
      _finishSending();
    }
  }

  /// Finalizes an assistant answer: attaches the envelope, stops streaming,
  /// surfaces the emergency fast-path when the envelope flags it, and emits a
  /// coarse, no-PII answered event.
  void _completeAnswer(
    ChatMessage assistant,
    Map<String, dynamic> envelope,
    String streamedText,
  ) {
    final isEmergency = envelope['emergency'] == true;
    setState(() {
      assistant.envelope = envelope;
      assistant.isStreaming = false;
      if (assistant.text.isEmpty && streamedText.isNotEmpty) {
        assistant.text = streamedText;
      }
      _emergencyActive = _emergencyActive || isEmergency;
    });
    // No free text / model identity is sent — only coarse booleans.
    _analytics.capture(AnalyticsEvent(
      kChatAnsweredEvent,
      {
        'emergency': isEmergency,
        'is_fallback': envelope['fallback'] == true,
      },
    ));
    _finishSending();
    _scrollToEnd();
  }

  void _finishSending() {
    if (!mounted) return;
    setState(() => _sending = false);
  }

  String get _streamErrorMessage => widget.isEnglish
      ? 'The connection was interrupted. Showing what was received so far.'
      : 'Kết nối bị gián đoạn. Hiển thị nội dung đã nhận được.';

  String get _genericErrorMessage => widget.isEnglish
      ? 'Could not get an answer right now. Please try again.'
      : 'Không thể nhận câu trả lời lúc này. Vui lòng thử lại.';

  /// Scrolls to the newest content. On the polished surface, auto-scroll is
  /// gated on the user being at/near the bottom (Req 2.3, 2.4); a jump-to-latest
  /// tap sets [force] to override the gate. Motion collapses under reduced
  /// motion (Req 8.2).
  void _scrollToEnd({bool force = false}) {
    if (_polished && !force && !_atBottom) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      final duration = _polished
          ? A11y.resolveMotionDuration(context, ClaraTokens.motionMedium)
          : const Duration(milliseconds: 200);
      if (duration == Duration.zero) {
        _scroll.jumpTo(_scroll.position.maxScrollExtent);
        return;
      }
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: duration,
        curve: Curves.easeOut,
      );
    });
  }

  /// Jump-to-latest handler: force-scroll to the end and hide the affordance.
  void _jumpToLatest() {
    setState(() {
      _atBottom = true;
      _showJumpToLatest = false;
    });
    _scrollToEnd(force: true);
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  // --- Emergency fast-path (Req 1.5) ---------------------------------------

  void _openEmergencyGuidance() {
    _analytics.capture(const AnalyticsEvent(kChatEmergencyOpenedEvent));
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        key: const Key('chat-emergency-dialog'),
        icon: const Icon(Icons.emergency_outlined),
        title: Text(
            widget.isEnglish ? _kEmergencyTitleEn : _kEmergencyTitleVi),
        content: Text(
            widget.isEnglish ? _kEmergencyBodyEn : _kEmergencyBodyVi),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: Text(widget.isEnglish ? 'Close' : 'Đóng'),
          ),
        ],
      ),
    );
  }

  // --- Build ---------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    if (!_enabled) {
      // Flag off: the surface is unreachable/disabled (Req 1.7).
      return Scaffold(
        appBar: AppBar(title: Text(widget.isEnglish ? 'Chat' : 'Trò chuyện')),
        body: Center(
          key: const Key('chat-disabled'),
          child: Text(widget.isEnglish
              ? 'Chat is not available.'
              : 'Tính năng trò chuyện chưa được bật.'),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.isEnglish ? 'Chat with CLARA' : 'Trò chuyện với CLARA'),
        actions: [
          Semantics(
            button: true,
            label: widget.isEnglish ? _kEmergencyTitleEn : _kEmergencyTitleVi,
            child: IconButton(
              key: const Key('chat-emergency-action'),
              tooltip: widget.isEnglish ? _kEmergencyTitleEn : _kEmergencyTitleVi,
              icon: const Icon(Icons.emergency_outlined),
              onPressed: _openEmergencyGuidance,
            ),
          ),
        ],
      ),
      body: ScreenErrorBoundary(
        child: Column(
          children: [
            if (widget.connectivity != null)
              OfflineBanner(connectivity: widget.connectivity!),
            if (_emergencyActive) _EmergencyBanner(isEnglish: widget.isEnglish),
            _StandingDisclaimer(isEnglish: widget.isEnglish),
            Expanded(
              child: _polished
                  ? PolishedChatView(
                      messages: _messages,
                      scrollController: _scroll,
                      inputController: _input,
                      sessionStore: widget.sessionStore,
                      isStreaming: _sending,
                      showJumpToLatest: _showJumpToLatest,
                      canSend: !_sending,
                      isEnglish: widget.isEnglish,
                      onSend: _send,
                      onStop: _stop,
                      onJumpToLatest: _jumpToLatest,
                      onSuggestionSelected: _onSuggestionSelected,
                      onCopy: _copy,
                      onRegenerate: _regenerate,
                    )
                  : _buildMessageList(context),
            ),
            if (!_polished) _buildComposer(context),
          ],
        ),
      ),
    );
  }

  Widget _buildMessageList(BuildContext context) {
    if (_messages.isEmpty) {
      return Center(
        key: const Key('chat-empty'),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            widget.isEnglish
                ? 'Ask CLARA a question to get started.'
                : 'Đặt câu hỏi cho CLARA để bắt đầu.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        ),
      );
    }
    return ListView.builder(
      key: const Key('chat-message-list'),
      controller: _scroll,
      padding: const EdgeInsets.all(12),
      itemCount: _messages.length,
      itemBuilder: (context, index) =>
          _buildMessage(context, _messages[index]),
    );
  }

  Widget _buildMessage(BuildContext context, ChatMessage message) {
    final theme = Theme.of(context);
    if (message.isUser) {
      return Align(
        alignment: Alignment.centerRight,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 4),
          padding: const EdgeInsets.all(10),
          constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.8,
          ),
          decoration: BoxDecoration(
            color: theme.colorScheme.primaryContainer,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(message.text,
              style: TextStyle(color: theme.colorScheme.onPrimaryContainer)),
        ),
      );
    }

    // Assistant bubble.
    final children = <Widget>[];
    if (message.isStreaming) {
      children.add(Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          const SizedBox(width: 8),
          Text(widget.isEnglish ? 'CLARA is typing…' : 'CLARA đang trả lời…',
              style: theme.textTheme.labelSmall),
        ],
      ));
      if (message.text.isNotEmpty) {
        children.add(const SizedBox(height: 8));
        children.add(Text(message.text, style: theme.textTheme.bodyMedium));
      }
    } else if (message.envelope != null) {
      // Render through the merged End_User-safe answer view (Req 1.6). The
      // standing disclaimer is rendered once at the screen level, so it is
      // suppressed on each bubble here.
      children.add(EndUserSafeAnswer(
        envelope: message.envelope!,
        role: widget.sessionStore.role,
        isEnglish: widget.isEnglish,
        showDisclaimer: false,
      ));
    } else if (message.text.isNotEmpty) {
      children.add(Text(message.text, style: theme.textTheme.bodyMedium));
    }

    if (message.errorNote != null) {
      children.add(const SizedBox(height: 8));
      children.add(Semantics(
        liveRegion: true,
        label: message.errorNote!,
        child: Text(
          message.errorNote!,
          key: const Key('chat-stream-error'),
          style: TextStyle(color: theme.colorScheme.error, fontSize: 12),
        ),
      ));
    }

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(10),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.85,
        ),
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: children,
        ),
      ),
    );
  }

  Widget _buildComposer(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: Semantics(
                textField: true,
                label: widget.isEnglish ? 'Message' : 'Tin nhắn',
                child: TextField(
                  key: const Key('chat-input'),
                  controller: _input,
                  minLines: 1,
                  maxLines: 4,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _send(),
                  decoration: InputDecoration(
                    hintText: widget.isEnglish
                        ? 'Ask CLARA…'
                        : 'Nhập câu hỏi cho CLARA…',
                    border: const OutlineInputBorder(),
                    isDense: true,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Semantics(
              button: true,
              label: widget.isEnglish ? 'Send' : 'Gửi',
              child: SizedBox(
                width: kMinTouchTarget,
                height: kMinTouchTarget,
                child: FilledButton(
                  key: const Key('chat-send'),
                  onPressed: _sending ? null : _send,
                  style: FilledButton.styleFrom(
                    padding: EdgeInsets.zero,
                    minimumSize: const Size(kMinTouchTarget, kMinTouchTarget),
                  ),
                  child: _sending
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.send),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Standing medical disclaimer rendered persistently on the chat surface
/// (Requirement 1.4). Status conveyed by text + semantics, not color alone.
class _StandingDisclaimer extends StatelessWidget {
  const _StandingDisclaimer({required this.isEnglish});

  final bool isEnglish;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final text = isEnglish ? _kChatDisclaimerEn : _kChatDisclaimerVi;
    return Semantics(
      label: text,
      child: Container(
        key: const Key('chat-standing-disclaimer'),
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        color: theme.colorScheme.surfaceContainerHighest,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ExcludeSemantics(
              child: Icon(Icons.info_outline,
                  size: 16, color: theme.colorScheme.onSurfaceVariant),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                text,
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Prominent emergency banner shown when an answer envelope flags an emergency
/// (Requirement 1.5). Directive only — no diagnostic reasoning.
class _EmergencyBanner extends StatelessWidget {
  const _EmergencyBanner({required this.isEnglish});

  final bool isEnglish;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final title = isEnglish ? _kEmergencyTitleEn : _kEmergencyTitleVi;
    final body = isEnglish ? _kEmergencyBodyEn : _kEmergencyBodyVi;
    return Semantics(
      liveRegion: true,
      label: '$title $body',
      child: Container(
        key: const Key('chat-emergency-banner'),
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        color: scheme.errorContainer,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ExcludeSemantics(
              child: Icon(Icons.emergency_outlined,
                  size: 20, color: scheme.onErrorContainer),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: scheme.onErrorContainer,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    body,
                    style: TextStyle(
                        color: scheme.onErrorContainer, fontSize: 12),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

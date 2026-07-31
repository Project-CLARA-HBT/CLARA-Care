// Chat surface for the CLARA_Mobile redesign (Experience_V3).
//
// clara-mobile-redesign, Requirement 9 (Chat as the central surface; Research
// unified into Chat's deep modes). This is the body opened by the shell's
// center circular Chat action.
//
// R9 as-built: a single surface with a segmented mode header that folds the
// deep research tiers into Chat, exactly as the web unifies research into Chat:
//
//   * "Trò chuyện" (Chat) — the polished `ChatScreen`, which owns every
//     safety-critical conversational behavior the redesign must preserve
//     (INV-6, Req 9.4/9.5): streaming with blocking fallback, the emergency
//     fast-path banner/escalation, the standing medical disclaimer,
//     stop/regenerate/copy, offline-mutation guard, and coarse no-PII
//     analytics.
//   * "Nghiên cứu" (Research) — the `ResearchScreen`, which owns the deep /
//     deep_beta tier2 research pipeline (async jobs over SSE, the
//     `research_mobile_deep` gate, and the role-based telemetry gate in
//     `core/research_telemetry_gate.dart` so detailed telemetry is admin-only).
//
// Neither screen is reimplemented — both are reused verbatim so their tested
// invariants hold. The mode header is `IndexedStack`-backed so switching modes
// preserves each surface's in-flight state (a running research job keeps
// streaming; the chat thread is not torn down). The Research tab is only shown
// when the `research_mobile_deep` capability is granted for the role; otherwise
// Chat is the sole surface (fail-closed) and the header collapses.
//
// No CLARA_API contract changes (INV-8): both children call the existing
// `ApiClient` methods only.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../core/api_client.dart';
import '../../core/feature_flags.dart';
import '../../core/session_store.dart';
import '../language_controller.dart';
import '../../screens/chat_screen.dart';
import '../../screens/research_screen.dart';
import '../../theme/tokens.dart';

/// Remote-config capability key gating the deep/deep_beta research tiers.
/// Exposed so the fail-closed gating decision can be property-tested directly.
const String kChatSurfaceResearchDeepFlag = 'research_mobile_deep';

/// The fail-closed R9 gating decision: the deep-research ("Nghiên cứu") tab and
/// the mode header are shown ONLY when the `research_mobile_deep` capability is
/// granted for the role. Pure so it can be tested without mounting the heavy
/// child surfaces.
bool chatSurfaceResearchDeepEnabled(MobileFeatureFlagResolver resolver) =>
    resolver.isEnabled(kChatSurfaceResearchDeepFlag);

/// The two modes folded into the central Chat surface (R9).
enum _ChatSurfaceMode { chat, research }

/// The redesigned Chat surface (shell center action). See file header.
class ChatSurfaceV3 extends StatefulWidget {
  const ChatSurfaceV3({
    super.key,
    required this.apiClient,
    required this.sessionStore,
    required this.resolver,
    this.languageController,
  });

  final ApiClient apiClient;
  final SessionStore sessionStore;
  final MobileFeatureFlagResolver resolver;

  /// App-wide consumer-language state. When absent (older embedded callers),
  /// this surface remains Vietnamese-first for backwards compatibility.
  final LanguageController? languageController;

  @override
  State<ChatSurfaceV3> createState() => _ChatSurfaceV3State();
}

class _ChatSurfaceV3State extends State<ChatSurfaceV3> {
  _ChatSurfaceMode _mode = _ChatSurfaceMode.chat;

  /// Deep research (the "Nghiên cứu" tab and its deep/deep_beta modes) is gated
  /// by the `research_mobile_deep` capability. When off, only Chat is shown and
  /// the mode header collapses (fail-closed).
  bool get _researchDeepEnabled =>
      chatSurfaceResearchDeepEnabled(widget.resolver);

  @override
  Widget build(BuildContext context) {
    final languageController = widget.languageController;
    if (languageController == null) {
      return _buildLocalized(isEnglish: false);
    }
    return AnimatedBuilder(
      animation: languageController,
      builder: (context, _) => _buildLocalized(
        isEnglish: languageController.languageCode == 'en',
      ),
    );
  }

  /// Rebuilds presentation copy when the app-wide language changes without
  /// recreating either child. The [IndexedStack] keeps the chat thread and a
  /// permitted research job alive across a language switch.
  Widget _buildLocalized({required bool isEnglish}) {
    final showModeHeader = _researchDeepEnabled;

    // IndexedStack keeps BOTH children alive so switching modes never tears down
    // an in-flight research job stream or the chat thread. Chat is index 0.
    final body = IndexedStack(
      index: _mode == _ChatSurfaceMode.research && _researchDeepEnabled ? 1 : 0,
      children: [
        ChatScreen(
          apiClient: widget.apiClient,
          sessionStore: widget.sessionStore,
          resolver: widget.resolver,
          // Streaming-first (SSE) with ChatScreen's built-in blocking fallback.
          streamingEnabled: true,
          // The shell owns the live locale; ChatScreen keeps its state while
          // the static UI copy changes between Vietnamese and English.
          isEnglish: isEnglish,
          // The Experience_V3 redesign always renders the polished
          // ChatGPT-class body; it is the design target here.
          polished: true,
        ),
        // Only construct the research surface when its capability is granted;
        // otherwise a lightweight placeholder that is never reachable (the
        // header is hidden), keeping the stack index in range.
        if (_researchDeepEnabled)
          ResearchScreen(
            apiClient: widget.apiClient,
            sessionStore: widget.sessionStore,
            deepResearchEnabled: true,
          )
        else
          const SizedBox.shrink(),
      ],
    );

    if (!showModeHeader) {
      return body;
    }

    return Column(
      children: [
        _ChatModeHeader(
          mode: _mode,
          isEnglish: isEnglish,
          onModeChanged: (next) {
            if (next == _mode) return;
            setState(() => _mode = next);
          },
        ),
        Expanded(child: body),
      ],
    );
  }
}

/// The segmented mode header folding Research into Chat (R9). Two options —
/// "Trò chuyện" and "Nghiên cứu" — with ≥48dp targets and single-announcement
/// semantics conveying the selected state by text, not color alone.
class _ChatModeHeader extends StatelessWidget {
  const _ChatModeHeader({
    required this.mode,
    required this.isEnglish,
    required this.onModeChanged,
  });

  final _ChatSurfaceMode mode;
  final bool isEnglish;
  final ValueChanged<_ChatSurfaceMode> onModeChanged;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          ClaraTokens.spaceMd,
          ClaraTokens.spaceSm,
          ClaraTokens.spaceMd,
          0,
        ),
        child: Semantics(
          container: true,
          label: isEnglish ? 'Mode' : 'Chế độ',
          child: SegmentedButton<_ChatSurfaceMode>(
            showSelectedIcon: false,
            segments: [
              ButtonSegment<_ChatSurfaceMode>(
                value: _ChatSurfaceMode.chat,
                icon: Icon(Icons.forum_outlined),
                label: Text(isEnglish ? 'Chat' : 'Trò chuyện'),
              ),
              ButtonSegment<_ChatSurfaceMode>(
                value: _ChatSurfaceMode.research,
                icon: Icon(Icons.science_outlined),
                label: Text(isEnglish ? 'Research' : 'Nghiên cứu'),
              ),
            ],
            selected: {mode},
            onSelectionChanged: (selection) => onModeChanged(selection.first),
          ),
        ),
      ),
    );
  }
}

/// Exposed for tests: the minimum tap target the segmented control honors.
const double kChatSurfaceMinTapTarget = A11y.minTapTargetDimension;

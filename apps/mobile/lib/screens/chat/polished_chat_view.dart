// PolishedChatView — the ChatGPT-class body for the CLARA chat surface
// (clara-mobile-ux-polish, Requirement 1, 2, 4, 8).
//
// Assembles the empty state, the message list (with auto-scroll + a
// jump-to-latest affordance), and the composer. It is a stateless view: the
// parent (`ChatScreen`) owns all state (messages, controllers, streaming) and
// passes callbacks. Motion is resolved through `A11y.resolveMotionDuration`
// (Requirement 8) and content is never gated on animation completion.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../core/session_store.dart';
import '../../theme/tokens.dart';
import '../chat_screen.dart' show ChatMessage;
import 'chat_bubbles.dart';
import 'chat_composer.dart';
import 'chat_empty_state.dart';

/// Whether a scroll position is at/near the bottom, within [threshold] logical
/// pixels of the maximum extent (Requirement 2.3, 2.4; Property P3). Pure so it
/// is trivially unit/property testable.
bool isNearBottom(double pixels, double maxExtent, {double threshold = 120.0}) {
  if (maxExtent <= 0) {
    return true;
  }
  return (maxExtent - pixels) <= threshold;
}

/// The polished chat body. Driven entirely by the parent's state + callbacks.
class PolishedChatView extends StatelessWidget {
  const PolishedChatView({
    super.key,
    required this.messages,
    required this.scrollController,
    required this.inputController,
    required this.sessionStore,
    required this.isStreaming,
    required this.showJumpToLatest,
    required this.canSend,
    required this.isEnglish,
    required this.onSend,
    required this.onStop,
    required this.onJumpToLatest,
    required this.onSuggestionSelected,
    required this.onCopy,
    required this.onRegenerate,
  });

  final List<ChatMessage> messages;
  final ScrollController scrollController;
  final TextEditingController inputController;
  final SessionStore sessionStore;
  final bool isStreaming;
  final bool showJumpToLatest;

  /// Whether sending is currently allowed (connectivity/session, not text —
  /// the composer applies the empty-text rule live).
  final bool canSend;
  final bool isEnglish;

  final VoidCallback onSend;
  final VoidCallback onStop;
  final VoidCallback onJumpToLatest;
  final ValueChanged<String> onSuggestionSelected;

  /// Copy the answer at [index] to the clipboard.
  final ValueChanged<int> onCopy;

  /// Regenerate the answer at [index].
  final ValueChanged<int> onRegenerate;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: Stack(
            children: [
              if (messages.isEmpty)
                ChatEmptyState(
                  onSuggestionSelected: onSuggestionSelected,
                  isEnglish: isEnglish,
                )
              else
                ListView.builder(
                  key: const Key('chat-message-list'),
                  controller: scrollController,
                  padding: const EdgeInsets.symmetric(
                    horizontal: ClaraTokens.spaceMd,
                    vertical: ClaraTokens.spaceSm,
                  ),
                  itemCount: messages.length,
                  itemBuilder: (context, index) =>
                      _buildMessage(context, index),
                ),
              if (showJumpToLatest)
                Positioned(
                  right: ClaraTokens.spaceMd,
                  bottom: ClaraTokens.spaceMd,
                  child: _JumpToLatest(
                    isEnglish: isEnglish,
                    onPressed: onJumpToLatest,
                  ),
                ),
            ],
          ),
        ),
        ChatComposer(
          controller: inputController,
          isStreaming: isStreaming,
          onSend: onSend,
          onStop: onStop,
          isEnglish: isEnglish,
          enabled: canSend,
        ),
      ],
    );
  }

  Widget _buildMessage(BuildContext context, int index) {
    final message = messages[index];
    if (message.isUser) {
      return UserBubble(text: message.text);
    }
    return AssistantBubble(
      text: message.text,
      isStreaming: message.isStreaming,
      envelope: message.envelope,
      role: sessionStore.role,
      isEnglish: isEnglish,
      errorNote: message.errorNote,
      anyStreaming: isStreaming,
      onCopy: () => onCopy(index),
      onRegenerate: () => onRegenerate(index),
    );
  }
}

/// A small "jump to latest" affordance shown when the user has scrolled away
/// from the bottom (Requirement 2.4).
class _JumpToLatest extends StatelessWidget {
  const _JumpToLatest({required this.isEnglish, required this.onPressed});

  final bool isEnglish;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final label = isEnglish ? 'Jump to latest' : 'Đến tin mới nhất';
    return Semantics(
      button: true,
      label: label,
      child: FloatingActionButton.small(
        key: const Key('chat-jump-to-latest'),
        heroTag: 'chat-jump-to-latest',
        tooltip: label,
        onPressed: onPressed,
        child: const Icon(Icons.arrow_downward),
      ),
    );
  }
}

/// Convenience: animate a scroll controller to its end, honoring reduced motion.
Future<void> animateToEnd(
  ScrollController controller,
  BuildContext context, {
  Duration duration = ClaraTokens.motionMedium,
}) async {
  if (!controller.hasClients) {
    return;
  }
  final resolved = A11y.resolveMotionDuration(context, duration);
  final target = controller.position.maxScrollExtent;
  if (resolved == Duration.zero) {
    controller.jumpTo(target);
    return;
  }
  await controller.animateTo(
    target,
    duration: resolved,
    curve: Curves.easeOut,
  );
}

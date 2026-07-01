// ChatComposer — the message input + send/stop control for the chat surface.
//
// A stateless composer: the parent owns the [TextEditingController] and all
// send/stream state. This widget renders a multiline, auto-growing input and a
// single trailing action that swaps between SEND (idle) and STOP (streaming):
//
//   * While [isStreaming] is true, it shows a STOP control that calls [onStop]
//     and is always enabled — the user can always interrupt generation.
//   * Otherwise it shows a SEND control, enabled only when [enabled] is true
//     and the trimmed input text is non-empty. A [ValueListenableBuilder] keeps
//     that enable-state live as the user types.
//
// Design/accessibility notes:
//   * Vietnamese-first copy (Requirement 11.1); [isEnglish] flips to English.
//   * Colors/shape come from `Theme.of(context)` + `ClaraTokens` — no hex.
//   * The action control is a >= 48dp touch target (Requirement 10.2) and both
//     the field and the button expose semantics (Requirement 10.1).
//   * Submitting via the keyboard `send` action triggers [onSend] only when the
//     send control would be enabled.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/tokens.dart';

/// Stateless chat input with an auto-growing text field and a trailing
/// send/stop action driven by [isStreaming].
class ChatComposer extends StatelessWidget {
  const ChatComposer({
    super.key,
    required this.controller,
    required this.isStreaming,
    required this.onSend,
    required this.onStop,
    this.isEnglish = false,
    this.enabled = true,
  });

  /// Parent-owned controller for the input text.
  final TextEditingController controller;

  /// Whether a response is currently streaming. When `true`, the trailing
  /// action is a STOP control.
  final bool isStreaming;

  /// Invoked to send the current message. Only called when sending is enabled.
  final VoidCallback onSend;

  /// Invoked to interrupt an in-progress stream.
  final VoidCallback onStop;

  /// When `true`, render English copy; otherwise Vietnamese (the default).
  final bool isEnglish;

  /// Gates sending (e.g., while the surface is offline or busy). Ignored while
  /// streaming — STOP is always available.
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final hint = isEnglish ? 'Ask CLARA…' : 'Nhập câu hỏi cho CLARA…';
    final fieldLabel = isEnglish ? 'Message' : 'Tin nhắn';

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceMd,
          vertical: ClaraTokens.spaceSm,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: Semantics(
                textField: true,
                label: fieldLabel,
                child: TextField(
                  key: const Key('chat-input'),
                  controller: controller,
                  enabled: enabled || isStreaming,
                  minLines: 1,
                  maxLines: 6,
                  textInputAction: TextInputAction.send,
                  keyboardType: TextInputType.multiline,
                  style: textTheme.bodyLarge?.copyWith(
                    color: scheme.onSurface,
                  ),
                  onSubmitted: (_) {
                    if (_canSend) {
                      onSend();
                    }
                  },
                  decoration: InputDecoration(
                    hintText: hint,
                    filled: true,
                    fillColor: scheme.surfaceContainerHighest,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: ClaraTokens.spaceMd,
                      vertical: ClaraTokens.spaceSm + ClaraTokens.spaceXs,
                    ),
                    border: OutlineInputBorder(
                      borderRadius:
                          BorderRadius.circular(ClaraTokens.radiusLg),
                      borderSide: BorderSide.none,
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius:
                          BorderRadius.circular(ClaraTokens.radiusLg),
                      borderSide: BorderSide.none,
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius:
                          BorderRadius.circular(ClaraTokens.radiusLg),
                      borderSide: BorderSide(color: scheme.primary, width: 1.5),
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: ClaraTokens.spaceSm),
            _ActionButton(
              isStreaming: isStreaming,
              onSend: onSend,
              onStop: onStop,
              controller: controller,
              enabled: enabled,
              isEnglish: isEnglish,
            ),
          ],
        ),
      ),
    );
  }

  /// Whether sending is currently permitted (idle + enabled + non-empty text).
  bool get _canSend =>
      !isStreaming && enabled && controller.text.trim().isNotEmpty;
}

/// The trailing send/stop action. Kept private so the composer stays a single
/// public widget; it rebuilds live with the controller for the send state.
class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.isStreaming,
    required this.onSend,
    required this.onStop,
    required this.controller,
    required this.enabled,
    required this.isEnglish,
  });

  final bool isStreaming;
  final VoidCallback onSend;
  final VoidCallback onStop;
  final TextEditingController controller;
  final bool enabled;
  final bool isEnglish;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    if (isStreaming) {
      final stopLabel = isEnglish ? 'Stop' : 'Dừng';
      return Semantics(
        button: true,
        label: stopLabel,
        child: Tooltip(
          message: stopLabel,
          child: SizedBox(
            width: A11y.minTapTargetDimension,
            height: A11y.minTapTargetDimension,
            child: IconButton.filled(
              key: const Key('chat-stop'),
              onPressed: onStop,
              icon: const Icon(Icons.stop),
              style: IconButton.styleFrom(
                backgroundColor: scheme.error,
                foregroundColor: scheme.onError,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                ),
              ),
            ),
          ),
        ),
      );
    }

    final sendLabel = isEnglish ? 'Send' : 'Gửi';
    return ValueListenableBuilder<TextEditingValue>(
      valueListenable: controller,
      builder: (context, value, _) {
        final canSend = enabled && value.text.trim().isNotEmpty;
        return Semantics(
          button: true,
          enabled: canSend,
          label: sendLabel,
          child: Tooltip(
            message: sendLabel,
            child: SizedBox(
              width: A11y.minTapTargetDimension,
              height: A11y.minTapTargetDimension,
              child: IconButton.filled(
                key: const Key('chat-send'),
                onPressed: canSend ? onSend : null,
                icon: const Icon(Icons.send),
                style: IconButton.styleFrom(
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

// Chat message bubbles for the polished CLARA chat surface
// (clara-mobile-ux-polish, Requirement 1, 2, 5).
//
// Distinct user/assistant treatments, a typing indicator while an assistant
// turn is streaming with no text yet, Markdown rendering for streamed assistant
// text, the End_User-safe answer projection for terminal envelopes, and
// per-message actions (copy / regenerate).
//
// All colors/typography come from `Theme.of(context)` so the web palette (light
// and dark) applies automatically. Motion is resolved through
// `A11y.resolveMotionDuration` so it collapses under reduced motion.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/tokens.dart';
import '../../widgets/end_user_safe_answer.dart';
import '../../widgets/markdown_view.dart';
import 'chat_flow_status.dart';

/// A right-aligned user turn (Requirement 1.1). Solid brand fill with a tail
/// corner flattened toward the trailing edge.
class UserBubble extends StatelessWidget {
  const UserBubble({super.key, required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: ClaraTokens.spaceXs),
        padding: const EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceMd,
          vertical: ClaraTokens.spaceSm + ClaraTokens.spaceXs,
        ),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.82,
        ),
        decoration: BoxDecoration(
          color: scheme.primary,
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(ClaraTokens.radiusLg),
            topRight: Radius.circular(ClaraTokens.radiusLg),
            bottomLeft: Radius.circular(ClaraTokens.radiusLg),
            bottomRight: Radius.circular(ClaraTokens.radiusSm),
          ),
        ),
        child: Text(
          text,
          style: textTheme.bodyLarge?.copyWith(color: scheme.onPrimary),
        ),
      ),
    );
  }
}

/// A left-aligned assistant turn (Requirement 1.1, 1.2, 2.2).
///
/// While [isStreaming] with no [text] yet, shows a [TypingIndicator]. Once text
/// is present it renders as Markdown; a terminal [envelope] renders through the
/// End_User-safe projection for [role]. When finished (non-streaming, with text
/// or an envelope), the [MessageActions] row (copy / regenerate) is shown.
class AssistantBubble extends StatelessWidget {
  const AssistantBubble({
    super.key,
    required this.text,
    required this.isStreaming,
    required this.envelope,
    required this.role,
    required this.isEnglish,
    required this.errorNote,
    required this.anyStreaming,
    this.flowSteps = const <ChatFlowStep>[],
    this.onCopy,
    this.onRegenerate,
  });

  final String text;
  final bool isStreaming;
  final Map<String, dynamic>? envelope;
  final String? role;
  final bool isEnglish;
  final String? errorNote;

  /// The live pipeline process (routing/retrieval/synthesis/verification/…)
  /// distilled from the SSE `step` frames. Rendered above the answer so the
  /// user sees which node CLARA is at, not just a spinner.
  final List<ChatFlowStep> flowSteps;

  /// True when any turn in the conversation is streaming (disables regenerate).
  final bool anyStreaming;

  final VoidCallback? onCopy;
  final VoidCallback? onRegenerate;

  bool get _finished => !isStreaming && (text.isNotEmpty || envelope != null);

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final children = <Widget>[];

    // Live pipeline process (which node CLARA is at). Shown while streaming and
    // kept as a collapsible summary once the turn finishes.
    if (flowSteps.isNotEmpty) {
      children.add(ChatFlowStatusView(
        steps: flowSteps,
        isActive: isStreaming,
        isEnglish: isEnglish,
      ));
    }

    if (isStreaming && text.isEmpty) {
      children.add(TypingIndicator(isEnglish: isEnglish));
    }

    if (envelope != null) {
      // Terminal envelope: render through the End_User-safe projection. The
      // standing disclaimer is shown once at the surface level, so suppress it
      // per-bubble here.
      children.add(EndUserSafeAnswer(
        envelope: envelope!,
        role: role,
        isEnglish: isEnglish,
        showDisclaimer: false,
      ));
    } else if (text.isNotEmpty) {
      children.add(MarkdownView(text));
    }

    if (errorNote != null) {
      children.add(const SizedBox(height: ClaraTokens.spaceSm));
      children.add(Semantics(
        liveRegion: true,
        label: errorNote!,
        child: Text(
          errorNote!,
          key: const Key('chat-stream-error'),
          style: textTheme.bodySmall?.copyWith(color: scheme.error),
        ),
      ));
    }

    if (_finished && (onCopy != null || onRegenerate != null)) {
      children.add(const SizedBox(height: ClaraTokens.spaceXs));
      children.add(MessageActions(
        isEnglish: isEnglish,
        onCopy: onCopy,
        onRegenerate: anyStreaming ? null : onRegenerate,
      ));
    }

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: ClaraTokens.spaceXs),
        padding: const EdgeInsets.symmetric(
          horizontal: ClaraTokens.spaceMd,
          vertical: ClaraTokens.spaceSm + ClaraTokens.spaceXs,
        ),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.9,
        ),
        decoration: BoxDecoration(
          color: scheme.surfaceContainerHighest,
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(ClaraTokens.radiusLg),
            topRight: Radius.circular(ClaraTokens.radiusLg),
            bottomLeft: Radius.circular(ClaraTokens.radiusSm),
            bottomRight: Radius.circular(ClaraTokens.radiusLg),
          ),
          border: Border.all(color: scheme.outline),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: children,
        ),
      ),
    );
  }
}

/// An animated three-dot "CLARA is typing…" indicator (Requirement 2.2). The
/// dot animation is suppressed under reduced motion; the label still conveys
/// the state.
class TypingIndicator extends StatefulWidget {
  const TypingIndicator({super.key, required this.isEnglish});

  final bool isEnglish;

  @override
  State<TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<TypingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1100),
    );
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Only run the looping animation when motion is allowed (Requirement 8.2).
    if (A11y.prefersReducedMotion(context)) {
      _controller.stop();
    } else if (!_controller.isAnimating) {
      _controller.repeat();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final label = widget.isEnglish ? 'CLARA is typing…' : 'CLARA đang trả lời…';
    return Semantics(
      liveRegion: true,
      label: label,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: 34,
            height: 12,
            child: AnimatedBuilder(
              animation: _controller,
              builder: (context, _) {
                return Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    for (var i = 0; i < 3; i++)
                      Padding(
                        padding: const EdgeInsets.only(right: 4),
                        child: _Dot(
                          color: scheme.onSurfaceVariant,
                          t: _dotOpacity(i),
                        ),
                      ),
                  ],
                );
              },
            ),
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          Text(label, style: textTheme.labelSmall),
        ],
      ),
    );
  }

  double _dotOpacity(int index) {
    if (!_controller.isAnimating) {
      return 0.7;
    }
    final phase = (_controller.value * 3 - index).clamp(0.0, 1.0);
    // Ease in and out so the wave feels smooth.
    final wave = (0.5 - (phase - 0.5).abs()) * 2; // 0→1→0
    return 0.35 + 0.65 * wave;
  }
}

class _Dot extends StatelessWidget {
  const _Dot({required this.color, required this.t});

  final Color color;
  final double t;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(
        color: color.withValues(alpha: t),
        shape: BoxShape.circle,
      ),
    );
  }
}

/// Per-message copy / regenerate actions (Requirement 5). Each control is a
/// ≥44px labeled touch target; regenerate is disabled (null [onRegenerate])
/// while any turn is streaming.
class MessageActions extends StatelessWidget {
  const MessageActions({
    super.key,
    required this.isEnglish,
    this.onCopy,
    this.onRegenerate,
  });

  final bool isEnglish;
  final VoidCallback? onCopy;
  final VoidCallback? onRegenerate;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final copyLabel = isEnglish ? 'Copy' : 'Sao chép';
    final regenLabel = isEnglish ? 'Regenerate' : 'Tạo lại';
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (onCopy != null)
          Semantics(
            button: true,
            label: copyLabel,
            child: Tooltip(
              message: copyLabel,
              child: SizedBox(
                width: A11y.minTapTargetDimension,
                height: A11y.minTapTargetDimension,
                child: IconButton(
                  key: const Key('chat-action-copy'),
                  onPressed: onCopy,
                  icon: const Icon(Icons.copy_outlined, size: 18),
                  color: scheme.onSurfaceVariant,
                ),
              ),
            ),
          ),
        Semantics(
          button: true,
          enabled: onRegenerate != null,
          label: regenLabel,
          child: Tooltip(
            message: regenLabel,
            child: SizedBox(
              width: A11y.minTapTargetDimension,
              height: A11y.minTapTargetDimension,
              child: IconButton(
                key: const Key('chat-action-regenerate'),
                onPressed: onRegenerate,
                icon: const Icon(Icons.refresh, size: 18),
                color: scheme.onSurfaceVariant,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

// ChatEmptyState — the welcoming, first-run state for the CLARA chat surface.
//
// Shown when a conversation has no messages yet. It introduces CLARA and offers
// a small set of safe, decision-support prompt suggestions the user can tap to
// pre-fill the composer. Tapping a suggestion NEVER sends a message; it only
// surfaces the prompt text to the parent (via [onSuggestionSelected]) so the
// parent can place it in the composer for the user to review, edit, and send.
//
// Design/accessibility notes:
//   * Vietnamese-first copy (Requirement 11.1); [isEnglish] flips to English.
//   * Colors/typography come from `Theme.of(context)` — no hardcoded hex.
//   * Suggestion chips are wrapped in [MinTapTarget] so each interactive target
//     meets the platform minimum (>= 48dp, Requirement 10.2), and each exposes a
//     button semantics label (Requirement 10.1).
//   * The suggestions are intentionally general health/decision-support prompts
//     (preparation, explanation, storage, when-to-escalate) — never a request
//     for a personal diagnosis or dosage.
//
// Stateless and pure: the parent owns all state; this widget only renders and
// reports taps.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/tokens.dart';

/// A single localized prompt suggestion (Vietnamese + English variants).
class _Suggestion {
  const _Suggestion({
    required this.vi,
    required this.en,
    required this.icon,
  });

  final String vi;
  final String en;
  final IconData icon;

  String text(bool isEnglish) => isEnglish ? en : vi;
}

/// Friendly, empty-conversation introduction for the chat surface with tappable
/// prompt suggestions that pre-fill (but do not send) the composer.
class ChatEmptyState extends StatelessWidget {
  const ChatEmptyState({
    super.key,
    required this.onSuggestionSelected,
    this.isEnglish = false,
  });

  /// Invoked with the chosen prompt text when a suggestion is tapped. The
  /// parent is expected to place the text into the composer; this widget never
  /// sends a message itself.
  final ValueChanged<String> onSuggestionSelected;

  /// When `true`, render English copy; otherwise Vietnamese (the default).
  final bool isEnglish;

  static const List<_Suggestion> _suggestions = <_Suggestion>[
    _Suggestion(
      vi: 'Tôi nên chuẩn bị gì trước khi đi khám?',
      en: 'What should I prepare before a doctor visit?',
      icon: Icons.event_available_outlined,
    ),
    _Suggestion(
      vi: 'Giải thích kết quả xét nghiệm máu cơ bản',
      en: 'Explain a basic blood test result',
      icon: Icons.science_outlined,
    ),
    _Suggestion(
      vi: 'Cách bảo quản thuốc đúng cách',
      en: 'How to store medicine properly',
      icon: Icons.medication_outlined,
    ),
    _Suggestion(
      vi: 'Dấu hiệu cần đi cấp cứu ngay',
      en: 'Warning signs that need emergency care',
      icon: Icons.emergency_outlined,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final textTheme = theme.textTheme;

    final headline = isEnglish ? "Hi! I'm CLARA." : 'Xin chào! Tôi là CLARA.';
    final subtitle = isEnglish
        ? 'Ask me a health question, or tap a suggestion below to get started.'
        : 'Hãy đặt cho tôi một câu hỏi sức khỏe, hoặc chọn một gợi ý bên dưới để bắt đầu.';

    return SingleChildScrollView(
      key: const Key('chat-empty-polished'),
      padding: const EdgeInsets.all(ClaraTokens.spaceLg),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Soft brand avatar. Decorative — the headline carries meaning.
              Container(
                width: 88,
                height: 88,
                decoration: BoxDecoration(
                  color: scheme.primaryContainer,
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: ExcludeSemantics(
                  child: Icon(
                    Icons.health_and_safety,
                    size: 44,
                    color: scheme.primary,
                  ),
                ),
              ),
              const SizedBox(height: ClaraTokens.spaceLg),
              Semantics(
                header: true,
                child: Text(
                  headline,
                  textAlign: TextAlign.center,
                  style: textTheme.headlineSmall?.copyWith(
                    color: scheme.onSurface,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const SizedBox(height: ClaraTokens.spaceSm),
              Text(
                subtitle,
                textAlign: TextAlign.center,
                style: textTheme.bodyMedium?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: ClaraTokens.spaceLg),
              Wrap(
                alignment: WrapAlignment.center,
                spacing: ClaraTokens.spaceSm,
                runSpacing: ClaraTokens.spaceSm,
                children: <Widget>[
                  for (var i = 0; i < _suggestions.length; i++)
                    _SuggestionChip(
                      key: Key('chat-suggestion-$i'),
                      suggestion: _suggestions[i],
                      isEnglish: isEnglish,
                      onSelected: onSuggestionSelected,
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A single tappable prompt suggestion. Tapping surfaces the prompt text to the
/// parent (pre-fill only) — it never sends a message.
class _SuggestionChip extends StatelessWidget {
  const _SuggestionChip({
    super.key,
    required this.suggestion,
    required this.isEnglish,
    required this.onSelected,
  });

  final _Suggestion suggestion;
  final bool isEnglish;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final prompt = suggestion.text(isEnglish);

    return MinTapTarget(
      semanticsLabel: prompt,
      child: Semantics(
        button: true,
        label: prompt,
        child: Material(
          color: scheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: () => onSelected(prompt),
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                minHeight: A11y.minTapTargetDimension,
                maxWidth: 320,
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: ClaraTokens.spaceMd,
                  vertical: ClaraTokens.spaceSm,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    ExcludeSemantics(
                      child: Icon(
                        suggestion.icon,
                        size: 20,
                        color: scheme.primary,
                      ),
                    ),
                    const SizedBox(width: ClaraTokens.spaceSm),
                    Flexible(
                      child: Text(
                        prompt,
                        style: textTheme.bodyMedium?.copyWith(
                          color: scheme.onSurface,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

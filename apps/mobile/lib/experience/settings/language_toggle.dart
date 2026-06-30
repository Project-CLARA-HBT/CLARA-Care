// Settings language toggle for CLARA_Mobile Experience_V2 (Req 9.1, 9.2, 9.6).
//
// A pure-UI control that lets the user pick the app-wide language between
// Tiếng Việt (`vi`, the Vietnamese-first default) and English (`en`). It is the
// presentation half of the language feature: it renders a `SectionHeader`
// ("Ngôn ngữ") and a list of selectable options, and DELEGATES all behavior to
// the injected [LanguageController]:
//
//   * It listens to the controller via [ListenableBuilder] so the current
//     selection always reflects controller state (including changes made
//     elsewhere or restored on launch).
//   * On a user pick it calls `controller.setLanguage(code)`; the controller
//     owns persistence (`LanguageStore`) and the coarse no-PII analytics event.
//     This widget itself performs NO storage and NO analytics (Req 9.2, 9.6).
//
// Accessibility (Req 9.3, 9.4, 9.5):
//   * Each option is a `RadioListTile` whose tap target is constrained to
//     ≥48dp (`A11y.minTapTargetDimension`) and is wrapped with a semantics
//     label that conveys both the option and its selected state — selection is
//     never conveyed by color alone.
//   * The section title is exposed as an a11y header via `SectionHeader`.
//   * Labels honor the OS text-scaling preference via `A11y.resolveTextScaler`.
//
// Copy is Vietnamese-first; the option labels are the languages' endonyms
// ("Tiếng Việt" / "English") so each is recognizable in its own language.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../../theme/components/clara_card.dart';
import '../../theme/components/section_header.dart';
import '../../theme/tokens.dart';
import '../language_controller.dart';

/// A single selectable language option (code + endonym label).
class _LanguageOption {
  const _LanguageOption(this.code, this.label);

  /// 2-letter language code (`'vi'` / `'en'`).
  final String code;

  /// Display label in the language's own script (endonym).
  final String label;
}

/// Settings control to choose the app-wide language (Req 9.1, 9.2, 9.6).
///
/// Pure presentation over an injected [LanguageController]: renders the
/// "Ngôn ngữ" section and a radio list of supported languages, calling
/// [LanguageController.setLanguage] on change. Persistence and analytics live
/// in the controller, not here.
class LanguageToggle extends StatelessWidget {
  const LanguageToggle({super.key, required this.controller});

  /// The app-wide language state. The toggle listens to it for the current
  /// selection and calls [LanguageController.setLanguage] on a user pick.
  final LanguageController controller;

  /// Vietnamese-first section title.
  static const String _sectionTitle = 'Ngôn ngữ';

  /// Supported options, in the controller's `vi`-first order, labeled with each
  /// language's endonym so it is recognizable in its own script.
  static const List<_LanguageOption> _options = <_LanguageOption>[
    _LanguageOption('vi', 'Tiếng Việt'),
    _LanguageOption('en', 'English'),
  ];

  @override
  Widget build(BuildContext context) {
    final textScaler = A11y.resolveTextScaler(context);

    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final selected = controller.languageCode;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            const SectionHeader(title: _sectionTitle),
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: ClaraTokens.spaceMd,
              ),
              child: ClaraCard.static_(
                semanticLabel: _sectionTitle,
                padding: const EdgeInsets.symmetric(
                  vertical: ClaraTokens.spaceXs,
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    for (final option in _options)
                      _LanguageRadioTile(
                        option: option,
                        groupValue: selected,
                        textScaler: textScaler,
                        onSelected: () => controller.setLanguage(option.code),
                      ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

/// One language row: a ≥48dp, screen-reader-labeled radio tile whose selected
/// state is conveyed by text/semantics (not color alone).
class _LanguageRadioTile extends StatelessWidget {
  const _LanguageRadioTile({
    required this.option,
    required this.groupValue,
    required this.textScaler,
    required this.onSelected,
  });

  final _LanguageOption option;
  final String groupValue;
  final TextScaler textScaler;
  final VoidCallback onSelected;

  @override
  Widget build(BuildContext context) {
    final isSelected = option.code == groupValue;
    // Convey selection in the spoken value, not by color alone (Req 9.5).
    final selectedSuffix = isSelected ? 'đã chọn' : 'chưa chọn';

    return Semantics(
      inMutuallyExclusiveGroup: true,
      selected: isSelected,
      button: true,
      label: '${option.label}, $selectedSuffix',
      child: ExcludeSemantics(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            minHeight: A11y.minTapTargetDimension,
          ),
          child: RadioListTile<String>(
            key: Key('language-option-${option.code}'),
            value: option.code,
            groupValue: groupValue,
            onChanged: (value) {
              if (value != null) {
                onSelected();
              }
            },
            controlAffinity: ListTileControlAffinity.trailing,
            title: Text(
              option.label,
              textScaler: textScaler,
            ),
          ),
        ),
      ),
    );
  }
}

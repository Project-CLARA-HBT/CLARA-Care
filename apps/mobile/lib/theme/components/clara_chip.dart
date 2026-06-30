// ClaraChip — a token-driven label chip for CLARA_Mobile Experience_V2
// (Requirements 2.2, 2.3).
//
// A compact, accessible chip used for tags, quick filters, and
// model-disclosure-like badges. It standardizes the small-surface look with a
// small corner radius (`ClaraTokens.radiusSm`) and token-based spacing, and
// adapts to three roles:
//
//   * Static badge — no [onTap], no [selected]: a presentational tag.
//   * Filter chip — [selected] provided (with optional [onTap]): a toggleable
//     quick filter whose selection state is conveyed by text/semantics, not
//     color alone (the screen reader hears "đã chọn"/"selected" via the
//     semantics value).
//   * Action chip — [onTap] provided: a tappable control announced as a button.
//
// An optional leading [icon] sits before the [label]. Semantics are exposed via
// `A11yLabeled`: interactive chips are marked as buttons, and the selected
// state (when applicable) is surfaced through the semantics `value`. Press
// feedback is timed through `A11y.resolveMotionDuration` so it collapses to
// instant under reduced motion (Requirement 2.4).
//
// Pure widget: no I/O, no analytics. The [label] (and any selected-state
// announcement text) is Vietnamese-first and supplied by callers — no
// hard-coded user-facing strings here.

import 'package:flutter/material.dart';

import '../../core/a11y.dart';
import '../tokens.dart';

/// A modern, token-driven label chip (tag / quick filter / disclosure badge).
class ClaraChip extends StatelessWidget {
  const ClaraChip({
    super.key,
    required this.label,
    this.icon,
    this.selected,
    this.onTap,
    this.selectedSemanticsValue,
  });

  /// The chip's text. Always rendered; Vietnamese-first, caller-supplied.
  final String label;

  /// Optional leading icon shown before [label].
  final IconData? icon;

  /// Toggle state for filter chips. When non-null the chip is rendered as a
  /// selectable filter and the selection is conveyed via semantics value.
  final bool? selected;

  /// Tap handler. When non-null the chip is interactive (announced as button).
  final VoidCallback? onTap;

  /// Optional spoken value announced when [selected] is true (e.g., "Đã chọn").
  /// When omitted, selection still toggles the underlying visual state but no
  /// extra value is spoken.
  final String? selectedSemanticsValue;

  /// Whether this chip is interactive (tappable or selectable).
  bool get _isInteractive => onTap != null || selected != null;

  /// Whether this chip is rendered in the selected state.
  bool get _isSelected => selected ?? false;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final shape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
    );

    final foreground =
        _isSelected ? scheme.onSecondaryContainer : scheme.onSurfaceVariant;
    final background =
        _isSelected ? scheme.secondaryContainer : scheme.surfaceContainerHighest;

    final row = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (icon != null) ...[
          Icon(icon, size: 16, color: foreground),
          const SizedBox(width: ClaraTokens.spaceXs),
        ],
        Flexible(
          child: Text(
            label,
            style: TextStyle(color: foreground, fontWeight: FontWeight.w500),
          ),
        ),
      ],
    );

    final body = Container(
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
      ),
      padding: const EdgeInsets.symmetric(
        horizontal: ClaraTokens.spaceMd,
        vertical: ClaraTokens.spaceSm,
      ),
      child: row,
    );

    final material = Material(
      color: Colors.transparent,
      shape: shape,
      clipBehavior: Clip.antiAlias,
      child: onTap != null
          ? InkWell(
              onTap: onTap,
              borderRadius: BorderRadius.circular(ClaraTokens.radiusSm),
              child: AnimatedContainer(
                duration: A11y.resolveMotionDuration(
                  context,
                  ClaraTokens.motionFast,
                ),
                child: body,
              ),
            )
          : body,
    );

    // Convey selection through semantics value (text/semantics, not color
    // alone) when the chip is a selectable filter.
    final semanticsValue =
        (selected != null && _isSelected) ? selectedSemanticsValue : null;

    if (_isInteractive) {
      return A11yLabeled(
        label: label,
        isButton: true,
        value: semanticsValue,
        child: material,
      );
    }

    return A11yLabeled(label: label, child: material);
  }
}

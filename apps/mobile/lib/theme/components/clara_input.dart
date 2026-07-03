// Text-input component for CLARA_Mobile Experience_V2 (Req 2.2, 2.3).
//
// `ClaraInput` is a thin wrapper over [TextFormField] that standardizes how the
// modern surfaces collect text. It deliberately adds no decoration of its own:
// the field's shape, fill, and borders come from the theme's
// `inputDecorationTheme` (token-driven radius, see `clara_theme.dart`), and the
// only spacing it introduces — the gap between the field and an external
// [errorText] line — is read from `ClaraTokens`. This keeps every input
// consistent and tunable in one place.
//
// Copy is caller-provided and Vietnamese-first: [label] and [hint] are required
// to be supplied by the call site (no hard-coded English strings live here), so
// screens own their localized wording.
//
// Accessibility (Requirement 2.3): the field honors the OS dynamic text-scaling
// preference through `A11y.resolveTextScaler`, clamped so large text stays
// legible without clipping. The visible [label] doubles as the field's
// screen-reader name via the underlying [InputDecoration].

import 'package:flutter/material.dart';

import '../../core/a11y.dart';

/// A token- and theme-driven single-line text field.
///
/// Wraps [TextFormField] so all styling flows from the active
/// `inputDecorationTheme`; the widget only forwards caller-provided content
/// ([label]/[hint]), behavior ([keyboardType], [obscureText]), and callbacks
/// ([onChanged], [validator]). Provide either a [validator] (form-driven errors)
/// or an [errorText] (externally-managed error), not both, depending on how the
/// surrounding screen manages validation state.
class ClaraInput extends StatelessWidget {
  const ClaraInput({
    super.key,
    required this.label,
    this.hint,
    this.controller,
    this.validator,
    this.obscureText = false,
    this.keyboardType,
    this.onChanged,
    this.errorText,
    this.enabled = true,
    this.textInputAction,
    this.focusNode,
    this.maxLines = 1,
  });

  /// Visible field label and screen-reader name (caller-provided, localized).
  final String label;

  /// Optional placeholder shown when the field is empty (caller-provided,
  /// localized).
  final String? hint;

  /// Optional external controller for the field's text.
  final TextEditingController? controller;

  /// Optional form validator; returns an error string or `null` when valid.
  final String? Function(String value)? validator;

  /// Whether to obscure input (e.g., passwords). Defaults to `false`.
  final bool obscureText;

  /// Optional soft-keyboard type hint.
  final TextInputType? keyboardType;

  /// Optional change callback fired on each edit.
  final ValueChanged<String>? onChanged;

  /// Optional externally-managed error message shown beneath the field.
  final String? errorText;

  /// Whether the field accepts input. Defaults to `true`.
  final bool enabled;

  /// Optional keyboard action button hint.
  final TextInputAction? textInputAction;

  /// Optional focus node for managing focus/traversal order.
  final FocusNode? focusNode;

  /// Maximum number of lines the field expands to. Defaults to `1` (single
  /// line); pass a larger value (or `null`) for multiline fields such as notes.
  /// Ignored when [obscureText] is true (obscured fields are always single
  /// line).
  final int? maxLines;

  @override
  Widget build(BuildContext context) {
    // Honor OS text scaling (clamped) so labels/hints/value stay legible
    // without clipping (Requirement 2.3).
    final textScaler = A11y.resolveTextScaler(context);

    return MediaQuery(
      data: MediaQuery.of(context).copyWith(textScaler: textScaler),
      child: TextFormField(
        controller: controller,
        focusNode: focusNode,
        enabled: enabled,
        obscureText: obscureText,
        maxLines: obscureText ? 1 : maxLines,
        keyboardType: keyboardType,
        textInputAction: textInputAction,
        onChanged: onChanged,
        // Adapt the form validator (value-only) to the framework signature.
        validator:
            validator == null ? null : (value) => validator!(value ?? ''),
        // Decoration geometry/fill/borders come from `inputDecorationTheme`;
        // only the caller's copy and any external error are supplied here.
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          errorText: errorText,
        ),
      ),
    );
  }
}

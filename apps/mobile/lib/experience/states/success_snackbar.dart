// Themed confirmation snackbars for CLARA_Mobile Experience_V2
// (Requirement 6.3).
//
// Helpers that surface a clear, Vietnamese-first confirmation after a mutating
// action succeeds (and lightweight error/info variants for parity). Each builds
// a themed [SnackBar] whose shape/spacing read from `ClaraTokens` and whose
// colors come from the active M3 `ColorScheme`, then shows it through the
// ambient `ScaffoldMessenger`.
//
// These are intentionally separate from the persistent error/offline surfaces:
// a failed *load* should use `ErrorRetryView`
// (`lib/widgets/error_retry_view.dart`) and offline state should use
// `OfflineBanner` (`lib/widgets/offline_banner.dart`). The error snackbar here
// is only for transient, non-blocking feedback on an action.
//
// Accessibility:
//   * A leading icon is decorative reinforcement only; the message text carries
//     the meaning so status is never conveyed by color alone (Requirement 9.5).
//   * The message is wrapped in a live-region `Semantics` so assistive tech
//     announces it when the snackbar appears.
//
// Pure UI: no analytics, no I/O. Returns the controller so callers can await
// dismissal if needed.

import 'package:flutter/material.dart';

import '../../theme/tokens.dart';

/// Vietnamese-first default success message (Requirement 6.3).
const String kClaraSuccessMessage = 'Đã lưu thành công.';

/// Vietnamese-first default error message for a transient action failure.
const String kClaraErrorMessage = 'Đã xảy ra lỗi. Vui lòng thử lại.';

/// Severity of a CLARA snackbar; selects the reinforcing icon/color.
enum ClaraSnackBarLevel { success, error, info }

/// Shows a themed **success** confirmation snackbar (Requirement 6.3).
///
/// ```dart
/// showClaraSuccessSnackBar(context); // "Đã lưu thành công."
/// showClaraSuccessSnackBar(context, 'Đã cập nhật hồ sơ.');
/// ```
ScaffoldFeatureController<SnackBar, SnackBarClosedReason>
    showClaraSuccessSnackBar(
  BuildContext context, [
  String message = kClaraSuccessMessage,
]) =>
        _showClaraSnackBar(
          context,
          message: message,
          level: ClaraSnackBarLevel.success,
        );

/// Shows a themed **error** snackbar for transient, non-blocking action
/// feedback. For a failed data *load*, prefer the persistent `ErrorRetryView`.
ScaffoldFeatureController<SnackBar, SnackBarClosedReason>
    showClaraErrorSnackBar(
  BuildContext context, [
  String message = kClaraErrorMessage,
]) =>
        _showClaraSnackBar(
          context,
          message: message,
          level: ClaraSnackBarLevel.error,
        );

/// Shows a themed neutral **info** snackbar.
ScaffoldFeatureController<SnackBar, SnackBarClosedReason>
    showClaraInfoSnackBar(
  BuildContext context,
  String message,
) =>
        _showClaraSnackBar(
          context,
          message: message,
          level: ClaraSnackBarLevel.info,
        );

/// Builds a themed [SnackBar] for [message] at [level], consuming
/// [ClaraTokens] for shape/spacing and the active [ColorScheme] for color.
///
/// Exposed for callers that need to compose the snackbar themselves (e.g.,
/// adding an action); most call sites should use the `show…` helpers.
SnackBar buildClaraSnackBar(
  BuildContext context, {
  required String message,
  ClaraSnackBarLevel level = ClaraSnackBarLevel.success,
  SnackBarAction? action,
}) {
  final scheme = Theme.of(context).colorScheme;
  final (Color background, Color foreground, IconData icon) =
      _styleFor(level, scheme);

  return SnackBar(
    behavior: SnackBarBehavior.floating,
    backgroundColor: background,
    margin: const EdgeInsets.all(ClaraTokens.spaceMd),
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(ClaraTokens.radiusMd),
    ),
    action: action,
    content: Semantics(
      liveRegion: true,
      label: message,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Decorative reinforcement only — the message text carries meaning.
          ExcludeSemantics(
            child: Icon(icon, size: 20, color: foreground),
          ),
          const SizedBox(width: ClaraTokens.spaceSm),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: foreground),
            ),
          ),
        ],
      ),
    ),
  );
}

/// Resolves to per-level (background, foreground, icon).
(Color, Color, IconData) _styleFor(
  ClaraSnackBarLevel level,
  ColorScheme scheme,
) {
  switch (level) {
    case ClaraSnackBarLevel.success:
      return (
        scheme.primaryContainer,
        scheme.onPrimaryContainer,
        Icons.check_circle_outline,
      );
    case ClaraSnackBarLevel.error:
      return (
        scheme.errorContainer,
        scheme.onErrorContainer,
        Icons.error_outline,
      );
    case ClaraSnackBarLevel.info:
      return (
        scheme.secondaryContainer,
        scheme.onSecondaryContainer,
        Icons.info_outline,
      );
  }
}

/// Clears any in-flight snackbar and shows the themed one for [message].
ScaffoldFeatureController<SnackBar, SnackBarClosedReason> _showClaraSnackBar(
  BuildContext context, {
  required String message,
  required ClaraSnackBarLevel level,
}) {
  final messenger = ScaffoldMessenger.of(context)..hideCurrentSnackBar();
  return messenger.showSnackBar(
    buildClaraSnackBar(context, message: message, level: level),
  );
}

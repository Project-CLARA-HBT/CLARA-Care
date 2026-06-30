import 'package:flutter/material.dart';

// =============================================================================
// ErrorRetryView — shared, reusable error state for every data surface.
// clara-mobile-feature-parity Task 12.1 (Requirements 9.1, 11.1; Property P12).
//
//   * 9.1  Every data surface presents a clear, non-PII error/offline state
//          with a retry affordance.
//   * 11.1 Error copy is descriptive, PII-free and Vietnamese-first.
//   * 10.x Accessibility: status is conveyed by text/semantics (not color
//          alone), the retry control exposes a semantics label, and meets the
//          platform minimum touch target (>= 48dp).
//
// This widget renders no PII itself; callers pass an already-sanitized message
// (typically `ApiException.message`, which is Vietnamese-first and PII-free, or
// the [kDefaultErrorMessage] fallback). It never logs or transmits anything.
// =============================================================================

/// Minimum interactive touch target, mirroring the platform/web a11y floor
/// (Requirement 10.2).
const double kMinTouchTarget = 48.0;

/// Default Vietnamese-first, PII-free error copy (Requirement 11.1).
const String kDefaultErrorMessage =
    'Đã xảy ra lỗi khi tải dữ liệu. Vui lòng thử lại.';

/// Default Vietnamese-first retry label.
const String kDefaultRetryLabel = 'Thử lại';

/// A centered error state with a message and a retry button.
///
/// Drop this into any data surface's error branch:
///
/// ```dart
/// if (_error != null) {
///   return ErrorRetryView(message: _error!, onRetry: _load);
/// }
/// ```
///
/// The [message] must already be sanitized (PII-free, Vietnamese-first); the
/// widget does not transform or log it. Status is communicated through the
/// message text and semantics, never by color alone (Requirement 10.5).
class ErrorRetryView extends StatelessWidget {
  const ErrorRetryView({
    super.key,
    this.message = kDefaultErrorMessage,
    required this.onRetry,
    this.retryLabel = kDefaultRetryLabel,
    this.icon = Icons.error_outline,
    this.padding = const EdgeInsets.all(24),
  });

  /// Sanitized, PII-free, Vietnamese-first message to display.
  final String message;

  /// Invoked when the user taps the retry control.
  final VoidCallback onRetry;

  /// Label for the retry control.
  final String retryLabel;

  /// Leading status icon (decorative; the message carries the meaning).
  final IconData icon;

  /// Outer padding around the centered content.
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: padding,
        child: Column(
          key: const Key('error-retry-view'),
          mainAxisSize: MainAxisSize.min,
          children: [
            // Decorative icon: excluded from semantics so the message text is
            // the single, authoritative status announcement (Requirement 10.5).
            ExcludeSemantics(
              child: Icon(icon, size: 40, color: scheme.error),
            ),
            const SizedBox(height: 12),
            Semantics(
              liveRegion: true,
              label: message,
              child: Text(
                message,
                textAlign: TextAlign.center,
                style: TextStyle(color: scheme.error),
              ),
            ),
            const SizedBox(height: 16),
            Semantics(
              button: true,
              label: retryLabel,
              child: FilledButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: Text(retryLabel),
                style: FilledButton.styleFrom(
                  minimumSize:
                      const Size(kMinTouchTarget, kMinTouchTarget),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

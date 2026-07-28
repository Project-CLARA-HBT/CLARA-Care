import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'error_retry_view.dart';

// =============================================================================
// ScreenErrorBoundary — screen-level exception containment.
// clara-mobile-feature-parity Task 12.5 (Requirement 11.4).
//
//   * 11.4 WHEN an unexpected exception occurs in a screen, THE Mobile_App
//          SHALL contain it within the screen and SHALL NOT crash the app or
//          leak the stack trace to the user.
//
// Containment has two layers:
//
//   1. A reusable [ScreenErrorBoundary] widget that screens wrap their body in.
//      When a descendant throws during build/layout, the failed subtree is
//      replaced — in place, inside the boundary — with the shared, non-PII
//      [ErrorRetryView] fallback (Vietnamese-first copy, a retry affordance).
//      The retry reconstructs the subtree so a transient failure can recover.
//
//   2. A documented, opt-in global install ([ScreenErrorBoundary.install]) that
//      overrides [ErrorWidget.builder] so that ANY uncaught build-phase error
//      anywhere in the app renders a clean fallback instead of the framework's
//      red error screen with a raw stack trace. Call it once from `main()`
//      before `runApp` as a safety net; it is idempotent.
//
// This widget renders no PII: the fallback uses the shared, pre-sanitized
// [kDefaultErrorMessage] (or a caller-supplied, already-sanitized message). The
// raw exception / stack trace is never surfaced to the user; in debug builds it
// is still reported to the console via [FlutterError.presentError] for the
// developer, but never shown in the UI.
// =============================================================================

/// Builds the fallback shown when a contained error is caught.
///
/// [details] is the captured framework error (developer-facing only — never
/// render its `exception`/`stack` to the user). [retry] reconstructs the
/// guarded subtree.
typedef ScreenErrorFallbackBuilder = Widget Function(
  BuildContext context,
  FlutterErrorDetails details,
  VoidCallback retry,
);

// --- Global clean ErrorWidget.builder install -------------------------------

ErrorWidgetBuilder? _originalErrorWidgetBuilder;
bool _cleanBuilderInstalled = false;

/// Installs (once) a clean, non-PII [ErrorWidget.builder].
///
/// The replacement reads the nearest [ScreenErrorBoundary] from the errored
/// element's context (the fallback is inflated at the failed subtree's
/// location, which is a descendant of the boundary) so it can show the
/// boundary's message and wire up its retry. With no boundary ancestor it falls
/// back to a bare, layout-safe, non-PII message — still no stack trace.
void _ensureCleanErrorWidgetBuilder() {
  if (_cleanBuilderInstalled) return;
  _cleanBuilderInstalled = true;
  _originalErrorWidgetBuilder = ErrorWidget.builder;
  ErrorWidget.builder = (FlutterErrorDetails details) {
    // In debug, surface the error to the developer console (no PII beyond the
    // exception itself, never shown to the user). In release this is a no-op.
    if (kDebugMode) {
      FlutterError.presentError(details);
    }
    return _FallbackErrorWidget(details: details);
  };
}

/// Inherited handle exposed by [ScreenErrorBoundary] to its subtree so the
/// replacement [ErrorWidget] can render the boundary's fallback and retry.
class _BoundaryScope extends InheritedWidget {
  const _BoundaryScope({
    required this.message,
    required this.retryLabel,
    required this.onRetry,
    required this.retry,
    required this.fallbackBuilder,
    required super.child,
  });

  final String message;
  final String retryLabel;
  final VoidCallback? onRetry;
  final VoidCallback retry;
  final ScreenErrorFallbackBuilder? fallbackBuilder;

  static _BoundaryScope? maybeOf(BuildContext context) {
    return context.dependOnInheritedWidgetOfExactType<_BoundaryScope>();
  }

  @override
  bool updateShouldNotify(_BoundaryScope oldWidget) {
    return message != oldWidget.message ||
        retryLabel != oldWidget.retryLabel ||
        onRetry != oldWidget.onRetry ||
        retry != oldWidget.retry ||
        fallbackBuilder != oldWidget.fallbackBuilder;
  }
}

/// The widget inflated in place of a subtree that threw during build.
///
/// It resolves the nearest [ScreenErrorBoundary] (if any) to render the shared
/// [ErrorRetryView] with the boundary's message and retry; otherwise it shows a
/// minimal, layout-safe, non-PII message. It NEVER renders the stack trace.
class _FallbackErrorWidget extends StatelessWidget {
  const _FallbackErrorWidget({required this.details});

  final FlutterErrorDetails details;

  @override
  Widget build(BuildContext context) {
    final scope = _BoundaryScope.maybeOf(context);
    if (scope != null) {
      if (scope.fallbackBuilder != null) {
        return scope.fallbackBuilder!(context, details, scope.retry);
      }
      return ErrorRetryView(
        message: scope.message,
        retryLabel: scope.retryLabel,
        onRetry: scope.retry,
      );
    }
    // No boundary ancestor: a bare, layout-safe, non-PII message. Wrapped so it
    // tolerates the unbounded constraints a raw ErrorWidget normally handles.
    return const _BareFallback();
  }
}

/// Minimal fallback used when no [ScreenErrorBoundary] is in scope. Renders
/// only the shared non-PII copy — never the stack trace — and is tolerant of
/// arbitrary layout constraints.
class _BareFallback extends StatelessWidget {
  const _BareFallback();

  @override
  Widget build(BuildContext context) {
    return Directionality(
      // Ensure text can lay out even if inflated outside a Directionality.
      textDirection: Directionality.maybeOf(context) ?? TextDirection.ltr,
      child: Container(
        key: const Key('screen-error-bare-fallback'),
        alignment: Alignment.center,
        padding: const EdgeInsets.all(24),
        child: const Text(
          kDefaultErrorMessage,
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}

/// Wraps a screen body so that an unexpected exception is contained within the
/// screen (Requirement 11.4) instead of crashing the app or leaking a stack
/// trace.
///
/// Usage — wrap a screen's body:
///
/// ```dart
/// @override
/// Widget build(BuildContext context) {
///   return Scaffold(
///     appBar: AppBar(title: const Text('Hồ sơ')),
///     body: ScreenErrorBoundary(
///       onRetry: _reload,
///       child: _buildBody(context),
///     ),
///   );
/// }
/// ```
///
/// For an app-wide safety net, also call [ScreenErrorBoundary.install] once in
/// `main()` before `runApp`.
class ScreenErrorBoundary extends StatefulWidget {
  const ScreenErrorBoundary({
    super.key,
    required this.child,
    this.message = kDefaultErrorMessage,
    this.retryLabel = kDefaultRetryLabel,
    this.onRetry,
    this.fallbackBuilder,
  });

  /// The guarded screen body.
  final Widget child;

  /// Sanitized, PII-free, Vietnamese-first message shown in the fallback.
  final String message;

  /// Label for the retry control in the fallback.
  final String retryLabel;

  /// Optional extra work to run when the user taps retry (e.g. re-fetch data).
  /// The guarded subtree is always reconstructed regardless.
  final VoidCallback? onRetry;

  /// Optional custom fallback builder. When null the shared [ErrorRetryView] is
  /// used. The builder MUST NOT render [FlutterErrorDetails.exception] or
  /// `stack` to the user.
  final ScreenErrorFallbackBuilder? fallbackBuilder;

  /// Whether the global clean [ErrorWidget.builder] has been installed.
  static bool get isInstalled => _cleanBuilderInstalled;

  /// Opt-in, idempotent global install. Override [ErrorWidget.builder] so any
  /// uncaught build-phase error renders a clean, non-PII fallback instead of
  /// the framework's red error screen / raw stack trace. Optionally route
  /// [FlutterError.onError] so uncaught framework errors are reported (debug
  /// console only) rather than presented to the user.
  ///
  /// Call once from `main()` before `runApp`:
  ///
  /// ```dart
  /// void main() {
  ///   WidgetsFlutterBinding.ensureInitialized();
  ///   ScreenErrorBoundary.install();
  ///   runApp(const ClaraApp());
  /// }
  /// ```
  ///
  /// For async/zone errors, additionally run the app inside
  /// `runZonedGuarded(() => runApp(...), (e, s) { /* log, no PII to user */ })`.
  static void install() {
    _ensureCleanErrorWidgetBuilder();
  }

  /// Restores the original [ErrorWidget.builder]. Intended for test teardown.
  @visibleForTesting
  static void debugReset() {
    if (_cleanBuilderInstalled && _originalErrorWidgetBuilder != null) {
      ErrorWidget.builder = _originalErrorWidgetBuilder!;
    }
    _cleanBuilderInstalled = false;
    _originalErrorWidgetBuilder = null;
  }

  /// Runs [action], containing any thrown/async error so it cannot escape and
  /// crash the surrounding flow. Returns the result, or null when contained.
  /// [onError] receives the (developer-facing) error for logging — never render
  /// it to the user.
  static Future<T?> guard<T>(
    Future<T> Function() action, {
    void Function(Object error, StackTrace stack)? onError,
  }) async {
    try {
      return await action();
    } catch (error, stack) {
      onError?.call(error, stack);
      return null;
    }
  }

  @override
  State<ScreenErrorBoundary> createState() => _ScreenErrorBoundaryState();
}

class _ScreenErrorBoundaryState extends State<ScreenErrorBoundary> {
  int _attempt = 0;

  void _retry() {
    widget.onRetry?.call();
    // Reconstruct the guarded subtree so a transient failure can recover.
    setState(() => _attempt++);
  }

  @override
  Widget build(BuildContext context) {
    return _BoundaryScope(
      message: widget.message,
      retryLabel: widget.retryLabel,
      onRetry: widget.onRetry,
      retry: _retry,
      fallbackBuilder: widget.fallbackBuilder,
      // A fresh key per attempt forces the previously-failed subtree to be
      // rebuilt from scratch on retry.
      child: KeyedSubtree(
        key: ValueKey<int>(_attempt),
        child: widget.child,
      ),
    );
  }
}

import 'package:flutter/material.dart';

import '../core/connectivity_service.dart';
import 'error_retry_view.dart';

// =============================================================================
// OfflineBanner + OfflineMutationGuard — shared offline/resilience primitives.
// clara-mobile-feature-parity Task 12.1 (Requirements 9.1, 9.4, 9.5; Property P12).
//
//   * 9.1 Every data surface can show a clear, non-PII offline state.
//   * 9.4 On reconnect the user can retry without losing entered input — the
//         guard never touches caller input, so it is preserved by construction.
//   * 9.5 Mutating operations (PHR save, cabinet add, scribe processing) are
//         blocked while offline rather than silently dropped, and the user is
//         informed.
//
// Both primitives consume the real [ConnectivityService]
// (`lib/core/connectivity_service.dart`) so screens behave consistently and so
// tests can drive connectivity deterministically. Neither logs nor transmits
// anything; all copy is Vietnamese-first and PII-free.
// =============================================================================

/// Default Vietnamese-first, PII-free offline banner copy (Requirement 9.1).
const String kDefaultOfflineMessage =
    'Bạn đang ngoại tuyến. Một số tính năng có thể không khả dụng.';

/// Default Vietnamese-first message shown when a mutation is blocked offline
/// (Requirement 9.5). The user's entered input is preserved for retry.
const String kOfflineMutationBlockedMessage =
    'Không có kết nối mạng. Thao tác đã được tạm dừng — dữ liệu bạn nhập vẫn '
    'được giữ lại. Vui lòng thử lại khi có mạng.';

/// A slim banner that appears only while the device is offline.
///
/// Place it at the top of any data surface (e.g. above a `ListView`):
///
/// ```dart
/// Column(children: [
///   OfflineBanner(connectivity: connectivity),
///   Expanded(child: body),
/// ]);
/// ```
///
/// It subscribes to [ConnectivityService.isOnline], seeding from
/// [ConnectivityService.currentValue], and collapses to zero height while
/// online. Status is conveyed by text and semantics, not color alone
/// (Requirement 10.5).
class OfflineBanner extends StatelessWidget {
  const OfflineBanner({
    super.key,
    required this.connectivity,
    this.message = kDefaultOfflineMessage,
    this.onRetry,
  });

  /// Connectivity signal to observe.
  final ConnectivityService connectivity;

  /// Sanitized, PII-free, Vietnamese-first banner message.
  final String message;

  /// Optional retry affordance (e.g. re-probe connectivity / reload).
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<bool>(
      stream: connectivity.isOnline,
      initialData: connectivity.currentValue,
      builder: (context, snapshot) {
        final online = snapshot.data ?? true;
        if (online) {
          return const SizedBox.shrink();
        }
        final scheme = Theme.of(context).colorScheme;
        return Semantics(
          liveRegion: true,
          label: message,
          child: Material(
            color: scheme.errorContainer,
            child: Padding(
              key: const Key('offline-banner'),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(
                children: [
                  ExcludeSemantics(
                    child: Icon(
                      Icons.cloud_off,
                      size: 18,
                      color: scheme.onErrorContainer,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      message,
                      style: TextStyle(
                        color: scheme.onErrorContainer,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  if (onRetry != null)
                    Semantics(
                      button: true,
                      label: kDefaultRetryLabel,
                      child: TextButton(
                        onPressed: onRetry,
                        style: TextButton.styleFrom(
                          minimumSize:
                              const Size(kMinTouchTarget, kMinTouchTarget),
                          foregroundColor: scheme.onErrorContainer,
                        ),
                        child: const Text(kDefaultRetryLabel),
                      ),
                    ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Outcome of evaluating whether a mutation may proceed (Property P12).
class MutationGuardResult {
  const MutationGuardResult._(this.allowed, this.message);

  /// The mutation may proceed (the device is online).
  const MutationGuardResult.allowed() : this._(true, null);

  /// The mutation is blocked offline; [message] explains why and reassures the
  /// user that entered input is preserved.
  const MutationGuardResult.blocked(String message) : this._(false, message);

  /// Whether the mutation may proceed.
  final bool allowed;

  /// User-facing, PII-free reason when [allowed] is false; otherwise null.
  final String? message;

  /// Whether the mutation was blocked.
  bool get blocked => !allowed;
}

/// Blocks mutating operations while offline without ever touching caller input,
/// so the user's entered data is preserved for retry (Requirements 9.4, 9.5;
/// Property P12).
///
/// Use it inside a screen's save/add handler:
///
/// ```dart
/// final ok = await guard.run(
///   isOnline: connectivity.currentValue,
///   mutate: () => apiClient.updatePhrRecord(...),
///   onBlocked: (msg) => ScaffoldMessenger.of(context)
///       .showSnackBar(SnackBar(content: Text(msg))),
/// );
/// // `ok == false` while offline; the form controllers are untouched.
/// ```
class OfflineMutationGuard {
  const OfflineMutationGuard({
    this.offlineMessage = kOfflineMutationBlockedMessage,
  });

  /// Vietnamese-first, PII-free message surfaced when a mutation is blocked.
  final String offlineMessage;

  /// Pure evaluation of whether a mutation may proceed given connectivity.
  /// Performs no I/O and mutates no state, so it is trivially testable and
  /// leaves caller input intact.
  MutationGuardResult evaluate({required bool isOnline}) {
    if (isOnline) {
      return const MutationGuardResult.allowed();
    }
    return MutationGuardResult.blocked(offlineMessage);
  }

  /// Runs [mutate] only when online. While offline the mutation is NOT invoked;
  /// [onBlocked] is called with a user-facing message and the method returns
  /// `false`. Because [mutate] is skipped entirely, any input the caller holds
  /// (text controllers, form state) is preserved for a later retry.
  ///
  /// Returns `true` iff [mutate] was invoked (i.e. the device was online).
  Future<bool> run({
    required bool isOnline,
    required Future<void> Function() mutate,
    required void Function(String message) onBlocked,
  }) async {
    final result = evaluate(isOnline: isOnline);
    if (result.blocked) {
      onBlocked(result.message!);
      return false;
    }
    await mutate();
    return true;
  }
}

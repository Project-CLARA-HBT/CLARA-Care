// Reusable test fake for the CLARA mobile feature-parity spec (task 1.1).
//
// The real `ConnectivityService` is introduced in task 1.2
// (`lib/core/connectivity_service.dart`). It does not exist yet, so this fake
// is written against the minimal interface the design specifies (design
// section I): an `isOnline` Stream<bool> plus the current value. Task 1.2 MUST
// make the real service conform to this surface so this fake remains a drop-in
// substitute (and can be updated to `implements ConnectivityService` once the
// production type lands).
//
// It backs the offline/resilience tests (Requirement 9; design Property 12 —
// offline write safety): a test can flip connectivity at will and assert that
// surfaces show the offline state and block mutations.

import 'dart:async';

/// Minimal connectivity contract the design requires (design section I).
///
/// This mirrors the surface task 1.2's real `ConnectivityService` must expose,
/// so production code and this fake stay interchangeable.
abstract class ConnectivityContract {
  /// The latest known connectivity state.
  bool get isOnlineNow;

  /// A stream that emits whenever connectivity changes. Implementations should
  /// expose a broadcast stream so multiple widgets can listen.
  Stream<bool> get isOnline;

  /// Releases any resources held by the service.
  void dispose();
}

/// A controllable [ConnectivityContract] for tests.
///
/// Construct online or offline, then drive transitions with [goOffline],
/// [goOnline], or [setOnline]. Listeners on [isOnline] receive every change;
/// the stream is a broadcast stream so a screen can subscribe in `initState`.
class FakeConnectivityService implements ConnectivityContract {
  FakeConnectivityService({bool online = true}) : _online = online;

  bool _online;
  final StreamController<bool> _controller = StreamController<bool>.broadcast();

  /// Number of state-change events emitted so far (useful for assertions).
  int emittedCount = 0;

  @override
  bool get isOnlineNow => _online;

  @override
  Stream<bool> get isOnline => _controller.stream;

  /// Sets connectivity to [online]; emits only when the value actually changes.
  void setOnline(bool online) {
    if (_online == online) {
      return;
    }
    _online = online;
    emittedCount++;
    _controller.add(online);
  }

  /// Convenience: transition to offline.
  void goOffline() => setOnline(false);

  /// Convenience: transition to online.
  void goOnline() => setOnline(true);

  @override
  void dispose() {
    _controller.close();
  }
}

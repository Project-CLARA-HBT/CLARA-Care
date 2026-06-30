import 'dart:async';

/// Connectivity / degraded-mode signal for CLARA_Mobile (Requirement 9.1).
///
/// Exposes a minimal, fakeable interface so every data surface can react to the
/// device going offline (show an offline/error state, block mutations) without
/// depending on a platform plugin. The contract is intentionally tiny:
///
///  * [isOnline] — a stream that emits the current value on subscribe and then
///    every subsequent change.
///  * [currentValue] — the last-known connectivity value, read synchronously.
///
/// Tests and the host app drive connectivity through an injectable
/// [ConnectivityProbe] (see [DefaultConnectivityService]) or by pushing values
/// directly, so no platform channel or new dependency is required.
abstract class ConnectivityService {
  /// Broadcast stream of connectivity values. On subscribe it immediately
  /// yields the current value, then emits on every change.
  Stream<bool> get isOnline;

  /// The last-known connectivity value, available synchronously.
  bool get currentValue;
}

/// A pluggable reachability probe: returns `true` when the network/API is
/// reachable. Kept as a function so the host can supply an HTTP/DNS check and
/// tests can supply a deterministic stub — no platform plugin needed.
typedef ConnectivityProbe = Future<bool> Function();

/// Default [ConnectivityService].
///
/// Dependency-light by design: it owns no platform plugin. Connectivity is
/// driven one of two ways, both injectable:
///
///  * Polling an injected [ConnectivityProbe] on a bounded [pollInterval]
///    (e.g. a lightweight HTTP HEAD or DNS lookup supplied by the host); a
///    probe that throws is treated as offline.
///  * Pushing values directly via [setOnline] (used by tests/host, or by the
///    networking layer when a request times out / a socket fails).
///
/// New listeners receive the current value first, then live changes. Duplicate
/// values are de-duplicated so the stream only emits on a real transition.
class DefaultConnectivityService implements ConnectivityService {
  DefaultConnectivityService({
    ConnectivityProbe? probe,
    Duration pollInterval = const Duration(seconds: 10),
    bool initialValue = true,
  })  : _probe = probe,
        _pollInterval = pollInterval,
        _current = initialValue {
    _controller = StreamController<bool>.broadcast();
    if (_probe != null) {
      _start();
    }
  }

  final ConnectivityProbe? _probe;
  final Duration _pollInterval;

  late final StreamController<bool> _controller;
  Timer? _timer;
  bool _current;
  bool _disposed = false;

  @override
  bool get currentValue => _current;

  @override
  Stream<bool> get isOnline async* {
    yield _current;
    yield* _controller.stream;
  }

  /// Pushes a connectivity value directly. Lets the host or tests drive the
  /// signal without a platform plugin (e.g. on a request timeout/socket error).
  /// No-op when the value is unchanged or the service has been disposed.
  void setOnline(bool value) => _update(value);

  /// Runs the injected probe once and publishes the result. A probe that
  /// throws is treated as offline. Returns the resolved value.
  Future<bool> refresh() async {
    if (_probe == null) {
      return _current;
    }
    bool reachable;
    try {
      reachable = await _probe();
    } catch (_) {
      reachable = false;
    }
    _update(reachable);
    return reachable;
  }

  void _start() {
    _timer ??= Timer.periodic(_pollInterval, (_) => refresh());
  }

  void _update(bool value) {
    if (_disposed || value == _current) {
      return;
    }
    _current = value;
    if (!_controller.isClosed) {
      _controller.add(value);
    }
  }

  /// Stops polling and closes the stream. Safe to call multiple times.
  void dispose() {
    if (_disposed) {
      return;
    }
    _disposed = true;
    _timer?.cancel();
    _timer = null;
    _controller.close();
  }
}

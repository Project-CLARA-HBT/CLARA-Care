// Reusable test fake for the CLARA mobile experience spec (task 1.1).
//
// A general-purpose in-memory secure storage for Experience_V2 widget/property
// tests. It generalizes the session-scoped `InMemorySessionSecureStorage`
// (see `fake_session_store.dart`) so the Experience_V2 persistence stores
// introduced in task 1.3 — `OnboardingStore` ("onboarding seen") and
// `LanguageStore` (language preference) — can be exercised deterministically,
// with no platform channels (the real `flutter_secure_storage` needs a device).
//
// It conforms to the project's existing `SessionSecureStorage` abstraction
// (positional `read`/`write`/`delete` by key) so it is a genuine drop-in
// wherever that contract is accepted, while adding two things widget/property
// tests for Experience_V2 need:
//
//   * Inspection helpers (`snapshot`, `isEmpty`, `containsKey`, read counters)
//     so a test can assert exactly what a store persisted.
//   * Fault injection (`throwOnRead`/`throwOnWrite`/`throwOnDelete`) so the
//     graceful-degradation defaults required by the design can be verified:
//     when secure storage is unavailable, onboarding falls back to "not seen"
//     and language falls back to the Vietnamese default, never crashing launch.
//
// Prefer this over per-file copies of an in-memory secure storage.

import 'package:clara_mobile/core/session_store.dart';

/// Controllable in-memory [SessionSecureStorage] for Experience_V2 tests.
///
/// Seed it with existing values to model a returning user (e.g. onboarding
/// already seen, a persisted language), drive transitions through the store
/// under test, then assert on [snapshot]. Flip the `throwOn*` switches to
/// simulate a secure-storage outage and verify graceful degradation.
class FakeSecureStorage implements SessionSecureStorage {
  FakeSecureStorage([Map<String, String>? seed])
      : _data = <String, String>{...?seed};

  final Map<String, String> _data;

  /// When true, [read] throws instead of returning a value — models a
  /// secure-storage read outage for graceful-degradation tests.
  bool throwOnRead = false;

  /// When true, [write] throws instead of persisting — models a write outage.
  bool throwOnWrite = false;

  /// When true, [delete] throws instead of removing a key.
  bool throwOnDelete = false;

  /// Number of [read] calls (including failed ones), for assertions.
  int readCount = 0;

  /// Number of successful [write] calls, for assertions.
  int writeCount = 0;

  /// Number of successful [delete] calls, for assertions.
  int deleteCount = 0;

  /// Read-only view of the currently persisted key/value pairs.
  Map<String, String> get snapshot => Map.unmodifiable(_data);

  /// Whether nothing is currently persisted.
  bool get isEmpty => _data.isEmpty;

  /// Whether [key] currently has a persisted value.
  bool containsKey(String key) => _data.containsKey(key);

  /// Directly seed/overwrite a value without going through the store under
  /// test — convenient for arranging a "returning user" precondition.
  void seed(String key, String value) {
    _data[key] = value;
  }

  /// Clears all persisted values and resets the call counters.
  void reset() {
    _data.clear();
    readCount = 0;
    writeCount = 0;
    deleteCount = 0;
    throwOnRead = false;
    throwOnWrite = false;
    throwOnDelete = false;
  }

  @override
  Future<String?> read(String key) async {
    readCount++;
    if (throwOnRead) {
      throw StateError('FakeSecureStorage.read failure (simulated outage)');
    }
    return _data[key];
  }

  @override
  Future<void> write(String key, String value) async {
    if (throwOnWrite) {
      throw StateError('FakeSecureStorage.write failure (simulated outage)');
    }
    _data[key] = value;
    writeCount++;
  }

  @override
  Future<void> delete(String key) async {
    if (throwOnDelete) {
      throw StateError('FakeSecureStorage.delete failure (simulated outage)');
    }
    _data.remove(key);
    deleteCount++;
  }
}

// Reusable test fakes for the CLARA mobile feature-parity spec (task 1.1).
//
// Session/credential fakes that keep widget and unit tests free of platform
// channels (the real `flutter_secure_storage` needs a device). They back the
// production [PersistentSessionStore]/[SessionStore] with an in-memory map, so
// tests exercise the genuine store contract (`setSession`/`hydrate`/`clear`,
// `isExpired`, `ChangeNotifier` notifications) without native I/O.
//
// Prefer these over per-file copies of `InMemorySessionSecureStorage`.

import 'package:clara_mobile/core/session_store.dart';

/// In-memory [SessionSecureStorage] for tests — no platform channels.
///
/// Inject into a real [PersistentSessionStore] to exercise its full behavior
/// (persist on login, restore on launch, clear on sign-out) deterministically.
class InMemorySessionSecureStorage implements SessionSecureStorage {
  InMemorySessionSecureStorage([Map<String, String>? seed])
      : _data = <String, String>{...?seed};

  final Map<String, String> _data;

  /// Read-only view of the currently persisted key/value pairs.
  Map<String, String> get snapshot => Map.unmodifiable(_data);

  /// Whether nothing is currently persisted (e.g., after `clear`).
  bool get isEmpty => _data.isEmpty;

  @override
  Future<String?> read(String key) async => _data[key];

  @override
  Future<void> write(String key, String value) async {
    _data[key] = value;
  }

  @override
  Future<void> delete(String key) async {
    _data.remove(key);
  }
}

/// Test factory helpers for building a ready-to-use [PersistentSessionStore]
/// backed by [InMemorySessionSecureStorage].
///
/// These are convenience constructors only — the returned object is the real
/// production store, so any behavior under test is the real behavior.
class FakeSessionStore {
  const FakeSessionStore._();

  /// An empty, unauthenticated store (no persisted credentials).
  static PersistentSessionStore empty({InMemorySessionSecureStorage? storage}) {
    return PersistentSessionStore(
      storage: storage ?? InMemorySessionSecureStorage(),
    );
  }

  /// An authenticated store with the given session already persisted.
  ///
  /// Defaults model a typical end-user session; pass [role] (e.g. `admin`,
  /// `doctor`) to drive role-gated surfaces. The returned store has already
  /// awaited [PersistentSessionStore.setSession], so it is authenticated on
  /// first pump.
  static Future<PersistentSessionStore> authenticated({
    String email = 'user@example.com',
    String accessToken = 'test-access-token',
    String refreshToken = 'test-refresh-token',
    String role = 'normal',
    InMemorySessionSecureStorage? storage,
  }) async {
    final store = PersistentSessionStore(
      storage: storage ?? InMemorySessionSecureStorage(),
    );
    await store.setSession(
      email: email,
      accessToken: accessToken,
      refreshToken: refreshToken,
      role: role,
    );
    return store;
  }
}

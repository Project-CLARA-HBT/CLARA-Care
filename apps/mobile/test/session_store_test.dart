// Feature: product-polish-analytics, Property 19/20
//
// Dart tests for the persistent mobile session store
// (`PersistentSessionStore` in `lib/core/session_store.dart`).
//
// These cover two design properties:
//
//   * Property 19 — Session persists and restores across restart, and clears
//     on sign-out. (Validates: Requirements 10.1, 10.2, 10.5)
//   * Property 20 — Expired or invalid stored tokens clear the store and route
//     to login. (Validates: Requirements 10.3)
//
// The tests inject an in-memory [SessionSecureStorage] double so they run
// without platform channels, and they use real-looking JWTs
// (header.payload.signature with a base64url-encoded `exp` claim). Each
// property is exercised across many generated inputs (>=200 iterations) to
// approximate property-based testing in Dart, complemented by example-based
// unit tests for important edge cases.

import 'dart:convert';
import 'dart:math';

import 'package:clara_mobile/core/session_store.dart';
import 'package:flutter_test/flutter_test.dart';

/// In-memory [SessionSecureStorage] test double.
///
/// Backs the store with a plain [Map] so no platform secure-storage channel is
/// touched. The same instance can be shared between two store objects to
/// simulate an app restart (write with one store, hydrate with another).
class InMemorySessionSecureStorage implements SessionSecureStorage {
  InMemorySessionSecureStorage([Map<String, String>? seed])
      : _data = {...?seed};

  final Map<String, String> _data;

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

  /// Number of entries currently persisted.
  int get length => _data.length;

  /// Whether any credential is still persisted.
  bool get isEmpty => _data.isEmpty;

  /// Immutable snapshot of the current contents (useful for assertions).
  Map<String, String> get snapshot => Map.unmodifiable(_data);
}

/// Base64url-encodes a JSON map without padding, matching how real JWT
/// libraries emit segments. The store normalizes padding on decode.
String _encodeSegment(Map<String, dynamic> map) {
  return base64Url.encode(utf8.encode(jsonEncode(map))).replaceAll('=', '');
}

/// Builds a real-looking JWT (`header.payload.signature`).
///
/// [extraClaims] are merged into the payload alongside [exp] (seconds since
/// epoch), so generated tokens look like genuine credentials.
String buildJwt({
  int? exp,
  Map<String, dynamic> extraClaims = const {},
  Map<String, dynamic>? header,
}) {
  final headerSegment = _encodeSegment(
    header ?? const {'alg': 'HS256', 'typ': 'JWT'},
  );
  final payload = <String, dynamic>{...extraClaims};
  if (exp != null) {
    payload['exp'] = exp;
  }
  final payloadSegment = _encodeSegment(payload);
  // A fixed opaque signature segment — the store never verifies signatures,
  // it only parses the payload's `exp` claim.
  const signature = 'c2lnbmF0dXJlLXBsYWNlaG9sZGVy';
  return '$headerSegment.$payloadSegment.$signature';
}

/// Seconds-since-epoch [Duration] offset from now (positive = future).
int _epochSecondsFromNow(Duration offset) {
  return DateTime.now().toUtc().add(offset).millisecondsSinceEpoch ~/ 1000;
}

String _randomString(Random rng, int length) {
  const chars =
      'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_';
  return String.fromCharCodes(
    List.generate(length, (_) => chars.codeUnitAt(rng.nextInt(chars.length))),
  );
}

void main() {
  const roles = <String>['normal', 'researcher', 'doctor', 'admin'];

  group('Property 19: persists, restores across restart, clears on sign-out',
      () {
    // Property: for any valid login result, the credentials written to the
    // persistent store are returned unchanged when a fresh store is
    // re-initialized from the SAME storage; after clear() the store is empty
    // and unauthenticated.
    test('restored session matches and clear() empties the store (generated)',
        () async {
      final rng = Random(20240519);
      const iterations = 250;

      for (var i = 0; i < iterations; i++) {
        // Generate a valid (future-dated) credential set.
        final email = '${_randomString(rng, 1 + rng.nextInt(12))}@example.com';
        final role = roles[rng.nextInt(roles.length)];
        final futureExp = _epochSecondsFromNow(
          // 1 hour .. ~2000 days in the future.
          Duration(seconds: 3600 + rng.nextInt(2000 * 24 * 3600)),
        );
        final accessToken = buildJwt(
          exp: futureExp,
          extraClaims: {
            'sub': _randomString(rng, 8),
            'role': role,
          },
        );
        final refreshToken = buildJwt(
          exp: _epochSecondsFromNow(
            Duration(seconds: futureExp + rng.nextInt(86400)),
          ),
          extraClaims: {'typ': 'refresh', 'jti': _randomString(rng, 6)},
        );

        // Shared storage simulates the device keychain across a restart.
        final storage = InMemorySessionSecureStorage();

        // First store writes the session (10.1).
        final writer = PersistentSessionStore(storage: storage);
        await writer.setSession(
          email: email,
          accessToken: accessToken,
          refreshToken: refreshToken,
          role: role,
        );
        expect(writer.isAuthenticated, isTrue,
            reason: 'writer should be authenticated after setSession');

        // Fresh store re-initializes from the SAME storage and hydrates,
        // simulating an app restart (10.2).
        final restored = PersistentSessionStore(storage: storage);
        await restored.hydrate();

        expect(restored.isAuthenticated, isTrue,
            reason: 'restored store should be authenticated on iteration $i');
        expect(restored.isExpired, isFalse);
        expect(restored.email, equals(email));
        expect(restored.accessToken, equals(accessToken));
        expect(restored.refreshToken, equals(refreshToken));
        expect(restored.role, equals(role));

        // Sign-out clears all credentials from memory and storage (10.5).
        await restored.clear();

        expect(restored.isAuthenticated, isFalse);
        expect(restored.email, isNull);
        expect(restored.accessToken, isNull);
        expect(restored.refreshToken, isNull);
        expect(restored.role, isNull);
        expect(storage.isEmpty, isTrue,
            reason: 'storage should be empty after clear() on iteration $i');
      }
    });

    test('example: a concrete valid session round-trips across restart',
        () async {
      final storage = InMemorySessionSecureStorage();
      final accessToken =
          buildJwt(exp: _epochSecondsFromNow(const Duration(days: 30)));
      final refreshToken =
          buildJwt(exp: _epochSecondsFromNow(const Duration(days: 60)));

      final writer = PersistentSessionStore(storage: storage);
      await writer.setSession(
        email: 'nguyen@example.com',
        accessToken: accessToken,
        refreshToken: refreshToken,
        role: 'doctor',
      );

      final restored = PersistentSessionStore(storage: storage);
      await restored.hydrate();

      expect(restored.isAuthenticated, isTrue);
      expect(restored.email, 'nguyen@example.com');
      expect(restored.accessToken, accessToken);
      expect(restored.refreshToken, refreshToken);
      expect(restored.role, 'doctor');

      await restored.clear();
      expect(restored.isAuthenticated, isFalse);
      expect(storage.isEmpty, isTrue);
    });

    test('example: hydrate with empty storage stays unauthenticated', () async {
      final storage = InMemorySessionSecureStorage();
      final store = PersistentSessionStore(storage: storage);

      await store.hydrate();

      expect(store.isAuthenticated, isFalse);
      expect(store.email, isNull);
      expect(store.accessToken, isNull);
      expect(storage.isEmpty, isTrue);
    });
  });

  group('Property 20: expired/invalid stored tokens clear the store', () {
    // Property: for any expired or invalid persisted token, launch
    // initialization (hydrate) clears the store and reports unauthenticated
    // (which routes the app to the login screen).
    test('expired tokens clear the store on hydrate (generated)', () async {
      final rng = Random(99887766);
      const iterations = 250;

      for (var i = 0; i < iterations; i++) {
        final expiredExp = _epochSecondsFromNow(
          // 1 second .. ~365 days in the past.
          Duration(seconds: -(1 + rng.nextInt(365 * 24 * 3600))),
        );
        final expiredToken = buildJwt(
          exp: expiredExp,
          extraClaims: {'sub': _randomString(rng, 8)},
        );

        // Seed storage directly with an expired session, as if persisted by a
        // previous (now stale) login.
        final storage = InMemorySessionSecureStorage({
          PersistentSessionStore.emailKey:
              '${_randomString(rng, 6)}@example.com',
          PersistentSessionStore.accessTokenKey: expiredToken,
          PersistentSessionStore.refreshTokenKey: _randomString(rng, 24),
          PersistentSessionStore.roleKey: roles[rng.nextInt(roles.length)],
        });

        final store = PersistentSessionStore(storage: storage);
        await store.hydrate();

        expect(store.isAuthenticated, isFalse,
            reason: 'expired token should not authenticate on iteration $i');
        expect(store.accessToken, isNull);
        expect(store.email, isNull);
        expect(store.role, isNull);
        expect(storage.isEmpty, isTrue,
            reason: 'expired session should be cleared from storage');
      }
    });

    test('invalid/malformed tokens clear the store on hydrate (generated)',
        () async {
      final rng = Random(54321);
      const iterations = 250;

      for (var i = 0; i < iterations; i++) {
        // Generate a variety of structurally invalid tokens.
        final variant = rng.nextInt(6);
        late final String invalidToken;
        switch (variant) {
          case 0:
            // Not a JWT at all.
            invalidToken = _randomString(rng, 1 + rng.nextInt(40));
            break;
          case 1:
            // Wrong number of segments.
            invalidToken =
                '${_randomString(rng, 6)}.${_randomString(rng, 6)}';
            break;
          case 2:
            // Three segments but the payload is not valid base64/JSON.
            invalidToken =
                '${_randomString(rng, 6)}.!!!not-base64!!!.${_randomString(rng, 6)}';
            break;
          case 3:
            // Valid JWT shape but no `exp` claim.
            invalidToken = buildJwt(extraClaims: {'sub': _randomString(rng, 8)});
            break;
          case 4:
            // `exp` present but wrong type (non-numeric string).
            invalidToken = buildJwt(extraClaims: {'exp': 'not-a-number'});
            break;
          default:
            // Payload is a JSON array, not an object.
            final payloadSegment = base64Url
                .encode(utf8.encode(jsonEncode([1, 2, 3])))
                .replaceAll('=', '');
            invalidToken =
                '${_randomString(rng, 6)}.$payloadSegment.${_randomString(rng, 6)}';
        }

        final storage = InMemorySessionSecureStorage({
          PersistentSessionStore.emailKey:
              '${_randomString(rng, 6)}@example.com',
          PersistentSessionStore.accessTokenKey: invalidToken,
          PersistentSessionStore.refreshTokenKey: _randomString(rng, 24),
          PersistentSessionStore.roleKey: roles[rng.nextInt(roles.length)],
        });

        final store = PersistentSessionStore(storage: storage);
        await store.hydrate();

        expect(store.isAuthenticated, isFalse,
            reason: 'invalid token (variant $variant) should not authenticate');
        expect(store.accessToken, isNull);
        expect(storage.isEmpty, isTrue,
            reason: 'invalid session should be cleared from storage');
      }
    });

    test('example: token expiring exactly now is treated as expired', () async {
      final nowExp = _epochSecondsFromNow(Duration.zero);
      final storage = InMemorySessionSecureStorage({
        PersistentSessionStore.accessTokenKey: buildJwt(exp: nowExp),
        PersistentSessionStore.emailKey: 'edge@example.com',
        PersistentSessionStore.refreshTokenKey: 'refresh',
        PersistentSessionStore.roleKey: 'normal',
      });

      final store = PersistentSessionStore(storage: storage);
      await store.hydrate();

      expect(store.isAuthenticated, isFalse);
      expect(storage.isEmpty, isTrue);
    });

    test('example: empty-string stored token clears and stays logged out',
        () async {
      final storage = InMemorySessionSecureStorage({
        PersistentSessionStore.accessTokenKey: '',
        PersistentSessionStore.emailKey: 'blank@example.com',
      });

      final store = PersistentSessionStore(storage: storage);
      await store.hydrate();

      expect(store.isAuthenticated, isFalse);
      expect(store.accessToken, isNull);
    });
  });
}

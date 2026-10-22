import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Minimal key/value abstraction over the platform secure storage.
///
/// Defining this interface keeps [PersistentSessionStore] testable: production
/// code uses [FlutterSecureSessionStorage] (backed by `flutter_secure_storage`)
/// while tests can inject an in-memory implementation without platform
/// channels.
abstract class SessionSecureStorage {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
}

/// Default [SessionSecureStorage] backed by `flutter_secure_storage`.
class FlutterSecureSessionStorage implements SessionSecureStorage {
  FlutterSecureSessionStorage([
    FlutterSecureStorage? storage,
    bool biometricProtection = false,
  ]) : _storage =
            storage ?? defaultStorage(biometricProtection: biometricProtection);

  /// Hardened hardware-backed storage options:
  /// - Android: EncryptedSharedPreferences backed by Android Keystore MasterKey (AES-256-GCM)
  ///   with auto-reset on cryptographic error to prevent unrecoverable crashes.
  /// - iOS: Non-synchronizable Keychain (disabled iCloud backup sync) with
  ///   KeychainAccessibility.first_unlock_this_device (or unlocked_this_device when biometric is active).
  static FlutterSecureStorage defaultStorage({
    bool biometricProtection = false,
  }) {
    return FlutterSecureStorage(
      aOptions: const AndroidOptions(
        encryptedSharedPreferences: true,
        resetOnError: true,
      ),
      iOptions: IOSOptions(
        accessibility: biometricProtection
            ? KeychainAccessibility.unlocked_this_device
            : KeychainAccessibility.first_unlock_this_device,
        synchronizable: false,
      ),
    );
  }

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);

  @override
  Future<void> delete(String key) => _storage.delete(key: key);
}

/// Persistent session/credential store for CLARA_Mobile.
///
/// Replaces the previous in-memory store with one backed by secure storage
/// while preserving the original [ChangeNotifier] public API (fields,
/// [setSession], [clear], [isAuthenticated]) so existing screens are
/// unaffected. New capabilities:
///
/// * [hydrate] — load persisted credentials on launch (10.2); clears the store
///   when the stored token is expired/invalid (10.3).
/// * [setSession] — persists credentials to secure storage (10.1).
/// * [clear] — removes all stored credentials (10.5).
/// * [isExpired] — pure token-expiry check used during [hydrate] (10.3).
class PersistentSessionStore extends ChangeNotifier {
  PersistentSessionStore({SessionSecureStorage? storage})
      : _storage = storage ?? FlutterSecureSessionStorage();

  static const String emailKey = 'clara.session.email';
  static const String accessTokenKey = 'clara.session.access_token';
  static const String refreshTokenKey = 'clara.session.refresh_token';
  static const String roleKey = 'clara.session.role';
  static const String organizationIdKey = 'clara.session.organization_id';
  static const String biometricEnabledKey = 'clara.settings.biometric_enabled';

  // Offline cache storage keys (kept in sync with CareguardOfflineCache and LifeMapReadCache).
  static const String careguardOfflineCacheKey =
      'clara.careguard.ddi.last_known_view';
  static const String lifeMapReadCacheKey =
      'clara.lifemap.today.read_projection';
  static const String lifeMapCaptureSessionKey =
      'clara.lifemap.capture.active_session';

  static String careguardScopedKey(String userId) =>
      'clara.careguard.ddi.$userId.last_known_view';

  static String lifeMapScopedKey(String userId) =>
      'clara.lifemap.today.$userId.read_projection';

  final SessionSecureStorage _storage;

  String? _email;
  String? _accessToken;
  String? _refreshToken;
  String? _role;
  String? _organizationId;
  bool _biometricEnabled = false;
  bool _biometricLocked = false;

  String? get email => _email;
  String? get accessToken => _accessToken;
  String? get refreshToken => _refreshToken;
  String? get role => _role;
  String? get organizationId => _organizationId;
  String? get userId => tokenSubject(_accessToken);

  /// Updates the active organization/tenant context and persists it to secure storage.
  Future<void> setOrganizationId(String? orgId) async {
    _organizationId = orgId;
    notifyListeners();
    if (orgId != null && orgId.isNotEmpty) {
      await _storage.write(organizationIdKey, orgId);
    } else {
      await _storage.delete(organizationIdKey);
    }
  }

  Future<String?> readLifeMapCaptureSessionId() =>
      _storage.read(lifeMapCaptureSessionKey);

  Future<void> writeLifeMapCaptureSessionId(String sessionId) =>
      _storage.write(lifeMapCaptureSessionKey, sessionId);

  Future<void> clearLifeMapCaptureSessionId() =>
      _storage.delete(lifeMapCaptureSessionKey);

  /// Whether biometric authentication is enabled for token protection.
  bool get isBiometricEnabled => _biometricEnabled;

  /// Whether credentials are held in memory but locked behind biometric local unlock.
  bool get isBiometricLocked => _biometricLocked;

  /// Whether credentials exist in memory regardless of biometric lock status.
  bool get hasStoredCredentials =>
      _accessToken != null && _accessToken!.isNotEmpty;

  /// Whether an access token is currently held in memory and unlocked.
  ///
  /// If biometric protection is enabled and the session is locked,
  /// this evaluates to false until [unlockBiometric] is called.
  bool get isAuthenticated => hasStoredCredentials && !_biometricLocked;

  /// Locks the session behind biometrics if biometric protection is enabled.
  void lockBiometric() {
    if (_biometricEnabled && !_biometricLocked) {
      _biometricLocked = true;
      notifyListeners();
    }
  }

  /// Unlocks the session upon successful biometric verification.
  void unlockBiometric() {
    if (_biometricLocked) {
      _biometricLocked = false;
      notifyListeners();
    }
  }

  /// Updates and persists the biometric authentication preference.
  Future<void> setBiometricEnabled(bool enabled) async {
    _biometricEnabled = enabled;
    if (!enabled) {
      _biometricLocked = false;
    }
    await _storage.write(biometricEnabledKey, enabled ? 'true' : 'false');
    notifyListeners();
  }

  /// Whether the in-memory access token is expired, missing, or unparseable.
  ///
  /// Used during [hydrate] to decide whether to restore or clear the session
  /// (Requirement 10.3). A missing token or a token without a parseable `exp`
  /// claim is treated as expired/invalid.
  bool get isExpired => isTokenExpired(_accessToken);

  /// Loads any persisted credentials on launch.
  ///
  /// * No stored token -> remains unauthenticated (login screen).
  /// * Valid stored token -> restores the authenticated session (10.2).
  /// * Expired/invalid stored token -> clears the store (10.3).
  Future<void> hydrate() async {
    final storedBio = await _storage.read(biometricEnabledKey);
    _biometricEnabled = storedBio == 'true';

    final storedEmail = await _storage.read(emailKey);
    final storedAccessToken = await _storage.read(accessTokenKey);
    final storedRefreshToken = await _storage.read(refreshTokenKey);
    final storedRole = await _storage.read(roleKey);
    final storedOrgId = await _storage.read(organizationIdKey);

    if (storedAccessToken == null || storedAccessToken.isEmpty) {
      _resetInMemory();
      notifyListeners();
      return;
    }

    _email = storedEmail;
    _accessToken = storedAccessToken;
    _refreshToken = storedRefreshToken;
    _role = storedRole;
    _organizationId = storedOrgId;

    if (isExpired) {
      // Expired or invalid stored token: clear credentials so the app routes
      // back to the login screen (Requirement 10.3).
      await clear();
      return;
    }

    if (_biometricEnabled) {
      _biometricLocked = true;
    }

    notifyListeners();
  }

  /// Stores the authenticated session credentials and persists them (10.1).
  Future<void> setSession({
    required String email,
    required String accessToken,
    required String refreshToken,
    required String role,
    String? organizationId,
  }) async {
    // Purge previous user's offline caches before storing new session tokens.
    if (_email != null || _accessToken != null) {
      await _purgeOfflineCaches(email: _email, token: _accessToken);
    }
    _email = email;
    _accessToken = accessToken;
    _refreshToken = refreshToken;
    _role = role;
    _organizationId = organizationId;
    _biometricLocked = false;
    // Notify synchronously (before awaiting persistence) so listeners react
    // immediately, matching the previous in-memory behavior.
    notifyListeners();

    await _storage.write(emailKey, email);
    await _storage.write(accessTokenKey, accessToken);
    await _storage.write(refreshTokenKey, refreshToken);
    await _storage.write(roleKey, role);
    if (organizationId != null && organizationId.isNotEmpty) {
      await _storage.write(organizationIdKey, organizationId);
    } else {
      await _storage.delete(organizationIdKey);
    }
  }

  /// Removes all stored credentials from memory and secure storage (10.5).
  Future<void> clear() async {
    final prevEmail = _email;
    final prevToken = _accessToken;
    _resetInMemory();
    notifyListeners();

    await _storage.delete(emailKey);
    await _storage.delete(accessTokenKey);
    await _storage.delete(refreshTokenKey);
    await _storage.delete(roleKey);
    await _storage.delete(organizationIdKey);
    await _purgeOfflineCaches(email: prevEmail, token: prevToken);
  }

  /// Explicitly purges all stored credentials, refresh tokens, and offline caches
  /// upon password reset or account recovery. Ensures zero stale tokens or
  /// cached medical data remain accessible on this device.
  Future<void> purgeOnPasswordReset() async {
    await clear();
  }

  Future<void> _purgeOfflineCaches({String? email, String? token}) async {
    await _storage.delete(careguardOfflineCacheKey);
    await _storage.delete(lifeMapReadCacheKey);
    await _storage.delete(lifeMapCaptureSessionKey);

    final sub = tokenSubject(token ?? _accessToken);
    if (sub != null && sub.isNotEmpty) {
      await _storage.delete(careguardScopedKey(sub));
      await _storage.delete(lifeMapScopedKey(sub));
    }
    final userEmail = email ?? _email;
    if (userEmail != null && userEmail.isNotEmpty) {
      await _storage.delete(careguardScopedKey(userEmail));
      await _storage.delete(lifeMapScopedKey(userEmail));
    }
  }

  void _resetInMemory() {
    _email = null;
    _accessToken = null;
    _refreshToken = null;
    _role = null;
    _organizationId = null;
    _biometricLocked = false;
  }

  /// Parses the `sub` (user identifier) claim from a JWT [token], returning
  /// `null` when the token is absent or cannot be parsed.
  static String? tokenSubject(String? token) {
    if (token == null || token.isEmpty) {
      return null;
    }

    final parts = token.split('.');
    if (parts.length != 3) {
      return null;
    }

    try {
      final payloadJson =
          utf8.decode(base64Url.decode(base64Url.normalize(parts[1])));
      final decoded = jsonDecode(payloadJson);
      if (decoded is! Map<String, dynamic>) {
        return null;
      }
      final sub = decoded['sub'] ?? decoded['user_id'] ?? decoded['id'];
      return sub?.toString();
    } catch (_) {
      return null;
    }
  }

  /// Pure, testable expiry check for a JWT access token.
  ///
  /// Returns `true` when [token] is null/empty, is not a parseable JWT, lacks
  /// an `exp` claim, or its `exp` (seconds since epoch) is at or before [now]
  /// (defaults to the current UTC time).
  static bool isTokenExpired(String? token, {DateTime? now}) {
    final expiry = tokenExpiry(token);
    if (expiry == null) {
      return true;
    }
    final reference = (now ?? DateTime.now()).toUtc();
    return !reference.isBefore(expiry);
  }

  /// Parses the `exp` claim from a JWT [token], returning its UTC expiry time,
  /// or `null` when the token is absent or cannot be parsed.
  static DateTime? tokenExpiry(String? token) {
    if (token == null || token.isEmpty) {
      return null;
    }

    final parts = token.split('.');
    if (parts.length != 3) {
      return null;
    }

    try {
      final payloadJson =
          utf8.decode(base64Url.decode(base64Url.normalize(parts[1])));
      final decoded = jsonDecode(payloadJson);
      if (decoded is! Map<String, dynamic>) {
        return null;
      }

      final exp = decoded['exp'];
      final seconds = _expToSeconds(exp);
      if (seconds == null) {
        return null;
      }

      return DateTime.fromMillisecondsSinceEpoch(seconds * 1000, isUtc: true);
    } catch (_) {
      return null;
    }
  }

  static int? _expToSeconds(Object? exp) {
    if (exp is int) {
      return exp;
    }
    if (exp is double) {
      return exp.round();
    }
    if (exp is String) {
      return int.tryParse(exp);
    }
    return null;
  }
}

/// Backwards-compatible alias so existing screens that reference `SessionStore`
/// (and `main.dart`'s `SessionStore()` construction) continue to work against
/// the persistent implementation.
typedef SessionStore = PersistentSessionStore;

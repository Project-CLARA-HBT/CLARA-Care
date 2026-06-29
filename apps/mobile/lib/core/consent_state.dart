/// Granular per-purpose consent model + persistence for CLARA_Mobile
/// (Requirement 8.1, 8.2, 8.4; Correctness Property P7).
///
/// This is the single client-side source of truth for the user's purpose-typed,
/// versioned, revocable consent (mirrors the web consent center). It is purely
/// additive and surfaced only behind `consent_center_mobile_enabled`
/// (Requirement 8.6 / 15.1): with the flag off the [ConsentCenterScreen] is
/// unreachable and nothing here runs.
///
/// Design principles preserved here:
///   * **Privacy-first defaults.** Every optional purpose defaults to *not
///     granted*; only the mandatory `coreService` purpose defaults to granted,
///     so analytics (and every other optional purpose) stays off until the user
///     explicitly opts in (Requirement 8.4, mirrors the analytics facade's
///     `consentGranted = false` default).
///   * **Analytics is wired to the facade.** Granting the `analytics` purpose
///     calls `Analytics.setConsent(granted: true)` and withdrawing it calls
///     `Analytics.setConsent(granted: false)` *immediately*, so transmission
///     begins/stops the moment the toggle flips (Requirement 8.4 / Property P7).
///   * **No PII.** Only a boolean grant + a policy version per purpose is ever
///     stored; no name/email/free-text is persisted or logged (Requirement
///     8.5 / 11.2).
///   * **Persistence via the secure-storage seam.** State is persisted through
///     the same [SessionSecureStorage] interface the session store uses, so it
///     is testable without platform channels and never leaves the device.
library;

import 'dart:convert';

import 'package:flutter/foundation.dart';

import 'analytics.dart';
import 'session_store.dart';

/// The current consent-policy version. Bumping this is how a new consent
/// version is rolled out; persisted state from an older version is still read
/// back, and re-affirming a purpose stamps it with the current version.
const String kConsentPolicyVersion = '2026-04-v1';

/// A purpose-typed processing consent (mirrors the web granular-consent set).
///
/// `coreService` is mandatory for the app to function; every other purpose is
/// optional and defaults to *not granted* (privacy-first).
enum ConsentPurpose {
  /// Core service: storing self-declared data to provide CLARA at all.
  coreService,

  /// Personalisation of recommendations/content.
  personalization,

  /// Use of de-identified data to improve CLARA / research.
  research,

  /// Cross-border processing of data.
  crossBorder,

  /// Sharing data via share links / referrals.
  sharing,

  /// Product analytics (consent-gated, PII-free).
  analytics,
}

/// Stable wire/storage key for a [ConsentPurpose] (snake_case, matches the
/// server-side purpose vocabulary). Used as the JSON key when persisting.
extension ConsentPurposeKey on ConsentPurpose {
  String get storageKey {
    switch (this) {
      case ConsentPurpose.coreService:
        return 'core_service';
      case ConsentPurpose.personalization:
        return 'personalization';
      case ConsentPurpose.research:
        return 'research';
      case ConsentPurpose.crossBorder:
        return 'cross_border';
      case ConsentPurpose.sharing:
        return 'sharing';
      case ConsentPurpose.analytics:
        return 'analytics';
    }
  }

  /// Whether this purpose is mandatory for the service to function. A mandatory
  /// purpose still exposes a toggle (for transparency) but defaults to granted.
  bool get isMandatory => this == ConsentPurpose.coreService;

  /// Vietnamese-first title (Requirement 5.5 copy convention).
  String get titleVi {
    switch (this) {
      case ConsentPurpose.coreService:
        return 'Dịch vụ cốt lõi';
      case ConsentPurpose.personalization:
        return 'Cá nhân hoá';
      case ConsentPurpose.research:
        return 'Nghiên cứu & cải thiện';
      case ConsentPurpose.crossBorder:
        return 'Xử lý xuyên biên giới';
      case ConsentPurpose.sharing:
        return 'Chia sẻ';
      case ConsentPurpose.analytics:
        return 'Phân tích sử dụng';
    }
  }

  /// Vietnamese-first description of what the purpose covers.
  String get descriptionVi {
    switch (this) {
      case ConsentPurpose.coreService:
        return 'Lưu trữ dữ liệu bạn tự khai báo để cung cấp các tính năng cơ bản '
            'của CLARA. Bắt buộc để sử dụng ứng dụng.';
      case ConsentPurpose.personalization:
        return 'Cá nhân hoá nội dung và gợi ý dựa trên hồ sơ của bạn.';
      case ConsentPurpose.research:
        return 'Sử dụng dữ liệu đã ẩn danh để cải thiện và nghiên cứu CLARA.';
      case ConsentPurpose.crossBorder:
        return 'Cho phép xử lý dữ liệu tại máy chủ ngoài lãnh thổ khi cần thiết.';
      case ConsentPurpose.sharing:
        return 'Cho phép tạo liên kết chia sẻ hồ sơ hoặc kết quả.';
      case ConsentPurpose.analytics:
        return 'Thu thập số liệu sử dụng ẩn danh (không kèm thông tin cá nhân) '
            'để cải thiện trải nghiệm.';
    }
  }
}

/// An immutable snapshot of the user's granular consent across every purpose.
///
/// Value-typed (with `==`/`hashCode`) so it is trivially testable, and
/// round-trips through [toJson]/[fromJson] for persistence.
@immutable
class ConsentState {
  ConsentState({
    required Map<ConsentPurpose, bool> grants,
    this.version = kConsentPolicyVersion,
  }) : grants = Map.unmodifiable(grants);

  /// Grant flag per purpose. Always contains an entry for every
  /// [ConsentPurpose] when produced by this class's factories.
  final Map<ConsentPurpose, bool> grants;

  /// The policy version these grants were last affirmed against.
  final String version;

  /// Privacy-first defaults: only the mandatory `coreService` purpose is
  /// granted; every optional purpose (including analytics) is off until the
  /// user explicitly opts in (Requirement 8.4).
  factory ConsentState.defaults() {
    return ConsentState(
      grants: <ConsentPurpose, bool>{
        for (final purpose in ConsentPurpose.values)
          purpose: purpose.isMandatory,
      },
    );
  }

  /// Whether [purpose] is currently granted (missing ⇒ not granted).
  bool isGranted(ConsentPurpose purpose) => grants[purpose] == true;

  /// Returns a copy with [purpose] set to [granted], stamped with the current
  /// policy version.
  ConsentState withGrant(ConsentPurpose purpose, bool granted) {
    return ConsentState(
      grants: <ConsentPurpose, bool>{...grants, purpose: granted},
      version: kConsentPolicyVersion,
    );
  }

  /// Serialises to a PII-free JSON map: a `version` plus a `purposes` object of
  /// `{ storageKey: bool }`.
  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'version': version,
      'purposes': <String, bool>{
        for (final entry in grants.entries) entry.key.storageKey: entry.value,
      },
    };
  }

  /// Parses a persisted snapshot, falling back to [ConsentState.defaults] for
  /// any missing/invalid purpose so an upgrade never loses the user's choices
  /// nor silently grants a new purpose.
  factory ConsentState.fromJson(Object? json) {
    final defaults = ConsentState.defaults();
    if (json is! Map) {
      return defaults;
    }
    final purposes = json['purposes'];
    final version =
        json['version'] is String ? json['version'] as String : kConsentPolicyVersion;
    final byKey = <String, bool>{};
    if (purposes is Map) {
      purposes.forEach((key, value) {
        byKey[key.toString()] = value == true;
      });
    }
    return ConsentState(
      grants: <ConsentPurpose, bool>{
        for (final purpose in ConsentPurpose.values)
          purpose: byKey.containsKey(purpose.storageKey)
              ? byKey[purpose.storageKey]!
              : defaults.isGranted(purpose),
      },
      version: version,
    );
  }

  @override
  bool operator ==(Object other) {
    if (other is! ConsentState) return false;
    if (other.version != version) return false;
    if (other.grants.length != grants.length) return false;
    for (final purpose in ConsentPurpose.values) {
      if (other.isGranted(purpose) != isGranted(purpose)) return false;
    }
    return true;
  }

  @override
  int get hashCode => Object.hash(
        version,
        Object.hashAll(
          ConsentPurpose.values.map((p) => isGranted(p)),
        ),
      );

  @override
  String toString() => 'ConsentState(version: $version, grants: $grants)';
}

/// Persistent, observable granular-consent store.
///
/// Backs an immutable [ConsentState] with the [SessionSecureStorage] seam and
/// keeps the [Analytics] facade in sync: whenever the `analytics` purpose
/// changes (including on [load]), it calls [Analytics.setConsent] so
/// transmission begins on grant and stops immediately on withdrawal
/// (Requirement 8.4 / Property P7).
class ConsentStore extends ChangeNotifier {
  ConsentStore({
    required SessionSecureStorage storage,
    Analytics? analytics,
  })  : _storage = storage,
        _analytics = analytics ?? getAnalyticsClient();

  /// Secure-storage key holding the JSON-encoded [ConsentState].
  static const String storageKey = 'clara.consent.state';

  final SessionSecureStorage _storage;
  final Analytics _analytics;

  ConsentState _state = ConsentState.defaults();
  bool _loaded = false;

  /// The current consent snapshot (defaults until [load] completes).
  ConsentState get state => _state;

  /// Whether persisted state has been loaded at least once.
  bool get loaded => _loaded;

  /// Whether [purpose] is currently granted.
  bool isGranted(ConsentPurpose purpose) => _state.isGranted(purpose);

  /// Loads any persisted consent from secure storage and synchronises the
  /// analytics facade with the persisted analytics grant. Falls back to
  /// privacy-first defaults when nothing is stored or the blob is corrupt.
  Future<void> load() async {
    ConsentState restored;
    try {
      final raw = await _storage.read(storageKey);
      if (raw == null || raw.isEmpty) {
        restored = ConsentState.defaults();
      } else {
        restored = ConsentState.fromJson(jsonDecode(raw));
      }
    } catch (_) {
      restored = ConsentState.defaults();
    }
    _state = restored;
    _loaded = true;
    // Keep the analytics facade consistent with the restored grant so a user
    // who previously opted in resumes transmission, and one who never did (or
    // withdrew) stays suppressed (Requirement 8.4).
    _analytics.setConsent(granted: _state.isGranted(ConsentPurpose.analytics));
    notifyListeners();
  }

  /// Grants or withdraws [purpose], persists the new state, and — for the
  /// `analytics` purpose — updates the analytics facade immediately so
  /// transmission begins on grant and stops on withdrawal (Requirement 8.4).
  Future<void> setConsent(ConsentPurpose purpose, bool granted) async {
    final next = _state.withGrant(purpose, granted);
    if (next == _state) {
      return;
    }
    _state = next;

    // Wire the analytics purpose to the facade BEFORE awaiting persistence so
    // suppression/transmission flips synchronously with the toggle.
    if (purpose == ConsentPurpose.analytics) {
      _analytics.setConsent(granted: granted);
    }
    notifyListeners();

    try {
      await _storage.write(storageKey, jsonEncode(_state.toJson()));
    } catch (_) {
      // Persistence failures must never break the consent flow; the in-memory
      // state (and the analytics facade) already reflect the user's choice.
    }
  }
}

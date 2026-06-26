import 'dart:convert';

/// Mobile analytics facade for CLARA_Mobile.
///
/// This mirrors the web facade contract (`apps/web/lib/analytics`):
/// `init` / `identify` / `capture`, with the same privacy rules.
///
///  * Safe no-op when no credentials are configured (Requirement 9.5).
///  * Suppresses all transmission until analytics consent is granted
///    (Requirement 9.3).
///  * Strips PII from every event payload before transmission
///    (Requirement 9.4).
///  * Identifies users by an opaque, deterministic pseudonymous id rather
///    than email or name (Requirement 9.6).
///
/// A provider-agnostic [AnalyticsTransport] keeps the SDK choice
/// (PostHog / Google Analytics / Plausible) swappable. The default
/// [NoOpAnalyticsTransport] performs no I/O; a real provider can be wired
/// later without touching call sites.

/// Immutable analytics configuration (provider credentials + host).
class AnalyticsConfig {
  const AnalyticsConfig({
    required this.provider,
    required this.apiKey,
    this.host,
  });

  final String provider;
  final String apiKey;
  final String? host;

  /// Empty provider or key means analytics is unconfigured and must no-op.
  bool get isConfigured => provider.trim().isNotEmpty && apiKey.trim().isNotEmpty;

  /// Reads credentials from `--dart-define` compile-time environment values,
  /// mirroring the web `ANALYTICS_SDK_*` keys. Absent values yield an
  /// unconfigured (no-op) config.
  factory AnalyticsConfig.fromEnvironment() {
    return const AnalyticsConfig(
      provider: String.fromEnvironment('ANALYTICS_SDK_PROVIDER'),
      apiKey: String.fromEnvironment('ANALYTICS_SDK_KEY'),
      host: String.fromEnvironment('ANALYTICS_SDK_HOST'),
    );
  }

  static const AnalyticsConfig disabled =
      AnalyticsConfig(provider: '', apiKey: '');
}

/// A named product event with optional structured properties.
class AnalyticsEvent {
  const AnalyticsEvent(this.name, [this.props = const <String, Object?>{}]);

  final String name;
  final Map<String, Object?> props;

  AnalyticsEvent copyWith({Map<String, Object?>? props}) {
    return AnalyticsEvent(name, props ?? this.props);
  }
}

/// Provider adapter contract. Implement one per analytics provider.
abstract class AnalyticsTransport {
  void init(AnalyticsConfig config);
  void identify(String distinctId);
  void capture(AnalyticsEvent event);
}

/// Default transport that performs no I/O. Used until a real provider is wired.
class NoOpAnalyticsTransport implements AnalyticsTransport {
  const NoOpAnalyticsTransport();

  @override
  void init(AnalyticsConfig config) {}

  @override
  void identify(String distinctId) {}

  @override
  void capture(AnalyticsEvent event) {}
}

/// Named events for the primary mobile screens.
class MobileAnalyticsEvents {
  const MobileAnalyticsEvents._();

  static const String loginViewed = 'mobile_login_viewed';
  static const String loginSucceeded = 'mobile_login_succeeded';
  static const String dashboardViewed = 'mobile_dashboard_viewed';
  static const String researchViewed = 'mobile_research_viewed';
  static const String researchSubmitted = 'mobile_research_submitted';
  static const String careguardViewed = 'mobile_careguard_viewed';
  static const String careguardAnalyzed = 'mobile_careguard_analyzed';
  static const String councilViewed = 'mobile_council_viewed';
  static const String councilRun = 'mobile_council_run';
  static const String phrViewed = 'mobile_phr_viewed';
  static const String phrSaved = 'mobile_phr_saved';
}

/// Consent + PII guarded analytics client mirroring the web `AnalyticsClient`.
class Analytics {
  Analytics({AnalyticsTransport? transport})
      : _transport = transport ?? const NoOpAnalyticsTransport();

  final AnalyticsTransport _transport;

  AnalyticsConfig _config = AnalyticsConfig.disabled;
  bool _consentGranted = false;
  bool _initialized = false;

  /// True only when valid provider credentials are present.
  bool get isConfigured => _config.isConfigured;

  /// True only when the user has granted analytics consent.
  bool get consentGranted => _consentGranted;

  /// Initializes the facade. The underlying transport is only initialized
  /// once credentials are present AND consent has been granted, so an
  /// unconfigured app (Requirement 9.5) or an un-consented user
  /// (Requirement 9.3) never loads or transmits through the SDK.
  void init(AnalyticsConfig config, {bool consentGranted = false}) {
    _config = config;
    _consentGranted = consentGranted;
    _ensureInitialized();
  }

  /// Updates analytics consent at runtime (e.g., after the consent gate).
  ///
  /// Granting consent lazily initializes the transport so the SDK is only
  /// loaded after the user opts in (mirrors the web `setConsent`).
  void setConsent({required bool granted}) {
    _consentGranted = granted;
    if (granted) {
      _ensureInitialized();
    }
  }

  /// Identifies the current user by an opaque pseudonymous id.
  ///
  /// No-op when unconfigured or consent is not granted. The raw [stableUserKey]
  /// (e.g., user id or email) is never transmitted — only its hash.
  void identify(String stableUserKey) {
    if (!isConfigured) {
      return; // 9.5 safe no-op without credentials
    }
    if (!_consentGranted) {
      return; // 9.3 suppress transmission without consent
    }
    final distinctId = pseudonymousId(stableUserKey);
    if (distinctId.isEmpty) {
      return;
    }
    _ensureInitialized();
    _safe(() => _transport.identify(distinctId)); // 9.6 opaque pseudonymous id
  }

  /// Captures a named event after stripping PII.
  ///
  /// No-op when unconfigured (Requirement 9.5) or consent is not granted
  /// (Requirement 9.3). PII keys are removed before transmission
  /// (Requirement 9.4).
  void capture(AnalyticsEvent event) {
    if (!isConfigured) {
      return; // 9.5 safe no-op without credentials
    }
    if (!_consentGranted) {
      return; // 9.3 suppress transmission without consent
    }
    _ensureInitialized();
    _safe(() => _transport.capture(stripPii(event))); // 9.4 PII-free payload
  }

  /// Lazily initializes the underlying transport exactly once, and only when
  /// the facade is both configured (9.5) and consented (9.3). This keeps a
  /// real provider SDK from loading or transmitting before the user opts in.
  void _ensureInitialized() {
    if (_initialized) {
      return;
    }
    if (!isConfigured) {
      return; // 9.5 — no credentials, stay a no-op
    }
    if (!_consentGranted) {
      return; // 9.3 — do not load/transmit without consent
    }
    _safe(() => _transport.init(_config));
    _initialized = true;
  }

  /// Convenience: emit a named event with optional properties.
  ///
  /// Mirrors the web facade's `AnalyticsClient.track`. Subject to the same
  /// no-op (9.5), consent suppression (9.3), and PII-stripping (9.4) rules as
  /// [capture], since it delegates to it.
  void track(String name,
      {Map<String, Object?> props = const <String, Object?>{}}) {
    capture(AnalyticsEvent(name, props));
  }

  /// Convenience: emit a screen-view event for one of the primary screens.
  void captureScreenView(String eventName,
      {Map<String, Object?> props = const <String, Object?>{}}) {
    capture(AnalyticsEvent(eventName, props));
  }

  /// Runs a transport call without ever throwing into product flows.
  ///
  /// Analytics failures are non-fatal and must never break a screen
  /// (mirrors the web `AnalyticsClient.safe`).
  void _safe(void Function() fn) {
    try {
      fn();
    } catch (_) {
      // Swallow: analytics must never disrupt the user-facing flow.
    }
  }
}

/// Creates a new [Analytics] client.
///
/// Mirrors the web `createAnalyticsClient`. Reads credentials from the
/// compile-time environment by default (unconfigured → safe no-op, 9.5) and
/// selects the [NoOpAnalyticsTransport] until a real provider transport is
/// wired. Pass an explicit [transport] in tests.
Analytics createAnalyticsClient({
  AnalyticsConfig? config,
  AnalyticsTransport? transport,
  bool consentGranted = false,
}) {
  final analytics = Analytics(transport: transport);
  analytics.init(
    config ?? AnalyticsConfig.fromEnvironment(),
    consentGranted: consentGranted,
  );
  return analytics;
}

Analytics? _sharedClient;

/// Returns the process-wide [Analytics] client, creating it on first use.
///
/// Mirrors the web `getAnalyticsClient` lazy singleton so primary screens can
/// emit named events through a single consent/PII-guarded client.
Analytics getAnalyticsClient() {
  return _sharedClient ??= createAnalyticsClient();
}

/// Resets the shared client. Intended for tests so each case starts from a
/// known, unconfigured state.
void resetAnalyticsClientForTest() {
  _sharedClient = null;
}

/// Returns a copy of [event] with all PII keys removed from its properties.
///
/// Drops names, emails, free-text queries, and drug/medication lists at any
/// nesting depth (Requirement 9.4). Pure and deterministic for testing.
AnalyticsEvent stripPii(AnalyticsEvent event) {
  return AnalyticsEvent(event.name, _stripPiiMap(event.props));
}

/// Produces a stable, opaque pseudonymous identifier from a stable user key.
///
/// Deterministic (same input yields the same id) and one-way: the returned id
/// never equals or contains the original email/name (Requirement 9.6). Returns
/// an empty string for an empty key.
String pseudonymousId(String stableUserKey) {
  final normalized = stableUserKey.trim();
  if (normalized.isEmpty) {
    return '';
  }
  return 'u_${_fnv1a64Hex(normalized)}';
}

// --- PII stripping internals -------------------------------------------------

/// Exact (normalized) keys that always denote PII or free-text content.
///
/// Mirrors the web facade denylist (`apps/web/lib/analytics`) so both clients
/// strip the same fields before transmission (Requirement 9.4).
const Set<String> _deniedExactKeys = <String>{
  // Names
  'name',
  'fullname',
  'firstname',
  'lastname',
  'givenname',
  'familyname',
  'surname',
  'username',
  'displayname',
  'patientname',
  // Contact / identity
  'email',
  'emailaddress',
  'mail',
  'phone',
  'phonenumber',
  'address',
  'dob',
  'dateofbirth',
  'birthdate',
  'ssn',
  'nationalid',
  // Free-text query content
  'q',
  'query',
  'question',
  'prompt',
  'message',
  'text',
  'content',
  'input',
  'userinput',
  'search',
  'searchquery',
  'body',
  'note',
  'notes',
  'transcript',
  // Medical content
  'drug',
  'drugs',
  'druglist',
  'medication',
  'medications',
  'medicine',
  'medicines',
  'symptom',
  'symptoms',
  'allergy',
  'allergies',
  'diagnosis',
  'prescription',
  'labs',
};

/// Normalized substrings that mark a property as PII / free-text medical data.
///
/// Mirrors the web facade pattern list so nested/compound keys such as
/// `patient_email` or `drug_names` are dropped consistently (Requirement 9.4).
const Set<String> _deniedSubstrings = <String>{
  'email',
  'query',
  'question',
  'prompt',
  'freetext',
  'userinput',
  'drug',
  'medicine',
  'medication',
  'symptom',
  'allergy',
  'diagnos',
  'prescription',
  'patient',
  'password',
};

bool _isPiiKey(String key) {
  final normalized = key.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
  if (normalized.isEmpty) {
    return false;
  }
  if (_deniedExactKeys.contains(normalized)) {
    return true;
  }
  return _deniedSubstrings.any(normalized.contains);
}

Map<String, Object?> _stripPiiMap(Map<String, Object?> input) {
  final result = <String, Object?>{};
  input.forEach((key, value) {
    if (_isPiiKey(key)) {
      return; // drop PII key entirely
    }
    result[key] = _stripPiiValue(value);
  });
  return result;
}

Object? _stripPiiValue(Object? value) {
  if (value is Map) {
    return _stripPiiMap(
      value.map((k, v) => MapEntry(k.toString(), v)),
    );
  }
  if (value is List) {
    return value.map(_stripPiiValue).toList();
  }
  return value;
}

/// FNV-1a 64-bit hash, hex-encoded. Uses [BigInt] so results are identical on
/// native and web targets (no platform-dependent integer overflow).
String _fnv1a64Hex(String input) {
  final mask = (BigInt.one << 64) - BigInt.one;
  final prime = BigInt.parse('1099511628211');
  var hash = BigInt.parse('14695981039346656037'); // FNV offset basis

  for (final byte in utf8.encode(input)) {
    hash = (hash ^ BigInt.from(byte)) & mask;
    hash = (hash * prime) & mask;
  }

  return hash.toRadixString(16).padLeft(16, '0');
}

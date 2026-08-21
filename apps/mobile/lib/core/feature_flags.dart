/// Mobile feature-flag resolver for CLARA_Mobile (Requirements 13.1, 15.1).
///
/// This is the single place the app resolves the **new, additive** mobile
/// feature gates. It combines two sources, both of which default to OFF so the
/// resolver is fail-closed by construction:
///
///   1. **Server, role-scoped flags** — the `feature_flags` map returned by
///      `GET /api/v1/mobile/summary` for the authenticated role (Req 13.1).
///   2. **Build-time `--dart-define` defaults** — compile-time switches for
///      surfaces not yet represented in the summary contract (Req 15.1),
///      mirroring the existing `kCouncilMobileParityEnabled` /
///      `CAREGUARD_MOBILE_CABINET_ENABLED` pattern.
///
/// Resolution semantics ("combine"): a gate is open when **either** the server
/// grants it for the role **or** the build was compiled with its define on:
///
///   `isEnabled(key) == serverSaysTrue(key) || buildDefault(key)`
///
/// Both inputs default to `false`, so:
///   * Every new flag defaults to `false` (Req 15.1).
///   * A null/unloadable summary, a non-map `feature_flags`, a missing key, or a
///     non-`true` value all resolve to `false` — unknown/missing ⇒ false
///     (fail-closed, mirroring `dashboard_screen.dart`'s `_featureEnabled`).
///
/// Production builds ship with all `--dart-define` defaults off, so the server's
/// role-scoped flags are authoritative there; the build-time defaults exist for
/// staged enablement and QA/dev builds of surfaces the summary does not yet
/// carry. The resolver never changes any CLARA_API contract (Req 15.5) and does
/// not perform any I/O — it is a pure function of the summary plus compile-time
/// constants, so it can be unit/property tested without rendering widgets.
library;

/// The new, additive mobile feature-flag keys.
///
/// Each key matches both the server `feature_flags` map key and the
/// corresponding `--dart-define` (uppercased). All gates these guard ship dark
/// (default `false`) until explicitly enabled per role/environment.
class MobileFeatureFlags {
  const MobileFeatureFlags._();

  /// Conversational chat surface (Requirement 1).
  static const String chatMobileEnabled = 'chat_mobile_enabled';

  /// Self-med medicine-cabinet CRUD feeding the DDI check (Requirement 3).
  static const String selfmedCabinetMobileEnabled =
      'selfmed_cabinet_mobile_enabled';

  /// Ambient scribe surface (Requirement 4).
  static const String scribeMobileEnabled = 'scribe_mobile_enabled';

  /// Enhanced PHR reads — export + emergency card (Requirement 5).
  static const String phrEnhancedMobileEnabled = 'phr_enhanced_mobile_enabled';

  /// Model family/version disclosure chips (Requirement 7).
  static const String modelDisclosureMobileEnabled =
      'model_disclosure_mobile_enabled';

  /// Versioned AI transparency notice gate (Requirement 7).
  static const String transparencyNoticeMobileEnabled =
      'transparency_notice_mobile_enabled';

  /// Granular consent center + DSAR self-service (Requirement 8).
  static const String consentCenterMobileEnabled =
      'consent_center_mobile_enabled';

  /// Read-only shared-resource / deep-link surface (Requirement 12).
  static const String sharingMobileEnabled = 'sharing_mobile_enabled';

  /// Modernized ChatGPT-class chat surface + web-palette theme
  /// (clara-mobile-ux-polish, Requirement 6, 10).
  static const String uxPolishEnabled = 'mobile_ux_polish_enabled';

  /// Server-authoritative LifeMap visit-draft capability. Unlike the staged
  /// mobile UI flags above, this mirrors an API feature gate and deliberately
  /// has no client-side build override: an older or misconfigured client must
  /// not expose a route whose safe server contract is unavailable.
  static const String lifeMapVietnameseDrafts = 'lifemap_vietnamese_drafts';

  /// All new mobile flag keys, in staged-enablement order.
  static const List<String> all = <String>[
    chatMobileEnabled,
    selfmedCabinetMobileEnabled,
    scribeMobileEnabled,
    phrEnhancedMobileEnabled,
    modelDisclosureMobileEnabled,
    transparencyNoticeMobileEnabled,
    consentCenterMobileEnabled,
    sharingMobileEnabled,
    uxPolishEnabled,
    lifeMapVietnameseDrafts,
  ];
}

// --- Build-time (`--dart-define`) defaults (all default false) ---------------
//
// Each must be a compile-time constant with a literal define name so the value
// is resolved at build time, matching the existing mobile flag pattern.

const bool _chatMobileDefault =
    bool.fromEnvironment('CHAT_MOBILE_ENABLED', defaultValue: false);
const bool _selfmedCabinetMobileDefault =
    bool.fromEnvironment('SELFMED_CABINET_MOBILE_ENABLED', defaultValue: false);
const bool _scribeMobileDefault =
    bool.fromEnvironment('SCRIBE_MOBILE_ENABLED', defaultValue: false);
const bool _phrEnhancedMobileDefault =
    bool.fromEnvironment('PHR_ENHANCED_MOBILE_ENABLED', defaultValue: false);
const bool _modelDisclosureMobileDefault = bool.fromEnvironment(
    'MODEL_DISCLOSURE_MOBILE_ENABLED',
    defaultValue: false);
const bool _transparencyNoticeMobileDefault = bool.fromEnvironment(
    'TRANSPARENCY_NOTICE_MOBILE_ENABLED',
    defaultValue: false);
const bool _consentCenterMobileDefault =
    bool.fromEnvironment('CONSENT_CENTER_MOBILE_ENABLED', defaultValue: false);
const bool _sharingMobileDefault =
    bool.fromEnvironment('SHARING_MOBILE_ENABLED', defaultValue: false);
const bool _uxPolishMobileDefault =
    bool.fromEnvironment('MOBILE_UX_POLISH_ENABLED', defaultValue: false);

/// The compile-time `--dart-define` defaults keyed by flag. All `false` unless
/// the build explicitly enabled one. Used as the build-time half of the
/// resolver's combine step.
const Map<String, bool> kMobileFeatureFlagBuildDefaults = <String, bool>{
  MobileFeatureFlags.chatMobileEnabled: _chatMobileDefault,
  MobileFeatureFlags.selfmedCabinetMobileEnabled: _selfmedCabinetMobileDefault,
  MobileFeatureFlags.scribeMobileEnabled: _scribeMobileDefault,
  MobileFeatureFlags.phrEnhancedMobileEnabled: _phrEnhancedMobileDefault,
  MobileFeatureFlags.modelDisclosureMobileEnabled:
      _modelDisclosureMobileDefault,
  MobileFeatureFlags.transparencyNoticeMobileEnabled:
      _transparencyNoticeMobileDefault,
  MobileFeatureFlags.consentCenterMobileEnabled: _consentCenterMobileDefault,
  MobileFeatureFlags.sharingMobileEnabled: _sharingMobileDefault,
  MobileFeatureFlags.uxPolishEnabled: _uxPolishMobileDefault,
  MobileFeatureFlags.lifeMapVietnameseDrafts: false,
};

// --- Experience_V2 build gate (single switch, default OFF) -------------------
//
// The one compile-time gate for the modernized "Experience_V2" mobile UI/UX
// (Material 3 design system, adaptive shell, modern Home, onboarding, polished
// states, micro-interactions, branding, language toggle). Read at exactly one
// place — `app.dart` — to choose the authenticated root surface.

/// The single build-time gate for the **liquid-glass** visual layer
/// (clara-mobile-liquid-glass, R1.1).
///
/// Resolved at compile time via `--dart-define=MOBILE_LIQUID_GLASS_ENABLED=…`
/// with a literal define name. Defaults to `false` (fail-closed) so the app is
/// byte-for-byte the Experience_V3 redesign until glass is enabled. When on (and
/// the redesign is on), chrome surfaces render the iOS-26-inspired translucent
/// material; clinical content stays opaque regardless. This gate is additionally
/// ANDed at runtime with the device-capability probe (reduce-transparency /
/// low-end), so a build with glass on still degrades to opaque where needed. It
/// changes no CLARA_API contract — client-side rendering only.
const bool kMobileLiquidGlassEnabled = bool.fromEnvironment(
  'MOBILE_LIQUID_GLASS_ENABLED',
  defaultValue: false,
);

/// The single build-time gate for the modern **Experience_V3 redesign**
/// (clara-mobile-redesign).
///
/// Resolved at compile time via `--dart-define=MOBILE_REDESIGN_ENABLED=…` with a
/// literal define name, mirroring [kMobileExperienceV2Enabled]. Defaults to
/// `false` (fail-closed) so the app is byte-for-byte the current experience
/// until the redesign is enabled. When on, `app.dart` selects the redesigned
/// authenticated root (`RedesignShell`) and pins `MaterialApp.themeMode` from
/// the persisted theme preference (default light). This gate is checked BEFORE
/// [kMobileExperienceV2Enabled], so it is a strict superset: the redesign wins
/// when both are on. It changes no CLARA_API contract — client-side surface
/// selection only.
const bool kMobileRedesignEnabled = bool.fromEnvironment(
  'MOBILE_REDESIGN_ENABLED',
  defaultValue: false,
);

/// The single build-time gate for the **unified** CLARA_Mobile experience
/// (spec: .kiro/specs/clara-mobile-unified).
///
/// This collapses the three historical layers (legacy Dashboard, Experience_V2,
/// Experience_V3 redesign) into ONE product-aligned client whose information
/// architecture matches the current web product: a Today home, LifeMap, a
/// unified Medicines hub, an Ask-CLARA action, and a Profile hub (PHR, Visits,
/// Family, Connected Health, Consent, Evidence, Settings).
///
/// Resolved at compile time via `--dart-define=MOBILE_UNIFIED_ENABLED=…`.
/// Defaults to `true`: the unified client is now the shipped default (Phase 7.3
/// of the spec), superseding the legacy Dashboard, Experience_V2, and the V3
/// redesign roots. Ship `--dart-define=MOBILE_UNIFIED_ENABLED=false` to fall
/// back to the prior root selection for A/B or rollback. This gate is checked
/// BEFORE
/// [kMobileRedesignEnabled] and [kMobileExperienceV2Enabled] in `app.dart`, so
/// it is a strict superset: when on, it selects the unified authenticated root
/// (`UnifiedRoot` → `UnifiedShell`). It changes no CLARA_API contract — it gates
/// only client-side surface selection.
const bool kMobileUnifiedEnabled = bool.fromEnvironment(
  'MOBILE_UNIFIED_ENABLED',
  defaultValue: true,
);

/// Build-time gate for the CLARA Health Social community surface on mobile
/// (spec: .kiro/specs/clara-health-social). Default OFF (fail-closed): when off,
/// no social entry is shown and no social route is called, so the app is
/// byte-for-byte the current experience. The server also gates every
/// `/api/v1/social/*` route behind its own `SOCIAL_PLATFORM_ENABLED` master
/// flag (404 when off), so this client gate never exposes a disabled backend.
const bool kMobileSocialEnabled = bool.fromEnvironment(
  'MOBILE_SOCIAL_ENABLED',
  defaultValue: false,
);

/// The single build-time gate for the modern Experience_V2 mobile UI/UX
/// (Requirements 1.1, 1.6).
///
/// Resolved at compile time via `--dart-define=MOBILE_EXPERIENCE_V2_ENABLED=…`
/// with a literal define name, mirroring the existing `_chatMobileDefault`
/// pattern. Defaults to `false` (fail-closed): when off, the app is
/// byte-for-byte the legacy experience (`ClaraApp` → `DashboardScreen`) and no
/// Experience_V2 surface is constructed. This gate is purely additive — it
/// changes no CLARA_API contract and gates only client-side surface selection.
const bool kMobileExperienceV2Enabled = bool.fromEnvironment(
  'MOBILE_EXPERIENCE_V2_ENABLED',
  defaultValue: false,
);

/// The compile-time half of the `mobile_ux_polish_enabled` gate
/// (clara-mobile-ux-polish, Requirement 6, 10).
///
/// Governs the **app-root theme palette** (`app.dart`), which is built at
/// `MaterialApp` construction time — before any server summary is loaded — so
/// it cannot depend on the runtime [MobileFeatureFlagResolver]. Resolved via
/// `--dart-define=MOBILE_UX_POLISH_ENABLED=…`, mirroring
/// [kMobileExperienceV2Enabled]. Defaults to `false` (fail-closed): when off,
/// the theme is byte-for-byte the pre-feature teal-seed theme. The runtime
/// resolver getter [MobileFeatureFlagResolver.uxPolishEnabled] governs the
/// polished chat UI itself; because the resolver combines `server OR
/// build-default`, a build compiled with this define on turns on both
/// consistently.
const bool kMobileUxPolishEnabled = _uxPolishMobileDefault;

/// Resolves mobile feature gates from the `mobile/summary` `feature_flags` map
/// combined with the compile-time `--dart-define` defaults.
///
/// Construct one per loaded summary (e.g., on the dashboard) and pass it to the
/// screens that gate on these flags. Tests may inject [buildDefaults] to
/// exercise the build-time half without recompiling with defines.
class MobileFeatureFlagResolver {
  /// Builds a resolver from a raw `mobile/summary` response [summary].
  ///
  /// A `null` summary, or one whose `feature_flags` is missing or not a
  /// `Map`, yields an empty server-flag set — every gate then resolves to its
  /// build-time default (all `false` in a normal build), i.e. fail-closed.
  MobileFeatureFlagResolver({
    Map<String, dynamic>? summary,
    Map<String, bool> buildDefaults = kMobileFeatureFlagBuildDefaults,
  })  : _serverFlags = _extractServerFlags(summary),
        _buildDefaults = buildDefaults;

  final Map<String, bool> _serverFlags;
  final Map<String, bool> _buildDefaults;

  /// Reads the server `feature_flags` map, mirroring `dashboard_screen.dart`'s
  /// `_featureEnabled`: only an explicit boolean `true` counts as granted; any
  /// other value (missing, `null`, non-bool, `false`) is treated as not
  /// granted by the server.
  static Map<String, bool> _extractServerFlags(Map<String, dynamic>? summary) {
    if (summary == null) {
      return const <String, bool>{};
    }
    final flags = summary['feature_flags'];
    if (flags is! Map) {
      return const <String, bool>{};
    }
    final result = <String, bool>{};
    flags.forEach((key, value) {
      result[key.toString()] = value == true;
    });
    return result;
  }

  /// Whether the server granted [key] for the authenticated role.
  bool serverGranted(String key) => _serverFlags[key] == true;

  /// Whether the build was compiled with the `--dart-define` default for [key].
  bool buildDefault(String key) => _buildDefaults[key] == true;

  /// Resolves a single gate: open when the server grants it **or** the build
  /// default enables it. Unknown/missing keys resolve to `false` (fail-closed).
  bool isEnabled(String key) => serverGranted(key) || buildDefault(key);

  // --- Convenience getters for the known new gates ---------------------------

  /// Chat surface gate (Requirement 1).
  bool get chatEnabled => isEnabled(MobileFeatureFlags.chatMobileEnabled);

  /// Self-med cabinet gate (Requirement 3).
  bool get selfMedCabinetEnabled =>
      isEnabled(MobileFeatureFlags.selfmedCabinetMobileEnabled);

  /// Ambient scribe gate (Requirement 4).
  bool get scribeEnabled => isEnabled(MobileFeatureFlags.scribeMobileEnabled);

  /// Enhanced PHR reads gate (Requirement 5).
  bool get phrEnhancedEnabled =>
      isEnabled(MobileFeatureFlags.phrEnhancedMobileEnabled);

  /// Model disclosure chips gate (Requirement 7).
  bool get modelDisclosureEnabled =>
      isEnabled(MobileFeatureFlags.modelDisclosureMobileEnabled);

  /// AI transparency notice gate (Requirement 7).
  bool get transparencyNoticeEnabled =>
      isEnabled(MobileFeatureFlags.transparencyNoticeMobileEnabled);

  /// Consent center + DSAR gate (Requirement 8).
  bool get consentCenterEnabled =>
      isEnabled(MobileFeatureFlags.consentCenterMobileEnabled);

  /// Sharing / deep-link gate (Requirement 12).
  bool get sharingEnabled => isEnabled(MobileFeatureFlags.sharingMobileEnabled);

  /// Modernized chat + web-palette theme gate (clara-mobile-ux-polish).
  bool get uxPolishEnabled => isEnabled(MobileFeatureFlags.uxPolishEnabled);

  /// Read-only Vietnamese LifeMap visit-preparation drafts. This uses the
  /// server capability directly and therefore remains closed if the mobile
  /// summary could not be read or the server disables the endpoint.
  bool get lifeMapVietnameseDraftsEnabled =>
      serverGranted(MobileFeatureFlags.lifeMapVietnameseDrafts);

  /// A snapshot of every known new gate's resolved value. Useful for tiles and
  /// for asserting flags-off equivalence in tests (Property 1).
  Map<String, bool> get resolved => <String, bool>{
        for (final key in MobileFeatureFlags.all) key: isEnabled(key),
      };
}
